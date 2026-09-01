"""Reconcile a batch of reinsurer-stated figures against what Cedeon holds.

Read-mostly, org-scoped, no AI. Lines are supplied directly (a file importer for
real bordereau formats is a later addition — PRODUCT §1a). Each line is matched to
one recoverable and run through the pure ``reconcile_statement_line`` check.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_correlation_id
from app.db.models.recoveries import Recoverable, ReinsurerStatement, ReinsurerStatementLine
from app.domain.audit import ActorType, AuditRecord
from app.domain.recoveries.statement_reconciliation import (
    MatchedRecoverable,
    StatementFinding,
    StatementFindingKind,
    StatementLine,
    reconcile_statement_line,
)
from app.repositories.audit import AuditRepository
from app.repositories.recoveries import RecoverableRepository
from app.repositories.reinsurance import ReinsurerRepository
from app.repositories.statements import ReinsurerStatementRepository
from app.services.auth import AuthenticatedContext
from app.services.errors import NotFoundError, ValidationError


@dataclass(slots=True)
class StatementLineInput:
    reinsurer_name: str
    currency: str
    reference: str | None = None
    their_agreed: Decimal | None = None
    their_paid: Decimal | None = None


def _finding_json(f: StatementFinding) -> dict[str, object]:
    return {
        "kind": f.kind.value,
        "text": f.text,
        "ours": str(f.ours) if f.ours is not None else None,
        "theirs": str(f.theirs) if f.theirs is not None else None,
    }


class ReinsurerStatementService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._statements = ReinsurerStatementRepository(session)
        self._recoverables = RecoverableRepository(session)
        self._reinsurers = ReinsurerRepository(session)
        self._audit = AuditRepository(session)

    async def list_statements(self, context: AuthenticatedContext) -> list[ReinsurerStatement]:
        return await self._statements.list_for_org(context.organization.id)

    async def get_statement(
        self, context: AuthenticatedContext, statement_id: UUID
    ) -> ReinsurerStatement:
        statement = await self._statements.get(context.organization.id, statement_id)
        if statement is None:
            raise NotFoundError("reinsurer statement not found")
        return statement

    async def create(
        self,
        context: AuthenticatedContext,
        *,
        label: str,
        currency: str,
        statement_date: dt.date | None,
        lines: list[StatementLineInput],
    ) -> ReinsurerStatement:
        if not label.strip():
            raise ValidationError("a label is required")
        if not lines:
            raise ValidationError("a statement needs at least one line")
        org_id = context.organization.id
        ccy = currency.upper()[:3]

        recoverables = await self._recoverables.portfolio(org_id)
        by_reinsurer: dict[str, list[Recoverable]] = {}
        for r in recoverables:
            by_reinsurer.setdefault(r.reinsurer.name.strip().lower(), []).append(r)

        statement = ReinsurerStatement(
            organization_id=org_id,
            label=label.strip(),
            currency=ccy,
            statement_date=statement_date,
            created_by=context.user.id,
        )
        self._statements.add(statement)

        discrepancies = 0
        for i, line in enumerate(lines, start=1):
            matched = self._match(line, by_reinsurer)
            findings = reconcile_statement_line(
                StatementLine(
                    reinsurer_name=line.reinsurer_name.strip(),
                    currency=(line.currency or ccy).upper()[:3],
                    reference=line.reference,
                    their_agreed=line.their_agreed,
                    their_paid=line.their_paid,
                ),
                None
                if matched is None
                else MatchedRecoverable(
                    reinsurer_name=matched.reinsurer.name,
                    currency=matched.currency,
                    expected=Decimal(matched.expected_amount),
                    our_agreed=(
                        Decimal(matched.agreed_amount)
                        if matched.agreed_amount is not None
                        else None
                    ),
                    our_collected=Decimal(matched.collected_amount),
                ),
            )
            clean = {f.kind for f in findings} == {StatementFindingKind.CLEAN}
            if not clean:
                discrepancies += 1
            statement.lines.append(
                ReinsurerStatementLine(
                    organization_id=org_id,
                    row_number=i,
                    reinsurer_name=line.reinsurer_name.strip(),
                    reference=line.reference,
                    currency=(line.currency or ccy).upper()[:3],
                    their_agreed=line.their_agreed,
                    their_paid=line.their_paid,
                    matched_recoverable_id=matched.id if matched is not None else None,
                    findings=[_finding_json(f) for f in findings],
                    resolved=clean,
                )
            )

        self._audit.record(
            AuditRecord(
                organization_id=org_id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="reinsurer_statement.reconciled",
                entity_type="reinsurer_statement",
                entity_id=statement.id,
                summary=(
                    f"{context.user.email} reconciled '{label.strip()}' — "
                    f"{len(lines)} lines, {discrepancies} discrepanc"
                    f"{'y' if discrepancies == 1 else 'ies'}"
                ),
                payload={"lines": len(lines), "discrepancies": discrepancies},
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        result = await self._statements.get(org_id, statement.id)
        assert result is not None
        return result

    async def resolve_line(
        self, context: AuthenticatedContext, statement_id: UUID, row_number: int
    ) -> ReinsurerStatement:
        statement = await self.get_statement(context, statement_id)
        line = next((x for x in statement.lines if x.row_number == row_number), None)
        if line is None:
            raise NotFoundError(f"statement has no line {row_number}")
        line.resolved = True
        self._audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="reinsurer_statement.line_resolved",
                entity_type="reinsurer_statement",
                entity_id=statement.id,
                summary=f"{context.user.email} resolved line {row_number} of '{statement.label}'",
                payload={"row_number": row_number},
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        result = await self._statements.get(context.organization.id, statement_id)
        assert result is not None
        return result

    @staticmethod
    def _match(
        line: StatementLineInput, by_reinsurer: dict[str, list[Recoverable]]
    ) -> Recoverable | None:
        candidates = by_reinsurer.get(line.reinsurer_name.strip().lower(), [])
        if not candidates:
            return None
        ref = (line.reference or "").strip().lower()
        if ref:
            for r in candidates:
                if (
                    str(r.id).lower().startswith(ref)
                    or str(r.recovery_candidate_id).lower().startswith(ref)
                    or ref in (r.note or "").lower()
                ):
                    return r
            return None
        return candidates[0] if len(candidates) == 1 else None
