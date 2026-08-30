"""Append-only audit log writer."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit import AuditEvent
from app.domain.audit import AuditRecord


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def record(self, entry: AuditRecord) -> AuditEvent:
        event = AuditEvent(
            organization_id=entry.organization_id,
            actor_type=entry.actor_type,
            actor_id=entry.actor_id,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            summary=entry.summary,
            payload=entry.payload,
            correlation_id=entry.correlation_id,
        )
        self._session.add(event)
        return event

    async def list_for_entity(
        self, organization_id: UUID, entity_type: str, entity_id: UUID
    ) -> list[AuditEvent]:
        result = await self._session.execute(
            select(AuditEvent)
            .where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.entity_type == entity_type,
                AuditEvent.entity_id == entity_id,
            )
            .order_by(AuditEvent.occurred_at.desc())
        )
        return list(result.scalars().all())
