"""Repository for recovery candidates and their immutable calculations. Org-scoped."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.recoveries import RecoveryAllocation, RecoveryCalculation, RecoveryCandidate
from app.domain.recoveries import RecoveryCandidateStatus

_WITH_CALCULATIONS = (
    selectinload(RecoveryCandidate.calculations)
    .selectinload(RecoveryCalculation.allocations)
    .selectinload(RecoveryAllocation.reinsurer),
)


class RecoveryCandidateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, obj: object) -> None:
        self._session.add(obj)

    async def get(self, organization_id: UUID, candidate_id: UUID) -> RecoveryCandidate | None:
        result = await self._session.execute(
            select(RecoveryCandidate)
            .where(
                RecoveryCandidate.id == candidate_id,
                RecoveryCandidate.organization_id == organization_id,
            )
            .execution_options(populate_existing=True)
            .options(*_WITH_CALCULATIONS)
        )
        return result.scalar_one_or_none()

    async def get_by_inputs(
        self,
        organization_id: UUID,
        *,
        treaty_version_id: UUID,
        treaty_layer_id: UUID,
        loss_event_id: UUID,
    ) -> RecoveryCandidate | None:
        result = await self._session.execute(
            select(RecoveryCandidate)
            .where(
                RecoveryCandidate.organization_id == organization_id,
                RecoveryCandidate.treaty_version_id == treaty_version_id,
                RecoveryCandidate.treaty_layer_id == treaty_layer_id,
                RecoveryCandidate.loss_event_id == loss_event_id,
            )
            .execution_options(populate_existing=True)
            .options(*_WITH_CALCULATIONS)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        organization_id: UUID,
        *,
        status: RecoveryCandidateStatus | None = None,
    ) -> list[RecoveryCandidate]:
        stmt = (
            select(RecoveryCandidate)
            .where(RecoveryCandidate.organization_id == organization_id)
            .options(*_WITH_CALCULATIONS)
            .order_by(RecoveryCandidate.created_at.desc())
        )
        if status is not None:
            stmt = stmt.where(RecoveryCandidate.status == status)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
