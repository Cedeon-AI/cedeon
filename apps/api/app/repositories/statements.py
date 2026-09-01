"""Reinsurer-statement persistence — org-scoped."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.recoveries import ReinsurerStatement, ReinsurerStatementLine


class ReinsurerStatementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, obj: object) -> None:
        self._session.add(obj)

    async def get(
        self, organization_id: UUID, statement_id: UUID
    ) -> ReinsurerStatement | None:
        result = await self._session.execute(
            select(ReinsurerStatement)
            .where(
                ReinsurerStatement.id == statement_id,
                ReinsurerStatement.organization_id == organization_id,
            )
            .options(selectinload(ReinsurerStatement.lines))
        )
        return result.scalar_one_or_none()

    async def list_for_org(self, organization_id: UUID) -> list[ReinsurerStatement]:
        result = await self._session.execute(
            select(ReinsurerStatement)
            .where(ReinsurerStatement.organization_id == organization_id)
            .options(selectinload(ReinsurerStatement.lines))
            .order_by(ReinsurerStatement.created_at.desc())
        )
        return list(result.scalars().all())

    async def unresolved_discrepancy_lines(
        self, organization_id: UUID
    ) -> list[ReinsurerStatementLine]:
        result = await self._session.execute(
            select(ReinsurerStatementLine).where(
                ReinsurerStatementLine.organization_id == organization_id,
                ReinsurerStatementLine.resolved.is_(False),
            )
        )
        return list(result.scalars().all())
