"""Repositories for AI runs, citations, term candidates, and reviews."""

from __future__ import annotations

import datetime as dt
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.extraction import (
    AgentRun,
    Citation,
    Review,
    ToolCall,
    TreatyTermCandidate,
)
from app.domain.ai import AgentRunStatus, AgentType

# A RUNNING agent_run older than this is treated as crashed, not in-flight.
_STALE_RUN_AFTER = dt.timedelta(minutes=15)


class AgentRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, run: AgentRun) -> None:
        self._session.add(run)

    async def get(self, organization_id: UUID, run_id: UUID) -> AgentRun | None:
        result = await self._session.execute(
            select(AgentRun).where(
                AgentRun.id == run_id, AgentRun.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def has_active_run(
        self, organization_id: UUID, agent_type: AgentType, subject_id: UUID
    ) -> bool:
        """True if a non-stale RUNNING agent_run already covers this subject —
        used to reject a duplicate enqueue (double click + a job retry racing)."""
        cutoff = dt.datetime.now(dt.UTC) - _STALE_RUN_AFTER
        result = await self._session.execute(
            select(AgentRun.id)
            .where(
                AgentRun.organization_id == organization_id,
                AgentRun.agent_type == agent_type,
                AgentRun.subject_id == subject_id,
                AgentRun.status == AgentRunStatus.RUNNING,
                AgentRun.started_at >= cutoff,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None


class ToolCallRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, call: ToolCall) -> None:
        self._session.add(call)

    async def list_for_run(self, organization_id: UUID, agent_run_id: UUID) -> list[ToolCall]:
        result = await self._session.execute(
            select(ToolCall)
            .where(
                ToolCall.organization_id == organization_id,
                ToolCall.agent_run_id == agent_run_id,
            )
            .order_by(ToolCall.ordinal)
        )
        return list(result.scalars().all())


class CitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, citation: Citation) -> None:
        self._session.add(citation)


class TermCandidateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, candidate: TreatyTermCandidate) -> None:
        self._session.add(candidate)

    async def list_for_version(
        self, organization_id: UUID, treaty_version_id: UUID
    ) -> list[TreatyTermCandidate]:
        result = await self._session.execute(
            select(TreatyTermCandidate)
            .where(
                TreatyTermCandidate.organization_id == organization_id,
                TreatyTermCandidate.treaty_version_id == treaty_version_id,
            )
            .options(selectinload(TreatyTermCandidate.citation))
            .order_by(TreatyTermCandidate.key, TreatyTermCandidate.created_at)
        )
        return list(result.scalars().all())

    async def get(self, organization_id: UUID, candidate_id: UUID) -> TreatyTermCandidate | None:
        result = await self._session.execute(
            select(TreatyTermCandidate)
            .where(
                TreatyTermCandidate.id == candidate_id,
                TreatyTermCandidate.organization_id == organization_id,
            )
            .options(selectinload(TreatyTermCandidate.citation))
        )
        return result.scalar_one_or_none()

    async def delete_for_version(self, treaty_version_id: UUID) -> None:
        candidates = (
            await self._session.execute(
                select(TreatyTermCandidate).where(
                    TreatyTermCandidate.treaty_version_id == treaty_version_id
                )
            )
        ).scalars()
        for candidate in candidates:
            await self._session.delete(candidate)


class ReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, review: Review) -> None:
        self._session.add(review)

    async def list_for_subject(self, organization_id: UUID, subject_id: UUID) -> list[Review]:
        result = await self._session.execute(
            select(Review)
            .where(
                Review.organization_id == organization_id,
                Review.subject_id == subject_id,
            )
            .order_by(Review.created_at.desc())
        )
        return list(result.scalars().all())
