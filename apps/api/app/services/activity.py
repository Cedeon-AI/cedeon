"""The activity / observability surface: what the AI did, what happened, and what
it cost. Read-only; every method is org-scoped (Phase 10)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit import AuditEvent
from app.db.models.extraction import AgentRun, ToolCall
from app.domain.ai import AgentRunStatus, AgentType
from app.repositories.activity import ActivityRepository, SpendByDay, SpendByType
from app.repositories.extraction import ToolCallRepository
from app.services.auth import AuthenticatedContext
from app.services.errors import NotFoundError


@dataclass(slots=True)
class SpendTotals:
    runs: int
    succeeded: int
    failed: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


@dataclass(slots=True)
class AiSpend:
    since: dt.datetime
    totals: SpendTotals
    by_type: list[SpendByType]
    by_day: list[SpendByDay]


class ActivityService:
    def __init__(self, session: AsyncSession) -> None:
        self._activity = ActivityRepository(session)
        self._tool_calls = ToolCallRepository(session)

    async def agent_runs(
        self,
        context: AuthenticatedContext,
        *,
        agent_type: AgentType | None = None,
        status: AgentRunStatus | None = None,
        limit: int = 50,
        before: dt.datetime | None = None,
    ) -> list[AgentRun]:
        return await self._activity.list_agent_runs(
            context.organization.id,
            agent_type=agent_type,
            status=status,
            limit=limit,
            before=before,
        )

    async def agent_run_detail(
        self, context: AuthenticatedContext, run_id: UUID
    ) -> tuple[AgentRun, list[ToolCall]]:
        run = await self._activity.get_agent_run(context.organization.id, run_id)
        if run is None:
            raise NotFoundError("agent run not found")
        tools = await self._tool_calls.list_for_run(context.organization.id, run_id)
        return run, tools

    async def audit_feed(
        self,
        context: AuthenticatedContext,
        *,
        action: str | None = None,
        actor_type: str | None = None,
        entity_type: str | None = None,
        limit: int = 50,
        before: dt.datetime | None = None,
    ) -> list[AuditEvent]:
        return await self._activity.audit_feed(
            context.organization.id,
            action=action,
            actor_type=actor_type,
            entity_type=entity_type,
            limit=limit,
            before=before,
        )

    async def ai_spend(self, context: AuthenticatedContext, *, days: int = 30) -> AiSpend:
        since = dt.datetime.now(dt.UTC) - dt.timedelta(days=max(1, min(days, 365)))
        by_type = await self._activity.spend_by_type(context.organization.id, since=since)
        by_day = await self._activity.spend_by_day(context.organization.id, since=since)
        totals = SpendTotals(
            runs=sum(t.runs for t in by_type),
            succeeded=sum(t.succeeded for t in by_type),
            failed=sum(t.failed for t in by_type),
            input_tokens=sum(t.input_tokens for t in by_type),
            output_tokens=sum(t.output_tokens for t in by_type),
            cost_usd=sum((t.cost_usd for t in by_type), Decimal("0")),
        )
        return AiSpend(since=since, totals=totals, by_type=by_type, by_day=by_day)
