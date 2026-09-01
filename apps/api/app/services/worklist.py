"""Builds the recovery desk's worklist by gathering every "needs a human" signal
across the pipeline and handing them to the pure ranker (``app.domain.worklist``).

Read-only, org-scoped, no AI. Some item kinds (notice deadlines, calculation
drift, suggested recoveries) are populated by later phases — their gathering
methods live here and return nothing until their feature lands.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.recoveries import Recoverable, RecoveryCandidate, RecoveryPacket
from app.domain.recoveries import (
    PacketVersionStatus,
    RecoverableStatus,
    RecoveryCandidateStatus,
    days_overdue,
    outstanding,
)
from app.domain.recoveries.chasing import entered_status_on, recommend_chase
from app.domain.recoveries.reconciliation import RecoverableAmounts, reconcile
from app.domain.treaties import TreatyVersionStatus
from app.domain.worklist import WorklistItem, WorklistKind, rank
from app.repositories.losses import LossEventRepository
from app.repositories.recoveries import RecoverableRepository, RecoveryCandidateRepository
from app.repositories.reinsurance import TreatyRepository
from app.services.auth import AuthenticatedContext
from app.services.obligations import ObligationService
from app.services.suggestions import SuggestionService

# A notice deadline this far out (or already past) is worth surfacing.
_NOTICE_HORIZON_DAYS = 45

_OPEN_REVIEW = (RecoveryCandidateStatus.NEEDS_REVIEW, RecoveryCandidateStatus.IN_REVIEW)
_ZERO = Decimal("0")


@dataclass(slots=True)
class WorklistSummary:
    open_count: int
    currency: str
    open_recoverable: Decimal
    overdue_outstanding: Decimal
    largest_open_recovery: Decimal | None


@dataclass(slots=True)
class Worklist:
    items: list[WorklistItem]
    summary: WorklistSummary


def _owed(r: Recoverable) -> Decimal:
    return outstanding(
        status=RecoverableStatus(r.status),
        expected_amount=Decimal(r.expected_amount),
        agreed_amount=Decimal(r.agreed_amount) if r.agreed_amount is not None else None,
        collected_amount=Decimal(r.collected_amount),
    )


class WorklistService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._treaties = TreatyRepository(session)
        self._candidates = RecoveryCandidateRepository(session)
        self._recoverables = RecoverableRepository(session)
        self._events = LossEventRepository(session)
        self._obligations = ObligationService(session)
        self._suggestions = SuggestionService(session)

    async def build(self, context: AuthenticatedContext) -> Worklist:
        org_id = context.organization.id
        today = dt.datetime.now(dt.UTC).date()

        event_names = {e.id: e.name for e in await self._events.list_for_org(org_id)}
        treaty_names = {t.id: t.name for t in await self._treaties.list(org_id)}
        candidates = await self._candidates.list(org_id)
        recoverables = await self._recoverables.portfolio(org_id)

        items: list[WorklistItem] = []
        items += await self._term_validation_items(org_id, today)
        items += await self._contract_change_items(org_id, candidates, event_names, treaty_names)
        items += self._recovery_review_items(candidates, event_names, treaty_names, today)
        items += await self._notice_due_items(context, candidates, event_names, treaty_names)
        items += await self._suggested_recovery_items(context)
        items += await self._packet_approval_items(org_id, candidates, event_names, today)
        items += self._recoverable_overdue_items(recoverables, today)
        items += self._reconciliation_items(recoverables)

        ranked = rank(items)
        return Worklist(items=ranked, summary=self._summary(recoverables, candidates, ranked))

    # --- gatherers ------------------------------------------------

    async def _term_validation_items(self, org_id: UUID, today: dt.date) -> list[WorklistItem]:
        out: list[WorklistItem] = []
        for treaty in await self._treaties.list(org_id):
            version = next((v for v in treaty.versions if v.id == treaty.current_version_id), None)
            if version is None or version.status is not TreatyVersionStatus.NEEDS_VALIDATION:
                continue
            out.append(
                WorklistItem(
                    kind=WorklistKind.TERM_VALIDATION,
                    key=f"term_validation:{treaty.id}",
                    title=f"Proposed terms · {treaty.name}",
                    detail="Extracted from the wording — awaiting your confirmation.",
                    href=f"/treaties/{treaty.id}/validate",
                    age_days=(today - version.created_at.date()).days,
                )
            )
        return out

    async def _contract_change_items(
        self,
        org_id: UUID,
        candidates: list[RecoveryCandidate],
        event_names: dict[UUID, str],
        treaty_names: dict[UUID, str],
    ) -> list[WorklistItem]:
        """A recovery calculated against a treaty version that has since been
        superseded (an endorsement opened a new version) — its basis may have
        moved. Re-open it against the current wording."""
        superseded = {
            v.id
            for treaty in await self._treaties.list(org_id)
            for v in treaty.versions
            if v.status is TreatyVersionStatus.SUPERSEDED
        }
        out: list[WorklistItem] = []
        for c in candidates:
            if (
                c.status is RecoveryCandidateStatus.REJECTED
                or c.treaty_version_id not in superseded
            ):
                continue
            event = event_names.get(c.loss_event_id, "loss event")
            treaty = treaty_names.get(c.treaty_id, "treaty")
            calc = next((x for x in c.calculations if x.id == c.current_calculation_id), None)
            out.append(
                WorklistItem(
                    kind=WorklistKind.CONTRACT_CHANGE,
                    key=f"contract_change:{c.id}",
                    title=f"{event} · {treaty}",
                    detail="The treaty was superseded by a new version — re-open this recovery "
                    "against the current wording.",
                    href=f"/recovery-candidates/{c.id}?section=calculation",
                    amount=Decimal(calc.layer_recovery) if calc is not None else None,
                    currency=c.currency,
                )
            )
        return out

    def _recovery_review_items(
        self,
        candidates: list[RecoveryCandidate],
        event_names: dict[UUID, str],
        treaty_names: dict[UUID, str],
        today: dt.date,
    ) -> list[WorklistItem]:
        out: list[WorklistItem] = []
        for c in candidates:
            calc = next((x for x in c.calculations if x.id == c.current_calculation_id), None)
            event = event_names.get(c.loss_event_id, "loss event")
            treaty = treaty_names.get(c.treaty_id, "treaty")

            if c.drifted_at is not None and calc is not None:
                prior = c.pre_drift_recovery
                if prior is not None:
                    delta = Decimal(calc.layer_recovery) - Decimal(prior)
                    sign = "+" if delta >= 0 else "-"
                    move = f" — {prior} to {calc.layer_recovery} ({sign}{abs(delta)})"
                else:
                    move = ""
                out.append(
                    WorklistItem(
                        kind=WorklistKind.RECOVERY_DRIFT,
                        key=f"recovery_drift:{c.id}",
                        title=f"{event} · {treaty}",
                        detail=f"Claims developed and the recovery moved{move}. Re-review.",
                        href=f"/recovery-candidates/{c.id}?section=calculation",
                        amount=Decimal(calc.layer_recovery),
                        currency=c.currency,
                        age_days=(today - c.drifted_at.date()).days,
                    )
                )
                continue

            if c.status not in _OPEN_REVIEW:
                continue
            out.append(
                WorklistItem(
                    kind=WorklistKind.RECOVERY_REVIEW,
                    key=f"recovery_review:{c.id}",
                    title=f"{event} · {treaty}",
                    detail=(
                        "Currency mismatch — some claims excluded. Review the calculation."
                        if c.currency_mismatch
                        else "Deterministic recovery calculated — review and confirm."
                    ),
                    href=f"/recovery-candidates/{c.id}?section=calculation",
                    amount=Decimal(calc.layer_recovery) if calc is not None else None,
                    currency=c.currency,
                    age_days=(today - c.updated_at.date()).days,
                )
            )
        return out

    async def _notice_due_items(
        self,
        context: AuthenticatedContext,
        candidates: list[RecoveryCandidate],
        event_names: dict[UUID, str],
        treaty_names: dict[UUID, str],
    ) -> list[WorklistItem]:
        out: list[WorklistItem] = []
        for c in candidates:
            if c.status is RecoveryCandidateStatus.REJECTED:
                continue
            ob = await self._obligations.for_candidate(context, c)
            if ob is None or ob.satisfied or ob.deadline is None or ob.days_until is None:
                continue
            if ob.days_until > _NOTICE_HORIZON_DAYS:
                continue
            event = event_names.get(c.loss_event_id, "loss event")
            treaty = treaty_names.get(c.treaty_id, "treaty")
            not_confirmed = c.status not in (
                RecoveryCandidateStatus.CONFIRMED,
                RecoveryCandidateStatus.NOTICE_DRAFTED,
            )
            detail = f"Notice due {ob.deadline.isoformat()}"
            if not_confirmed:
                detail += " — confirm the recovery and file it."
            out.append(
                WorklistItem(
                    kind=WorklistKind.NOTICE_DUE,
                    key=f"notice_due:{c.id}",
                    title=f"{event} · {treaty}",
                    detail=detail,
                    href=f"/recovery-candidates/{c.id}?section=notice",
                    currency=c.currency,
                    due_in_days=ob.days_until,
                )
            )
        return out

    async def _suggested_recovery_items(self, context: AuthenticatedContext) -> list[WorklistItem]:
        out: list[WorklistItem] = []
        for s in await self._suggestions.for_organization(context):
            out.append(
                WorklistItem(
                    kind=WorklistKind.SUGGESTED_RECOVERY,
                    key=f"suggested_recovery:{s.treaty_version_id}:{s.loss_event_id}",
                    title=f"{s.loss_event_name} · {s.treaty_name}",
                    detail=(
                        f"This treaty may respond — {s.suggestion.reason} Open a recovery to check."
                    ),
                    href="/recovery-candidates/new",
                    amount=s.suggestion.indicative_recovery,
                    currency=s.suggestion.currency,
                )
            )
        return out

    async def _packet_approval_items(
        self,
        org_id: UUID,
        candidates: list[RecoveryCandidate],
        event_names: dict[UUID, str],
        today: dt.date,
    ) -> list[WorklistItem]:
        by_candidate = {c.id: c for c in candidates}
        stmt = (
            select(RecoveryPacket)
            .where(RecoveryPacket.organization_id == org_id)
            .options(selectinload(RecoveryPacket.versions))
        )
        out: list[WorklistItem] = []
        for packet in (await self._session.execute(stmt)).scalars().all():
            current = next((v for v in packet.versions if v.id == packet.current_version_id), None)
            if current is None or current.status is not PacketVersionStatus.DRAFT:
                continue
            candidate = by_candidate.get(packet.recovery_candidate_id)
            if candidate is None or candidate.status is RecoveryCandidateStatus.REJECTED:
                continue
            calc = next(
                (x for x in candidate.calculations if x.id == candidate.current_calculation_id),
                None,
            )
            event = event_names.get(candidate.loss_event_id, "recovery")
            out.append(
                WorklistItem(
                    kind=WorklistKind.PACKET_APPROVAL,
                    key=f"packet_approval:{packet.id}",
                    title=f"Packet v{current.version_no} · {event}",
                    detail="Generated and awaiting approval.",
                    href=f"/recovery-candidates/{packet.recovery_candidate_id}?section=packet",
                    amount=Decimal(calc.layer_recovery) if calc is not None else None,
                    currency=candidate.currency,
                    age_days=(today - current.created_at.date()).days,
                )
            )
        return out

    def _recoverable_overdue_items(
        self, recoverables: list[Recoverable], today: dt.date
    ) -> list[WorklistItem]:
        out: list[WorklistItem] = []
        for r in recoverables:
            status = RecoverableStatus(r.status)
            if not status.is_open or r.due_date is None:
                continue
            overdue = days_overdue(r.due_date, today)
            owed = _owed(r)
            if overdue <= 0 or owed <= _ZERO:
                continue
            entered = entered_status_on(
                status,
                created_at=r.created_at,
                notified_at=r.notified_at,
                agreed_at=r.agreed_at,
                billed_at=r.billed_at,
                settled_at=r.settled_at,
                updated_at=r.updated_at,
            )
            hint = recommend_chase(
                status=status,
                days_in_status=max((today - entered.date()).days, 0),
                days_overdue=overdue,
            )
            out.append(
                WorklistItem(
                    kind=WorklistKind.RECOVERABLE_OVERDUE,
                    key=f"recoverable_overdue:{r.id}",
                    title=f"{r.reinsurer.name} · {status.value}",
                    detail=hint.text,
                    href=(f"/recovery-candidates/{r.recovery_candidate_id}?section=collection"),
                    amount=owed,
                    currency=r.currency,
                    due_in_days=-overdue,
                    age_days=overdue,
                )
            )
        return out

    def _reconciliation_items(self, recoverables: list[Recoverable]) -> list[WorklistItem]:
        out: list[WorklistItem] = []
        for r in recoverables:
            findings = reconcile(
                RecoverableAmounts(
                    status=RecoverableStatus(r.status),
                    currency=r.currency,
                    expected=Decimal(r.expected_amount),
                    agreed=Decimal(r.agreed_amount) if r.agreed_amount is not None else None,
                    billed=Decimal(r.billed_amount) if r.billed_amount is not None else None,
                    collected=Decimal(r.collected_amount),
                )
            )
            if not findings:
                continue
            top = findings[0]
            extra = f" (+{len(findings) - 1} more)" if len(findings) > 1 else ""
            out.append(
                WorklistItem(
                    kind=WorklistKind.RECONCILIATION_MISMATCH,
                    key=f"reconciliation_mismatch:{r.id}",
                    title=f"{r.reinsurer.name} · {RecoverableStatus(r.status).value}",
                    detail=top.text + extra,
                    href=f"/recovery-candidates/{r.recovery_candidate_id}?section=collection",
                    amount=top.gap,
                    currency=r.currency,
                )
            )
        return out

    # --- summary -------------------------------------------------

    def _summary(
        self,
        recoverables: list[Recoverable],
        candidates: list[RecoveryCandidate],
        ranked: list[WorklistItem],
    ) -> WorklistSummary:
        currency = recoverables[0].currency if recoverables else "USD"
        today = dt.datetime.now(dt.UTC).date()

        open_recoverable = _ZERO
        overdue_outstanding = _ZERO
        for r in recoverables:
            if r.currency != currency:
                continue
            owed = _owed(r)
            open_recoverable += owed
            if r.due_date is not None and days_overdue(r.due_date, today) > 0:
                overdue_outstanding += owed

        amounts = [
            Decimal(calc.layer_recovery)
            for c in candidates
            if c.status is not RecoveryCandidateStatus.REJECTED
            for calc in [
                next((x for x in c.calculations if x.id == c.current_calculation_id), None)
            ]
            if calc is not None
        ]
        return WorklistSummary(
            open_count=len(ranked),
            currency=currency,
            open_recoverable=open_recoverable,
            overdue_outstanding=overdue_outstanding,
            largest_open_recovery=max(amounts) if amounts else None,
        )
