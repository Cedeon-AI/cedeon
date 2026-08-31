"""Collection tracking: a *recoverable* moving from notified to cash in the bank,
per reinsurer. Pure — standard library only, no AI, no I/O (ADR-0010, ADR-0024).

The expected amount is a fact carried from the immutable ``RecoveryCalculation``.
``agreed`` / ``billed`` / ``collected`` are human-entered facts, corrected over
time; every change is on the append-only audit log.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

_ZERO = Decimal("0.00")


class RecoverableStatus(StrEnum):
    """One reinsurer's leg of a confirmed recovery.

    PENDING ─▶ NOTIFIED ─▶ AGREED ─▶ BILLED ─▶ COLLECTED
                   └──────────┴─────────┴──▶ DISPUTED ──▶ (back to an active state)
                                          └──▶ WRITTEN_OFF
    """

    PENDING = "pending"
    NOTIFIED = "notified"
    AGREED = "agreed"
    BILLED = "billed"
    COLLECTED = "collected"
    DISPUTED = "disputed"
    WRITTEN_OFF = "written_off"

    @property
    def is_open(self) -> bool:
        return self in _OPEN

    @property
    def is_terminal(self) -> bool:
        return self in (RecoverableStatus.COLLECTED, RecoverableStatus.WRITTEN_OFF)


_OPEN = frozenset(
    {
        RecoverableStatus.PENDING,
        RecoverableStatus.NOTIFIED,
        RecoverableStatus.AGREED,
        RecoverableStatus.BILLED,
        RecoverableStatus.DISPUTED,
    }
)

# A forward flow for the "advance" hint. DISPUTED / WRITTEN_OFF are side moves the
# reviewer makes explicitly, never suggested.
_FLOW: tuple[RecoverableStatus, ...] = (
    RecoverableStatus.PENDING,
    RecoverableStatus.NOTIFIED,
    RecoverableStatus.AGREED,
    RecoverableStatus.BILLED,
    RecoverableStatus.COLLECTED,
)


def next_status(current: RecoverableStatus) -> RecoverableStatus | None:
    """The natural next step in the forward flow, or None at the end / off-flow."""
    try:
        i = _FLOW.index(current)
    except ValueError:
        return None
    return _FLOW[i + 1] if i + 1 < len(_FLOW) else None


class AgingBucket(StrEnum):
    CURRENT = "current"
    D1_30 = "1_30"
    D31_60 = "31_60"
    D61_90 = "61_90"
    D90_PLUS = "90_plus"


def days_overdue(due_date: dt.date | None, as_of: dt.date) -> int:
    """Positive when past due, 0 otherwise (and when there is no due date)."""
    if due_date is None:
        return 0
    return max((as_of - due_date).days, 0)


def aging_bucket(due_date: dt.date | None, as_of: dt.date) -> AgingBucket:
    d = days_overdue(due_date, as_of)
    if d <= 0:
        return AgingBucket.CURRENT
    if d <= 30:
        return AgingBucket.D1_30
    if d <= 60:
        return AgingBucket.D31_60
    if d <= 90:
        return AgingBucket.D61_90
    return AgingBucket.D90_PLUS


def outstanding(
    *,
    status: RecoverableStatus,
    expected_amount: Decimal,
    agreed_amount: Decimal | None,
    collected_amount: Decimal,
) -> Decimal:
    """What is still owed on this leg. Written-off legs owe nothing; otherwise it is
    the agreed figure (falling back to expected) less what has been collected."""
    if status is RecoverableStatus.WRITTEN_OFF:
        return _ZERO
    basis = agreed_amount if agreed_amount is not None else expected_amount
    return max(basis - collected_amount, _ZERO)


@dataclass(frozen=True, slots=True)
class RecoverableRow:
    """The fields of one recoverable the summary math needs."""

    status: RecoverableStatus
    currency: str
    expected_amount: Decimal
    agreed_amount: Decimal | None
    collected_amount: Decimal
    due_date: dt.date | None


@dataclass(frozen=True, slots=True)
class StatusTotal:
    status: RecoverableStatus
    count: int
    outstanding: Decimal


@dataclass(frozen=True, slots=True)
class RecoverableSummary:
    currency: str
    count: int
    total_expected: Decimal
    total_collected: Decimal
    total_outstanding: Decimal
    overdue_count: int
    overdue_outstanding: Decimal
    by_status: tuple[StatusTotal, ...]
    by_aging: dict[str, Decimal]


def summarize_recoverables(
    rows: Iterable[RecoverableRow], *, as_of: dt.date, currency: str = "USD"
) -> RecoverableSummary:
    """Portfolio roll-up. Single-currency: rows in another currency are ignored
    (there is no FX — mirrors the calculation engine, ADR-0018)."""
    scoped = [r for r in rows if r.currency == currency]

    total_expected = _ZERO
    total_collected = _ZERO
    total_outstanding = _ZERO
    overdue_count = 0
    overdue_outstanding = _ZERO
    status_count: dict[RecoverableStatus, int] = {}
    status_out: dict[RecoverableStatus, Decimal] = {}
    aging: dict[str, Decimal] = {b.value: _ZERO for b in AgingBucket}

    for r in scoped:
        out = outstanding(
            status=r.status,
            expected_amount=r.expected_amount,
            agreed_amount=r.agreed_amount,
            collected_amount=r.collected_amount,
        )
        total_expected += r.expected_amount
        total_collected += r.collected_amount
        total_outstanding += out
        status_count[r.status] = status_count.get(r.status, 0) + 1
        status_out[r.status] = status_out.get(r.status, _ZERO) + out

        if out > _ZERO:
            bucket = aging_bucket(r.due_date, as_of)
            aging[bucket.value] += out
            if bucket is not AgingBucket.CURRENT:
                overdue_count += 1
                overdue_outstanding += out

    by_status = tuple(
        StatusTotal(status=s, count=status_count[s], outstanding=status_out[s])
        for s in RecoverableStatus
        if s in status_count
    )
    return RecoverableSummary(
        currency=currency,
        count=len(scoped),
        total_expected=total_expected,
        total_collected=total_collected,
        total_outstanding=total_outstanding,
        overdue_count=overdue_count,
        overdue_outstanding=overdue_outstanding,
        by_status=by_status,
        by_aging=aging,
    )
