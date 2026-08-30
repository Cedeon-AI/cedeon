"""UUIDv7 identifiers — time-ordered, index-friendly, generated in the application."""

from __future__ import annotations

from uuid import UUID

import uuid_utils


def new_id() -> UUID:
    """A fresh UUIDv7 as a stdlib ``uuid.UUID``."""
    return UUID(str(uuid_utils.uuid7()))


def id_from_str(value: str) -> UUID:
    return UUID(value)
