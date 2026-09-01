"""Team-invitation domain concepts.

An invitation is a signed, expiring, single-use offer to join one organization at
one role, addressed to one email. It is accepted only by authenticating as that
email (docs/DECISIONS.md ADR-0026).
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"


def is_live(status: InvitationStatus, expires_at: dt.datetime, *, now: dt.datetime) -> bool:
    """A pending invitation that has not expired — the only state that can be accepted."""
    return status is InvitationStatus.PENDING and expires_at > now
