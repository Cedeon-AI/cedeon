"""The deterministic XOL recovery engine. Higher priority than any UI (ADR-0010)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.money import CurrencyMismatchError, Money
from app.domain.recoveries import (
    ENGINE_VERSION,
    Participation,
    allocate_recovery,
    calculate_recovery,
    calculate_xol_recovery,
)
from app.domain.recoveries.calculations import CalculationError

USD = "USD"


def M(amount: str | int, currency: str = USD) -> Money:
    return Money(Decimal(str(amount)), currency)


ATTACHMENT = M(50_000_000)
LIMIT = M(20_000_000)


# --- golden table: $20M xs $50M ------------------------------------------

GOLDEN = [
    ("30000000.00", "0.00"),  # below attachment
    ("50000000.00", "0.00"),  # exactly at attachment
    ("50000000.01", "0.01"),  # one cent into the layer
    ("55000000.00", "5000000.00"),  # inside the layer
    ("58700000.00", "8700000.00"),  # the demo event
    ("70000000.00", "20000000.00"),  # exactly exhausts the layer
    ("70000000.01", "20000000.00"),  # just past exhaustion
    ("100000000.00", "20000000.00"),  # far above
]


@pytest.mark.parametrize(("gross", "expected"), GOLDEN)
def test_golden_recovery_table(gross: str, expected: str) -> None:
    result = calculate_xol_recovery(M(gross), ATTACHMENT, LIMIT)
    assert result.layer_recovery.amount == Decimal(expected)
    assert result.engine_version == ENGINE_VERSION
    assert result.currency == USD


def test_amount_above_attachment_is_reported() -> None:
    result = calculate_xol_recovery(M("58700000.00"), ATTACHMENT, LIMIT)
    assert result.amount_above_attachment.amount == Decimal("8700000.00")


def test_trace_records_each_step() -> None:
    result = calculate_xol_recovery(M("58700000.00"), ATTACHMENT, LIMIT)
    labels = [step.label for step in result.trace]
    assert labels == ["gross event loss", "amount above attachment", "layer recovery"]
    assert result.trace[-1].result == "8700000.00"


def test_zero_gross_loss() -> None:
    assert calculate_xol_recovery(M(0), ATTACHMENT, LIMIT).layer_recovery.is_zero


def test_zero_attachment_layer_from_ground_up() -> None:
    result = calculate_xol_recovery(M("15000000.00"), M(0), LIMIT)
    assert result.layer_recovery.amount == Decimal("15000000.00")


class TestInvalidInputs:
    def test_negative_gross_loss_rejected(self) -> None:
        with pytest.raises(CalculationError, match="gross loss"):
            calculate_xol_recovery(M("-1.00"), ATTACHMENT, LIMIT)

    def test_negative_attachment_rejected(self) -> None:
        with pytest.raises(CalculationError, match="attachment"):
            calculate_xol_recovery(M("55000000.00"), M("-1.00"), LIMIT)

    def test_zero_limit_rejected(self) -> None:
        with pytest.raises(CalculationError, match="limit"):
            calculate_xol_recovery(M("55000000.00"), ATTACHMENT, M(0))

    def test_negative_limit_rejected(self) -> None:
        with pytest.raises(CalculationError, match="limit"):
            calculate_xol_recovery(M("55000000.00"), ATTACHMENT, M("-1.00"))

    def test_currency_mismatch_rejected(self) -> None:
        with pytest.raises(CalculationError, match="currency"):
            calculate_xol_recovery(M("55000000.00"), M(50_000_000, "EUR"), LIMIT)


# --- allocation --------------------------------------------------------


def _parts(*pairs: tuple[str, str]) -> list[Participation]:
    return [Participation(key=k, label=k.title(), share=Decimal(s)) for k, s in pairs]


def test_golden_allocation() -> None:
    allocs = allocate_recovery(
        M("8700000.00"), _parts(("alpha", "0.5"), ("beta", "0.3"), ("gamma", "0.2"))
    )
    assert {a.label: a.amount.amount for a in allocs} == {
        "Alpha": Decimal("4350000.00"),
        "Beta": Decimal("2610000.00"),
        "Gamma": Decimal("1740000.00"),
    }
    assert sum((a.amount.amount for a in allocs), Decimal("0")) == Decimal("8700000.00")


def test_partial_placement_leaves_cedent_retention() -> None:
    calc = calculate_recovery(
        gross_loss=M("58700000.00"),
        attachment=ATTACHMENT,
        limit=LIMIT,
        participations=_parts(("alpha", "0.5"), ("beta", "0.3")),  # 80% placed
    )
    ceded = sum((a.amount.amount for a in calc.allocations), Decimal("0"))
    assert ceded == Decimal("6960000.00")  # 80% of 8.7M
    assert calc.cedent_retention.amount == Decimal("1740000.00")
    assert calc.total_ceded.amount + calc.cedent_retention.amount == calc.layer_recovery.amount


def test_penny_residual_is_distributed_and_sums_exactly() -> None:
    allocs = allocate_recovery(
        M("100.00"), _parts(("a", "0.3333"), ("b", "0.3333"), ("c", "0.3334"))
    )
    assert sum((a.amount.cents for a in allocs), 0) == 10_000


def test_allocation_rejects_shares_over_100_percent() -> None:
    with pytest.raises(CalculationError, match="> 100"):
        allocate_recovery(M("8700000.00"), _parts(("a", "0.6"), ("b", "0.6")))


def test_allocation_rejects_zero_and_duplicate() -> None:
    with pytest.raises(CalculationError, match="sum to zero"):
        allocate_recovery(M("100.00"), _parts(("a", "0"), ("b", "0")))
    with pytest.raises(CalculationError, match="unique"):
        allocate_recovery(M("100.00"), _parts(("a", "0.5"), ("a", "0.5")))


def test_no_participations_yields_no_allocations() -> None:
    calc = calculate_recovery(
        gross_loss=M("58700000.00"), attachment=ATTACHMENT, limit=LIMIT, participations=[]
    )
    assert calc.allocations == ()
    assert calc.cedent_retention.amount == calc.layer_recovery.amount


def test_full_calculation_golden() -> None:
    calc = calculate_recovery(
        gross_loss=M("58700000.00"),
        attachment=ATTACHMENT,
        limit=LIMIT,
        participations=_parts(("alpha", "0.5"), ("beta", "0.3"), ("gamma", "0.2")),
    )
    assert calc.layer_recovery.amount == Decimal("8700000.00")
    assert [a.amount.amount for a in calc.allocations] == [
        Decimal("4350000.00"),
        Decimal("2610000.00"),
        Decimal("1740000.00"),
    ]
    assert calc.cedent_retention.is_zero
    assert calc.engine_version == ENGINE_VERSION


# --- properties -------------------------------------------------------

_money_cents = st.integers(min_value=0, max_value=10**11)


@given(gross_cents=_money_cents)
def test_recovery_is_within_zero_and_limit(gross_cents: int) -> None:
    result = calculate_xol_recovery(Money(Decimal(gross_cents) / 100, USD), ATTACHMENT, LIMIT)
    assert Decimal("0") <= result.layer_recovery.amount <= LIMIT.amount


@given(a=_money_cents, b=_money_cents)
def test_recovery_is_monotonic_in_gross_loss(a: int, b: int) -> None:
    lo, hi = sorted((a, b))
    r_lo = calculate_xol_recovery(Money(Decimal(lo) / 100, USD), ATTACHMENT, LIMIT)
    r_hi = calculate_xol_recovery(Money(Decimal(hi) / 100, USD), ATTACHMENT, LIMIT)
    assert r_hi.layer_recovery.amount >= r_lo.layer_recovery.amount


@given(
    layer_cents=st.integers(min_value=0, max_value=10**10),
    weights=st.lists(st.integers(min_value=1, max_value=10**6), min_size=1, max_size=6),
)
def test_allocations_always_sum_to_ceded_total_exactly(
    layer_cents: int, weights: list[int]
) -> None:
    total_weight = sum(weights)
    parts = [
        Participation(key=f"p{i}", label=f"P{i}", share=Decimal(w) / total_weight)
        for i, w in enumerate(weights)
    ]
    layer = Money(Decimal(layer_cents) / 100, USD)
    allocs = allocate_recovery(layer, parts)
    assert sum((a.amount.cents for a in allocs), 0) == layer.cents
    assert all(not a.amount.is_negative for a in allocs)


def test_currency_mismatch_in_money_ops_surfaces() -> None:
    # a stray currency in participations can't happen (they carry only Decimal),
    # but a mismatched layer/limit is caught by calculate_xol_recovery, and
    # Money arithmetic itself is currency-checked:
    with pytest.raises(CurrencyMismatchError):
        _ = M("1.00", "USD") + M("1.00", "EUR")
