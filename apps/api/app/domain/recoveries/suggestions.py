"""Should Cedeon suggest opening a recovery for this (treaty, event) pair?

A deterministic screen — currency, the treaty window, and gross above the
attachment. It proposes; a human promotes it to a real ``RecoveryCandidate``.
No AI, no I/O (ADR-0010).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

_ZERO = Decimal("0")


class SuggestionMiss(StrEnum):
    """Why a (treaty, event) pair is *not* suggested — useful for explaining
    a near-miss to the analyst."""

    CURRENCY = "currency_mismatch"
    WINDOW = "outside_treaty_window"
    BELOW_ATTACHMENT = "gross_below_attachment"
    ALREADY_OPEN = "recovery_already_exists"


@dataclass(frozen=True, slots=True)
class LayerWindow:
    currency: str
    attachment: Decimal
    limit: Decimal
    effective_date: dt.date | None
    expiration_date: dt.date | None


@dataclass(frozen=True, slots=True)
class EventFacts:
    currency: str | None
    date_from: dt.date | None
    date_to: dt.date | None
    gross_in_currency: Decimal  # Σ gross_incurred of the event's losses in the layer currency


@dataclass(frozen=True, slots=True)
class Suggestion:
    gross: Decimal
    attachment: Decimal
    limit: Decimal
    currency: str
    indicative_recovery: Decimal
    reason: str


def _within_window(event: EventFacts, layer: LayerWindow) -> bool:
    first = event.date_from or event.date_to
    if first is None:
        return True  # undated event — don't exclude on window
    last = event.date_to or event.date_from
    before_inception = layer.effective_date is not None and first < layer.effective_date
    after_expiry = (
        layer.expiration_date is not None and last is not None and last > layer.expiration_date
    )
    return not (before_inception or after_expiry)


def evaluate_suggestion(
    event: EventFacts, layer: LayerWindow, *, has_open_candidate: bool
) -> Suggestion | SuggestionMiss:
    """Screen one (event, layer) pair. Returns a ``Suggestion`` when Cedeon should
    propose opening a recovery, otherwise the reason it didn't."""
    if has_open_candidate:
        return SuggestionMiss.ALREADY_OPEN
    if event.gross_in_currency <= _ZERO:
        return SuggestionMiss.CURRENCY
    if not _within_window(event, layer):
        return SuggestionMiss.WINDOW
    if event.gross_in_currency <= layer.attachment:
        return SuggestionMiss.BELOW_ATTACHMENT

    above = event.gross_in_currency - layer.attachment
    indicative = min(above, layer.limit)
    return Suggestion(
        gross=event.gross_in_currency,
        attachment=layer.attachment,
        limit=layer.limit,
        currency=layer.currency,
        indicative_recovery=indicative,
        reason=(
            f"{event.gross_in_currency} gross is above the {layer.attachment} attachment "
            f"— an indicative {indicative} recovery on this layer."
        ),
    )
