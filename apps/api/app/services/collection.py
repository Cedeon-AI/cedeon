"""Collection tracking: turning a confirmed recovery into recoverables and moving
each one from notified to cash collected (docs/DECISIONS.md ADR-0024).

No AI. The expected amount is a fact carried from the immutable calculation; the
agreed / billed / collected figures are human-entered facts. Every change is on
the append-only audit log.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_correlation_id
from app.db.models.recoveries import Recoverable, RecoveryCalculation, RecoveryCandidate
from app.domain.audit import ActorType, AuditRecord
from app.domain.recoveries import (
    RecoverableRow,
    RecoverableStatus,
    RecoverableSummary,
    RecoveryCandidateStatus,
    summarize_recoverables,
)
from app.repositories.audit import AuditRepository
from app.repositories.recoveries import RecoverableRepository, RecoveryCandidateRepository
from app.services.auth import AuthenticatedContext
from app.services.errors import ConflictError, NotFoundError, ValidationError

_MATERIALIZABLE = (
    RecoveryCandidateStatus.CONFIRMED,
    RecoveryCandidateStatus.NOTICE_DRAFTED,
)
_STATUS_STAMP = {
    RecoverableStatus.NOTIFIED: "notified_at",
    RecoverableStatus.AGREED: "agreed_at",
    RecoverableStatus.BILLED: "billed_at",
    RecoverableStatus.COLLECTED: "settled_at",
}


class CollectionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._recoverables = RecoverableRepository(session)
        self._candidates = RecoveryCandidateRepository(session)
        self._audit = AuditRepository(session)

    # --- reading --------------------------------------------------------

    async def list_for_candidate(
        self, context: AuthenticatedContext, candidate_id: UUID
    ) -> list[Recoverable]:
        return await self._recoverables.for_candidate(context.organization.id, candidate_id)

    async def portfolio(
        self, context: AuthenticatedContext, *, status: RecoverableStatus | None = None
    ) -> list[Recoverable]:
        return await self._recoverables.portfolio(context.organization.id, status=status)

    async def summary(self, context: AuthenticatedContext) -> RecoverableSummary:
        rows = await self._recoverables.portfolio(context.organization.id)
        as_of = dt.datetime.now(tz=dt.UTC).date()
        return summarize_recoverables(
            (
                RecoverableRow(
                    status=r.status,
                    currency=r.currency,
                    expected_amount=r.expected_amount,
                    agreed_amount=r.agreed_amount,
                    collected_amount=r.collected_amount,
                    due_date=r.due_date,
                )
                for r in rows
            ),
            as_of=as_of,
        )

    # --- writing -------------------------------------------------------

    async def materialize(
        self, context: AuthenticatedContext, candidate_id: UUID
    ) -> list[Recoverable]:
        """Create one recoverable per reinsurer on the confirmed recovery's current
        calculation. Idempotent — if they already exist, return them unchanged."""
        org_id = context.organization.id
        candidate = await self._candidates.get(org_id, candidate_id)
        if candidate is None:
            raise NotFoundError("recovery not found")
        if candidate.status not in _MATERIALIZABLE:
            raise ConflictError("confirm the recovery before tracking collection")

        existing = await self._recoverables.for_candidate(org_id, candidate_id)
        if existing:
            return existing

        calc = _current_calculation(candidate)
        if calc is None or not calc.allocations:
            raise ConflictError("the recovery has no calculation with allocations")

        created: list[Recoverable] = []
        for alloc in calc.allocations:
            recoverable = Recoverable(
                organization_id=org_id,
                recovery_candidate_id=candidate.id,
                recovery_calculation_id=calc.id,
                reinsurer_id=alloc.reinsurer_id,
                currency=calc.currency,
                status=RecoverableStatus.PENDING,
                expected_amount=alloc.allocated_recovery,
                collected_amount=Decimal("0.00"),
            )
            self._recoverables.add(recoverable)
            created.append(recoverable)

        self._audit.record(
            AuditRecord(
                organization_id=org_id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="recovery.recoverables_materialized",
                entity_type="recovery_candidate",
                entity_id=candidate.id,
                summary=(
                    f"{context.user.email} started collection tracking — "
                    f"{len(created)} recoverable(s), {calc.layer_recovery} {calc.currency} expected"
                ),
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        return await self._recoverables.for_candidate(org_id, candidate_id)

    async def update(
        self,
        context: AuthenticatedContext,
        recoverable_id: UUID,
        *,
        status: RecoverableStatus | None = None,
        agreed_amount: str | None = None,
        billed_amount: str | None = None,
        collect: str | None = None,
        due_date: dt.date | None = None,
        clear_due_date: bool = False,
        note: str | None = None,
    ) -> Recoverable:
        org_id = context.organization.id
        recoverable = await self._recoverables.get(org_id, recoverable_id)
        if recoverable is None:
            raise NotFoundError("recoverable not found")

        changes: list[str] = []
        now = dt.datetime.now(tz=dt.UTC)

        if agreed_amount is not None:
            recoverable.agreed_amount = _money(agreed_amount, "agreed amount")
            changes.append(f"agreed {recoverable.agreed_amount}")
        if billed_amount is not None:
            recoverable.billed_amount = _money(billed_amount, "billed amount")
            changes.append(f"billed {recoverable.billed_amount}")
        if collect is not None:
            delta = _money(collect, "collected amount")
            if delta <= Decimal("0"):
                raise ValidationError("a collection must be a positive amount")
            recoverable.collected_amount = (recoverable.collected_amount or Decimal("0")) + delta
            changes.append(f"collected +{delta} (total {recoverable.collected_amount})")
        if clear_due_date:
            recoverable.due_date = None
            changes.append("due date cleared")
        elif due_date is not None:
            recoverable.due_date = due_date
            changes.append(f"due {due_date.isoformat()}")
        if note is not None:
            recoverable.note = note.strip() or None
            changes.append("note updated")

        # collected in full → settle, unless already terminal
        basis = recoverable.agreed_amount or recoverable.expected_amount
        if (
            status is None
            and not recoverable.status.is_terminal
            and recoverable.collected_amount >= basis
            and recoverable.collected_amount > Decimal("0")
        ):
            status = RecoverableStatus.COLLECTED

        if status is not None and status is not recoverable.status:
            recoverable.status = status
            stamp = _STATUS_STAMP.get(status)
            if stamp is not None and getattr(recoverable, stamp) is None:
                setattr(recoverable, stamp, now)
            changes.append(f"status → {status.value}")

        if not changes:
            raise ValidationError("nothing to update")

        self._audit.record(
            AuditRecord(
                organization_id=org_id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="recovery.recoverable_updated",
                entity_type="recoverable",
                entity_id=recoverable.id,
                summary=f"{context.user.email} updated a recoverable — {'; '.join(changes)}",
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        refreshed = await self._recoverables.get(org_id, recoverable_id)
        assert refreshed is not None
        return refreshed


def _current_calculation(candidate: RecoveryCandidate) -> RecoveryCalculation | None:
    return next(
        (c for c in candidate.calculations if c.id == candidate.current_calculation_id), None
    )


def _money(raw: str, field: str) -> Decimal:
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"{field} is not a valid amount") from exc
    if value < Decimal("0"):
        raise ValidationError(f"{field} cannot be negative")
    return value.quantize(Decimal("0.01"))
