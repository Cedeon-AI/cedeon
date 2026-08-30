"""Recovery-candidate lifecycle + the deterministic hash of a calculation's
inputs. Pure: standard library only, no AI, no I/O (ADR-0010)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum


class RecoveryCandidateStatus(StrEnum):
    """docs/PRODUCT.md — Recovery Candidate lifecycle.

    NEEDS_REVIEW ─▶ IN_REVIEW ─▶ CONFIRMED ─▶ NOTICE_DRAFTED
                          └──▶ REJECTED
    (inputs change → recalculation → new immutable RecoveryCalculation;
     a CONFIRMED candidate reverts to NEEDS_REVIEW)
    """

    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    IN_REVIEW = "in_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    NOTICE_DRAFTED = "notice_drafted"

    @property
    def is_open(self) -> bool:
        return self in (
            RecoveryCandidateStatus.DRAFT,
            RecoveryCandidateStatus.NEEDS_REVIEW,
            RecoveryCandidateStatus.IN_REVIEW,
        )


def recovery_input_hash(
    *,
    engine_version: str,
    treaty_version_id: str,
    treaty_layer_id: str,
    loss_event_id: str,
    currency: str,
    gross_loss: Decimal,
    attachment: Decimal,
    limit: Decimal,
    participations: Sequence[tuple[str, Decimal]],
) -> str:
    """A stable SHA-256 over every input to ``calculate_recovery``. Two calls with
    the same inputs produce the same hash; any change (a new loss committed to the
    event, a re-validated treaty, a shifted share) produces a different one."""
    payload = {
        "engine_version": engine_version,
        "treaty_version_id": treaty_version_id,
        "treaty_layer_id": treaty_layer_id,
        "loss_event_id": loss_event_id,
        "currency": currency,
        "gross_loss": _canon(gross_loss),
        "attachment": _canon(attachment),
        "limit": _canon(limit),
        "participations": sorted([key, _canon(share)] for key, share in participations),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _canon(amount: Decimal) -> str:
    """Normalize a Decimal so ``50000000`` and ``50000000.00`` hash identically."""
    normalized = amount.normalize()
    # Decimal.normalize() gives e.g. 5E+7 — expand it back to plain notation.
    return f"{normalized:f}"
