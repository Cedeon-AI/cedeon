"""Per-organization AI spend budgets (docs/DECISIONS.md ADR-0028).

Every organization has an optional calendar-month USD cap on AI spend
(``organizations.ai_budget_usd``; NULL = unlimited). ``enforce`` is called before
any model work is enqueued or run; ``notify_if_crossed`` emails the operator once
per month when an org nears or passes the cap. Spend is the sum of
``agent_runs.cost_usd`` for the current month — the same figure the
``/activity/ai-spend`` screen shows.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_correlation_id, get_logger
from app.db.models.extraction import AgentRun
from app.db.models.identity import Organization
from app.domain.audit import ActorType, AuditRecord
from app.notifications import EmailMessage, EmailSender
from app.repositories.audit import AuditRepository
from app.services.errors import ConflictError, NotFoundError, UsageLimitError

log = get_logger(__name__)

_WARN_FRACTION = Decimal("0.8")


def _month_start(now: dt.datetime) -> dt.datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@dataclass(frozen=True, slots=True)
class BudgetStatus:
    budget_usd: Decimal | None  # None → unlimited
    spent_usd: Decimal  # current calendar month
    period_start: dt.datetime

    @property
    def unlimited(self) -> bool:
        return self.budget_usd is None

    @property
    def remaining_usd(self) -> Decimal | None:
        return None if self.budget_usd is None else self.budget_usd - self.spent_usd

    @property
    def exhausted(self) -> bool:
        return self.budget_usd is not None and self.spent_usd >= self.budget_usd


class AiBudgetService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._audit = AuditRepository(session)

    async def status(self, organization_id: UUID) -> BudgetStatus:
        org = await self._session.get(Organization, organization_id)
        if org is None:
            raise NotFoundError("organization not found")
        return await self._status_for(org)

    async def enforce(self, organization_id: UUID) -> None:
        """Raise before any AI work is enqueued or run for this organization."""
        if not self._settings.ai_enabled:
            raise ConflictError("AI features are disabled in this environment")
        org = await self._session.get(Organization, organization_id)
        if org is None:
            raise NotFoundError("organization not found")
        status = await self._status_for(org)
        if status.exhausted:
            raise UsageLimitError(
                "this workspace has reached its AI usage limit for the month — "
                "contact Cedeon to raise it",
                detail={
                    "budget_usd": str(status.budget_usd),
                    "spent_usd": str(status.spent_usd),
                    "period_start": status.period_start.isoformat(),
                },
            )

    async def notify_if_crossed(self, organization_id: UUID, *, email: EmailSender) -> None:
        """Best-effort: after a run records its cost, alert ops once per month if the
        org has reached 80% of (or passed) its budget. Never raises — a notification
        failure must not fail the job that called it."""
        try:
            org = await self._session.get(Organization, organization_id)
            if org is None or org.ai_budget_usd is None:
                return
            status = await self._status_for(org)
            if status.spent_usd < org.ai_budget_usd * _WARN_FRACTION:
                return
            if (
                org.ai_budget_notified_at is not None
                and org.ai_budget_notified_at >= status.period_start
            ):
                return  # already alerted this month

            org.ai_budget_notified_at = dt.datetime.now(dt.UTC)
            pct = int((status.spent_usd / org.ai_budget_usd) * 100)
            self._audit.record(
                AuditRecord(
                    organization_id=org.id,
                    actor_type=ActorType.SYSTEM,
                    action="organization.ai_budget_alert",
                    entity_type="organization",
                    entity_id=org.id,
                    summary=f"{org.name} at {pct}% of its ${org.ai_budget_usd} monthly AI budget",
                    payload={
                        "spent_usd": str(status.spent_usd),
                        "budget_usd": str(org.ai_budget_usd),
                    },
                    correlation_id=get_correlation_id(),
                )
            )
            if self._settings.ops_email:
                await email.send(
                    EmailMessage(
                        to=self._settings.ops_email,
                        subject=f"[Cedeon] {org.name} at {pct}% of its monthly AI budget",
                        text_body=(
                            f"{org.name} ({org.slug}) has spent ${status.spent_usd} of its "
                            f"${org.ai_budget_usd} AI budget this month "
                            f"(since {status.period_start.date()}).\n\n"
                            f"Raise it with:  just set-org-budget {org.slug} <usd>"
                        ),
                        from_addr=self._settings.email_from,
                    )
                )
        except Exception:  # a failed notification must never break the job that called it
            log.warning("ai_budget.notify_failed", organization_id=str(organization_id))

    async def _status_for(self, org: Organization) -> BudgetStatus:
        start = _month_start(dt.datetime.now(dt.UTC))
        spent = await self._session.scalar(
            select(func.coalesce(func.sum(AgentRun.cost_usd), 0)).where(
                AgentRun.organization_id == org.id,
                AgentRun.created_at >= start,
            )
        )
        return BudgetStatus(
            budget_usd=org.ai_budget_usd,
            spent_usd=Decimal(spent or 0),
            period_start=start,
        )
