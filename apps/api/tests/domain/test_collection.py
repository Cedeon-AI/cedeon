"""Pure tests for the collection-tracking domain (ADR-0024). No DB, no AI."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from app.domain.recoveries import (
    AgingBucket,
    RecoverableRow,
    RecoverableStatus,
    aging_bucket,
    days_overdue,
    next_status,
    outstanding,
    summarize_recoverables,
)

_TODAY = dt.date(2027, 6, 1)
D = Decimal


def test_next_status_walks_the_forward_flow() -> None:
    assert next_status(RecoverableStatus.PENDING) is RecoverableStatus.NOTIFIED
    assert next_status(RecoverableStatus.BILLED) is RecoverableStatus.COLLECTED
    assert next_status(RecoverableStatus.COLLECTED) is None
    # off-flow states get no suggestion
    assert next_status(RecoverableStatus.DISPUTED) is None


@pytest.mark.parametrize(
    ("due", "expected_days", "expected_bucket"),
    [
        (None, 0, AgingBucket.CURRENT),
        (dt.date(2027, 7, 1), 0, AgingBucket.CURRENT),  # not yet due
        (dt.date(2027, 5, 20), 12, AgingBucket.D1_30),
        (dt.date(2027, 4, 15), 47, AgingBucket.D31_60),
        (dt.date(2027, 3, 20), 73, AgingBucket.D61_90),
        (dt.date(2027, 1, 1), 151, AgingBucket.D90_PLUS),
    ],
)
def test_aging(due: dt.date | None, expected_days: int, expected_bucket: AgingBucket) -> None:
    assert days_overdue(due, _TODAY) == expected_days
    assert aging_bucket(due, _TODAY) is expected_bucket


def test_outstanding_uses_agreed_then_expected_then_zero_when_written_off() -> None:
    assert outstanding(
        status=RecoverableStatus.BILLED,
        expected_amount=D("4350000.00"),
        agreed_amount=None,
        collected_amount=D("0"),
    ) == D("4350000.00")
    # agreed lower than expected → outstanding follows agreed
    assert outstanding(
        status=RecoverableStatus.AGREED,
        expected_amount=D("4350000.00"),
        agreed_amount=D("4000000.00"),
        collected_amount=D("1000000.00"),
    ) == D("3000000.00")
    # over-collected never goes negative
    assert outstanding(
        status=RecoverableStatus.COLLECTED,
        expected_amount=D("100.00"),
        agreed_amount=None,
        collected_amount=D("150.00"),
    ) == D("0.00")
    # written off owes nothing regardless
    assert outstanding(
        status=RecoverableStatus.WRITTEN_OFF,
        expected_amount=D("4350000.00"),
        agreed_amount=None,
        collected_amount=D("0"),
    ) == D("0.00")


def test_summary_rolls_up_the_golden_split() -> None:
    rows = [
        RecoverableRow(
            RecoverableStatus.COLLECTED, "USD", D("4350000.00"), None, D("4350000.00"), None
        ),
        RecoverableRow(
            RecoverableStatus.BILLED, "USD", D("2610000.00"), None, D("0"), dt.date(2027, 4, 1)
        ),
        RecoverableRow(RecoverableStatus.NOTIFIED, "USD", D("1740000.00"), None, D("0"), None),
        # a EUR row is ignored — no FX
        RecoverableRow(RecoverableStatus.NOTIFIED, "EUR", D("999.00"), None, D("0"), None),
    ]
    s = summarize_recoverables(rows, as_of=_TODAY, currency="USD")

    assert s.count == 3
    assert s.total_expected == D("8700000.00")
    assert s.total_collected == D("4350000.00")
    assert s.total_outstanding == D("4350000.00")  # 2.61M billed + 1.74M notified
    assert s.overdue_count == 1  # only the billed one has a past-due date
    assert s.overdue_outstanding == D("2610000.00")
    assert s.by_aging["61_90"] == D("2610000.00")
    assert s.by_aging["current"] == D("1740000.00")
    statuses = {t.status: t for t in s.by_status}
    assert statuses[RecoverableStatus.COLLECTED].outstanding == D("0.00")
    assert statuses[RecoverableStatus.BILLED].count == 1
