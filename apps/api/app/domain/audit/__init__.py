"""Audit domain concepts. The audit log is append-only (see docs/DECISIONS.md ADR-0012)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID


class ActorType(StrEnum):
    USER = "user"
    SYSTEM = "system"
    AGENT = "agent"


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """A single thing that happened, ready to be persisted as an ``audit_events`` row."""

    organization_id: UUID | None
    actor_type: ActorType
    action: str
    entity_type: str
    entity_id: UUID | None
    summary: str
    actor_id: UUID | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if self.actor_type is ActorType.USER and self.actor_id is None:
            raise ValueError("a USER audit record must carry an actor_id")
