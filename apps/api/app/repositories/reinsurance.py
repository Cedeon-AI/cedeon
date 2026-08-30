"""Repositories for reinsurance structure. Every query is organization-scoped."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.reinsurance import (
    Cedent,
    ReinsuranceProgram,
    Reinsurer,
    Treaty,
    TreatyParticipation,
    TreatyVersion,
)


class CedentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, organization_id: UUID, cedent_id: UUID) -> Cedent | None:
        result = await self._session.execute(
            select(Cedent).where(Cedent.id == cedent_id, Cedent.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, organization_id: UUID, name: str) -> Cedent | None:
        result = await self._session.execute(
            select(Cedent).where(Cedent.organization_id == organization_id, Cedent.name == name)
        )
        return result.scalar_one_or_none()

    async def list(self, organization_id: UUID) -> list[Cedent]:
        result = await self._session.execute(
            select(Cedent).where(Cedent.organization_id == organization_id).order_by(Cedent.name)
        )
        return list(result.scalars().all())

    def add(self, cedent: Cedent) -> None:
        self._session.add(cedent)


class ReinsurerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, organization_id: UUID, reinsurer_id: UUID) -> Reinsurer | None:
        result = await self._session.execute(
            select(Reinsurer).where(
                Reinsurer.id == reinsurer_id,
                Reinsurer.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, organization_id: UUID, name: str) -> Reinsurer | None:
        result = await self._session.execute(
            select(Reinsurer).where(
                Reinsurer.organization_id == organization_id, Reinsurer.name == name
            )
        )
        return result.scalar_one_or_none()

    async def list(self, organization_id: UUID) -> list[Reinsurer]:
        result = await self._session.execute(
            select(Reinsurer)
            .where(Reinsurer.organization_id == organization_id)
            .order_by(Reinsurer.name)
        )
        return list(result.scalars().all())

    def add(self, reinsurer: Reinsurer) -> None:
        self._session.add(reinsurer)


class ProgramRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, organization_id: UUID, program_id: UUID) -> ReinsuranceProgram | None:
        result = await self._session.execute(
            select(ReinsuranceProgram)
            .where(
                ReinsuranceProgram.id == program_id,
                ReinsuranceProgram.organization_id == organization_id,
            )
            .options(selectinload(ReinsuranceProgram.cedent))
        )
        return result.scalar_one_or_none()

    async def list(self, organization_id: UUID) -> list[ReinsuranceProgram]:
        result = await self._session.execute(
            select(ReinsuranceProgram)
            .where(ReinsuranceProgram.organization_id == organization_id)
            .options(selectinload(ReinsuranceProgram.cedent))
            .order_by(ReinsuranceProgram.treaty_year.desc(), ReinsuranceProgram.name)
        )
        return list(result.scalars().all())

    async def treaty_counts(self, organization_id: UUID) -> dict[UUID, int]:
        result = await self._session.execute(
            select(Treaty.program_id, func.count(Treaty.id))
            .where(Treaty.organization_id == organization_id)
            .group_by(Treaty.program_id)
        )
        return {row[0]: row[1] for row in result.all()}

    def add(self, program: ReinsuranceProgram) -> None:
        self._session.add(program)


class TreatyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, organization_id: UUID, treaty_id: UUID) -> Treaty | None:
        result = await self._session.execute(
            select(Treaty)
            .where(Treaty.id == treaty_id, Treaty.organization_id == organization_id)
            .options(
                selectinload(Treaty.program).selectinload(ReinsuranceProgram.cedent),
                selectinload(Treaty.versions),
            )
        )
        return result.scalar_one_or_none()

    async def list(self, organization_id: UUID) -> list[Treaty]:
        result = await self._session.execute(
            select(Treaty)
            .where(Treaty.organization_id == organization_id)
            .options(
                selectinload(Treaty.program).selectinload(ReinsuranceProgram.cedent),
                selectinload(Treaty.versions),
            )
            .order_by(Treaty.created_at.desc())
        )
        return list(result.scalars().all())

    def add(self, treaty: Treaty) -> None:
        self._session.add(treaty)


class TreatyVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, organization_id: UUID, version_id: UUID) -> TreatyVersion | None:
        result = await self._session.execute(
            select(TreatyVersion)
            .where(
                TreatyVersion.id == version_id,
                TreatyVersion.organization_id == organization_id,
            )
            .execution_options(populate_existing=True)
            .options(
                selectinload(TreatyVersion.layers),
                selectinload(TreatyVersion.participations).selectinload(
                    TreatyParticipation.reinsurer
                ),
                selectinload(TreatyVersion.terms),
            )
        )
        return result.scalar_one_or_none()

    def add(self, version: TreatyVersion) -> None:
        self._session.add(version)
