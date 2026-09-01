"""The hours-clause grouper proposes; it never decides."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from app.domain.losses.occurrences import (
    ClaimForGrouping,
    propose_occurrences,
    window_days,
)

D = Decimal


def _c(day: int, amount: str, cid: str | None = None) -> ClaimForGrouping:
    return ClaimForGrouping(
        claim_id=cid or f"C{day}",
        date_of_loss=dt.date(2027, 9, day),
        gross_incurred=D(amount),
    )


def test_window_days_rounds_up() -> None:
    assert window_days(168) == 7
    assert window_days(72) == 3
    assert window_days(1) == 1
    assert window_days(0) == 1


def test_claims_inside_one_window_are_a_single_occurrence() -> None:
    claims = [_c(1, "1000000"), _c(3, "2000000"), _c(7, "3000000")]
    proposal = propose_occurrences(claims, hours=168)  # 7-day window
    assert not proposal.splits_the_event
    occ = proposal.occurrences[0]
    assert occ.claim_count == 3
    assert occ.gross_incurred == D("6000000")
    assert occ.start_date == dt.date(2027, 9, 1)
    assert occ.end_date == dt.date(2027, 9, 7)


def test_a_gap_beyond_the_window_starts_a_new_occurrence() -> None:
    claims = [_c(1, "1000000"), _c(5, "1000000"), _c(12, "4000000"), _c(14, "1000000")]
    proposal = propose_occurrences(claims, hours=168)  # 7-day window
    assert proposal.splits_the_event
    assert [o.claim_count for o in proposal.occurrences] == [2, 2]
    assert [o.gross_incurred for o in proposal.occurrences] == [D("2000000"), D("5000000")]
    assert proposal.occurrences[1].start_date == dt.date(2027, 9, 12)


def test_a_short_window_splits_more() -> None:
    claims = [_c(1, "1000000"), _c(4, "1000000"), _c(7, "1000000")]
    proposal = propose_occurrences(claims, hours=72)  # 3-day window
    assert [o.index for o in proposal.occurrences] == [1, 2, 3]


def test_empty_claims_gives_no_occurrences() -> None:
    assert propose_occurrences([], hours=168).occurrences == []
