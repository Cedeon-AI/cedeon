"""The audit_events table must reject UPDATE and DELETE (ADR-0012)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.models.audit import AuditEvent
from app.domain.audit import ActorType

pytestmark = pytest.mark.db


async def _insert_one(session) -> uuid.UUID:
    event = AuditEvent(
        organization_id=None,
        actor_type=ActorType.SYSTEM,
        action="test.event",
        entity_type="test",
        entity_id=None,
        summary="a test event",
    )
    session.add(event)
    await session.commit()
    return event.id


async def test_update_is_rejected(session) -> None:
    event_id = await _insert_one(session)
    with pytest.raises(DBAPIError):
        await session.execute(
            text("UPDATE audit_events SET summary = 'tampered' WHERE id = :id"),
            {"id": event_id},
        )
    await session.rollback()


async def test_delete_is_rejected(session) -> None:
    event_id = await _insert_one(session)
    with pytest.raises(DBAPIError):
        await session.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": event_id})
    await session.rollback()


async def test_insert_is_allowed(session) -> None:
    event_id = await _insert_one(session)
    row = (
        await session.execute(
            text("SELECT summary FROM audit_events WHERE id = :id"), {"id": event_id}
        )
    ).one()
    assert row.summary == "a test event"
