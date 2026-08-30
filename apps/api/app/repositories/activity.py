"""Read models for the activity / observability surface: AI runs, the audit feed,
and AI spend. Every query is organization-scoped (Phase 10)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit import AuditEvent
from app.db.models.extraction import AgentRun
from app.domain.ai import AgentRunStatus, AgentType


@dataclass(slots=True)
class SpendByType:
    agent_type: str
    runs: int
    succeeded: int
    failed: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    avg_latency_ms: int | None


@dataclass(slots=True)
class SpendByDay:
    day: str
    runs: int
    cost_usd: Decimal


class ActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_agent_run(self, organization_id: UUID, run_id: UUID) -> AgentRun | None:
        result = await self._session.execute(
            select(AgentRun).where(
                AgentRun.id == run_id, AgentRun.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_agent_runs(
        self,
        organization_id: UUID,
        *,
        agent_type: AgentType | None = None,
        status: AgentRunStatus | None = None,
        limit: int = 50,
        before: dt.datetime | None = None,
    ) -> list[AgentRun]:
        stmt = (
            select(AgentRun)
            .where(AgentRun.organization_id == organization_id)
            .order_by(AgentRun.created_at.desc())
            .limit(max(1, min(limit, 200)))
        )
        if agent_type is not None:
            stmt = stmt.where(AgentRun.agent_type == agent_type)
        if status is not None:
            stmt = stmt.where(AgentRun.status == status)
        if before is not None:
            stmt = stmt.where(AgentRun.created_at < before)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def audit_feed(
        self,
        organization_id: UUID,
        *,
        action: str | None = None,
        actor_type: str | None = None,
        entity_type: str | None = None,
        limit: int = 50,
        before: dt.datetime | None = None,
    ) -> list[AuditEvent]:
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.organization_id == organization_id)
            .order_by(AuditEvent.occurred_at.desc())
            .limit(max(1, min(limit, 200)))
        )
        if action:
            stmt = stmt.where(AuditEvent.action == action)
        if actor_type:
            stmt = stmt.where(AuditEvent.actor_type == actor_type)
        if entity_type:
            stmt = stmt.where(AuditEvent.entity_type == entity_type)
        if before is not None:
            stmt = stmt.where(AuditEvent.occurred_at < before)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def spend_by_type(
        self, organization_id: UUID, *, since: dt.datetime
    ) -> list[SpendByType]:
        succeeded = func.count(AgentRun.id).filter(AgentRun.status == AgentRunStatus.SUCCEEDED)
        failed = func.count(AgentRun.id).filter(AgentRun.status == AgentRunStatus.FAILED)
        result = await self._session.execute(
            select(
                AgentRun.agent_type,
                func.count(AgentRun.id),
                succeeded,
                failed,
                func.coalesce(func.sum(AgentRun.input_tokens), 0),
                func.coalesce(func.sum(AgentRun.output_tokens), 0),
                func.coalesce(func.sum(AgentRun.cost_usd), 0),
                func.avg(AgentRun.latency_ms),
            )
            .where(
                AgentRun.organization_id == organization_id,
                AgentRun.created_at >= since,
            )
            .group_by(AgentRun.agent_type)
            .order_by(AgentRun.agent_type)
        )
        return [
            SpendByType(
                agent_type=row[0].value if hasattr(row[0], "value") else str(row[0]),
                runs=row[1],
                succeeded=row[2],
                failed=row[3],
                input_tokens=int(row[4]),
                output_tokens=int(row[5]),
                cost_usd=Decimal(row[6]),
                avg_latency_ms=int(row[7]) if row[7] is not None else None,
            )
            for row in result.all()
        ]

    async def spend_by_day(self, organization_id: UUID, *, since: dt.datetime) -> list[SpendByDay]:
        day = func.date_trunc("day", AgentRun.created_at)
        result = await self._session.execute(
            select(
                day,
                func.count(AgentRun.id),
                func.coalesce(func.sum(AgentRun.cost_usd), 0),
            )
            .where(
                AgentRun.organization_id == organization_id,
                AgentRun.created_at >= since,
            )
            .group_by(day)
            .order_by(day)
        )
        return [
            SpendByDay(day=row[0].date().isoformat(), runs=row[1], cost_usd=Decimal(row[2]))
            for row in result.all()
        ]
