"""Hours-clause occurrence grouping — *assistive*, never automatic (PRODUCT §7,
2026-09-01 scope expansion).

An hours clause says all losses from one catastrophe within a rolling window of N
hours count as a single occurrence, and the cedent chooses when each window starts.
Cedeon does not decide that — it *proposes* a grouping (greedy: anchor the first
window at the earliest claim, then the next uncovered claim, and so on) for a human
to accept or adjust.

Claims carry a date, not a timestamp, so the window is applied in whole days
(`ceil(hours / 24)`). Pure: standard library only (ADR-0010).
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from decimal import Decimal

# Common hours-clause windows by peril — a hint when the treaty does not state one.
DEFAULT_HOURS_BY_PERIL: dict[str, int] = {
    "hurricane": 168,
    "windstorm": 72,
    "storm": 72,
    "tornado": 72,
    "hail": 72,
    "flood": 168,
    "earthquake": 168,
    "wildfire": 168,
    "riot": 72,
    "freeze": 72,
}

_ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class ClaimForGrouping:
    claim_id: str
    date_of_loss: dt.date
    gross_incurred: Decimal


@dataclass(frozen=True, slots=True)
class ProposedOccurrence:
    index: int  # 1-based
    start_date: dt.date
    end_date: dt.date
    claim_ids: list[str]
    claim_count: int
    gross_incurred: Decimal


@dataclass(frozen=True, slots=True)
class OccurrenceProposal:
    hours: int
    window_days: int
    occurrences: list[ProposedOccurrence]

    @property
    def splits_the_event(self) -> bool:
        return len(self.occurrences) > 1


def window_days(hours: int) -> int:
    return max(1, math.ceil(hours / 24))


def propose_occurrences(claims: list[ClaimForGrouping], hours: int) -> OccurrenceProposal:
    """Greedy anchored grouping. Deterministic; the human confirms or re-anchors."""
    wd = window_days(hours)
    ordered = sorted(claims, key=lambda c: (c.date_of_loss, c.claim_id))
    occurrences: list[ProposedOccurrence] = []
    i = 0
    while i < len(ordered):
        anchor = ordered[i].date_of_loss
        cutoff = anchor + dt.timedelta(days=wd - 1)
        bucket = [c for c in ordered[i:] if c.date_of_loss <= cutoff]
        occurrences.append(
            ProposedOccurrence(
                index=len(occurrences) + 1,
                start_date=anchor,
                end_date=max(c.date_of_loss for c in bucket),
                claim_ids=[c.claim_id for c in bucket],
                claim_count=len(bucket),
                gross_incurred=sum((c.gross_incurred for c in bucket), _ZERO),
            )
        )
        i += len(bucket)
    return OccurrenceProposal(hours=hours, window_days=wd, occurrences=occurrences)
