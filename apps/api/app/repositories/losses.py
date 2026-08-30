"""Repositories for loss imports, events, and underlying losses. Org-scoped."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.losses import (
    LossEvent,
    LossImport,
    LossImportRow,
    UnderlyingLoss,
)


class LossImportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, obj: object) -> None:
        self._session.add(obj)

    async def get(self, organization_id: UUID, import_id: UUID) -> LossImport | None:
        result = await self._session.execute(
            select(LossImport).where(
                LossImport.id == import_id,
                LossImport.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_sha256(self, organization_id: UUID, sha256: str) -> LossImport | None:
        result = await self._session.execute(
            select(LossImport).where(
                LossImport.organization_id == organization_id,
                LossImport.sha256 == sha256,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_org(self, organization_id: UUID) -> list[LossImport]:
        result = await self._session.execute(
            select(LossImport)
            .where(LossImport.organization_id == organization_id)
            .order_by(LossImport.created_at.desc())
        )
        return list(result.scalars().all())

    async def rows(self, import_id: UUID) -> list[LossImportRow]:
        result = await self._session.execute(
            select(LossImportRow)
            .where(LossImportRow.loss_import_id == import_id)
            .order_by(LossImportRow.row_number)
        )
        return list(result.scalars().all())


class LossEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, event: LossEvent) -> None:
        self._session.add(event)

    async def get(self, organization_id: UUID, event_id: UUID) -> LossEvent | None:
        result = await self._session.execute(
            select(LossEvent).where(
                LossEvent.id == event_id, LossEvent.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_identifier(self, organization_id: UUID, identifier: str) -> LossEvent | None:
        result = await self._session.execute(
            select(LossEvent).where(
                LossEvent.organization_id == organization_id,
                LossEvent.event_identifier == identifier,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_org(self, organization_id: UUID) -> list[LossEvent]:
        result = await self._session.execute(
            select(LossEvent)
            .where(LossEvent.organization_id == organization_id)
            .order_by(LossEvent.date_of_loss_from.desc().nullslast(), LossEvent.name)
        )
        return list(result.scalars().all())

    async def aggregates(self, organization_id: UUID) -> dict[UUID, dict[str, tuple[int, Decimal]]]:
        """event_id -> {currency: (claim_count, incurred_sum)}."""
        result = await self._session.execute(
            select(
                UnderlyingLoss.loss_event_id,
                UnderlyingLoss.currency,
                func.count(UnderlyingLoss.id),
                func.coalesce(func.sum(UnderlyingLoss.gross_incurred), 0),
            )
            .where(
                UnderlyingLoss.organization_id == organization_id,
                UnderlyingLoss.loss_event_id.is_not(None),
            )
            .group_by(UnderlyingLoss.loss_event_id, UnderlyingLoss.currency)
        )
        out: dict[UUID, dict[str, tuple[int, Decimal]]] = {}
        for event_id, currency, count, total in result.all():
            out.setdefault(event_id, {})[currency] = (count, Decimal(total))
        return out


class UnderlyingLossRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, loss: UnderlyingLoss) -> None:
        self._session.add(loss)

    async def for_event(self, organization_id: UUID, event_id: UUID) -> list[UnderlyingLoss]:
        result = await self._session.execute(
            select(UnderlyingLoss)
            .where(
                UnderlyingLoss.organization_id == organization_id,
                UnderlyingLoss.loss_event_id == event_id,
            )
            .order_by(UnderlyingLoss.date_of_loss, UnderlyingLoss.claim_id)
        )
        return list(result.scalars().all())
