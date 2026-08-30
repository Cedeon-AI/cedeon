"""Money value object + exact allocation. Financial-safety critical."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.money import (
    AllocationError,
    CurrencyMismatchError,
    Money,
    MoneyError,
    NegativeMoneyError,
    allocate,
)

USD = "USD"


class TestConstruction:
    def test_normalizes_currency_case(self) -> None:
        assert Money(Decimal("1.00"), "usd").currency == "USD"

    def test_accepts_whole_cent(self) -> None:
        assert Money(Decimal("10"), USD).amount == Decimal("10.00")
        assert Money(Decimal("10.5"), USD).amount == Decimal("10.50")
        assert Money(Decimal("2610000.0000"), USD).amount == Decimal("2610000.00")

    def test_rejects_sub_cent_precision(self) -> None:
        with pytest.raises(MoneyError, match="sub-cent"):
            Money(Decimal("100.005"), USD)

    def test_rejects_float(self) -> None:
        with pytest.raises(MoneyError):
            Money(1.0, USD)  # type: ignore[arg-type]

    def test_rejects_non_finite(self) -> None:
        with pytest.raises(MoneyError):
            Money(Decimal("NaN"), USD)
        with pytest.raises(MoneyError):
            Money(Decimal("Infinity"), USD)

    def test_rejects_bad_currency(self) -> None:
        for bad in ["US", "USDX", "12$", ""]:
            with pytest.raises(MoneyError):
                Money(Decimal("1.00"), bad)

    def test_round_is_half_even(self) -> None:
        assert Money.round(Decimal("100.005"), USD).amount == Decimal("100.00")
        assert Money.round(Decimal("100.015"), USD).amount == Decimal("100.02")
        assert Money.round(Decimal("100.011"), USD).amount == Decimal("100.01")

    def test_zero(self) -> None:
        z = Money.zero(USD)
        assert z.amount == Decimal("0.00")
        assert z.is_zero

    def test_equality_and_hash(self) -> None:
        assert Money(Decimal("1"), "usd") == Money(Decimal("1.00"), "USD")
        assert len({Money(Decimal("1.00"), USD), Money(Decimal("1"), "usd")}) == 1


class TestArithmetic:
    def test_add_sub(self) -> None:
        assert Money(Decimal("50"), USD) + Money(Decimal("8.70"), USD) == Money(
            Decimal("58.70"), USD
        )
        assert Money(Decimal("58.70"), USD) - Money(Decimal("50"), USD) == Money(
            Decimal("8.70"), USD
        )

    def test_currency_mismatch_raises(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            Money(Decimal("1.00"), USD) + Money(Decimal("1.00"), "EUR")
        with pytest.raises(CurrencyMismatchError):
            _ = Money(Decimal("1.00"), USD) < Money(Decimal("2.00"), "EUR")

    def test_ordering_and_min_max(self) -> None:
        a, b = Money(Decimal("5.00"), USD), Money(Decimal("9.00"), USD)
        assert a < b and b > a and a <= a and b >= b
        assert Money.max(a, b) == b
        assert Money.min(a, b) == a

    def test_negation_and_sign(self) -> None:
        assert (-Money(Decimal("5.00"), USD)).amount == Decimal("-5.00")
        assert Money(Decimal("-0.01"), USD).is_negative
        assert Money(Decimal("0.01"), USD).is_positive

    def test_require_non_negative(self) -> None:
        Money(Decimal("0.00"), USD).require_non_negative()
        with pytest.raises(NegativeMoneyError):
            Money(Decimal("-0.01"), USD).require_non_negative("recovery")

    def test_cents(self) -> None:
        assert Money(Decimal("8700000.00"), USD).cents == 870_000_000


class TestAllocate:
    def test_golden_participation_split(self) -> None:
        """8,700,000.00 split 50/30/20 → 4,350,000 / 2,610,000 / 1,740,000."""
        parts = allocate(
            Money(Decimal("8700000.00"), USD),
            [("alpha", Decimal("0.50")), ("beta", Decimal("0.30")), ("gamma", Decimal("0.20"))],
        )
        assert [p.amount.amount for p in parts] == [
            Decimal("4350000.00"),
            Decimal("2610000.00"),
            Decimal("1740000.00"),
        ]
        assert sum((p.amount.amount for p in parts), Decimal("0")) == Decimal("8700000.00")

    def test_residual_cents_go_to_largest_remainder_then_order(self) -> None:
        # 100.00 split in three equal parts → 33.34 / 33.33 / 33.33 (extra cent to first).
        parts = allocate(
            Money(Decimal("100.00"), USD),
            [("a", Decimal("1")), ("b", Decimal("1")), ("c", Decimal("1"))],
        )
        assert [p.amount.amount for p in parts] == [
            Decimal("33.34"),
            Decimal("33.33"),
            Decimal("33.33"),
        ]

    def test_sum_is_exact_for_awkward_split(self) -> None:
        parts = allocate(
            Money(Decimal("1000000.01"), USD),
            [("a", Decimal("0.333333")), ("b", Decimal("0.333333")), ("c", Decimal("0.333334"))],
        )
        assert sum((p.amount.amount for p in parts), Decimal("0")) == Decimal("1000000.01")

    def test_zero_total(self) -> None:
        parts = allocate(Money.zero(USD), [("a", Decimal("1")), ("b", Decimal("2"))])
        assert all(p.amount.is_zero for p in parts)

    def test_single_weight_gets_everything(self) -> None:
        parts = allocate(Money(Decimal("42.42"), USD), [("only", Decimal("0.9"))])
        assert parts[0].amount.amount == Decimal("42.42")

    def test_rejects_empty_negative_and_duplicate(self) -> None:
        with pytest.raises(AllocationError):
            allocate(Money(Decimal("1.00"), USD), [])
        with pytest.raises(AllocationError):
            allocate(Money(Decimal("1.00"), USD), [("a", Decimal("-1"))])
        with pytest.raises(AllocationError):
            allocate(Money(Decimal("1.00"), USD), [("a", Decimal("0")), ("b", Decimal("0"))])
        with pytest.raises(AllocationError):
            allocate(Money(Decimal("1.00"), USD), [("a", Decimal("1")), ("a", Decimal("1"))])

    def test_rejects_negative_total(self) -> None:
        with pytest.raises(NegativeMoneyError):
            allocate(Money(Decimal("-1.00"), USD), [("a", Decimal("1"))])

    @given(
        total_cents=st.integers(min_value=0, max_value=10**12),
        weights=st.lists(st.integers(min_value=1, max_value=10**6), min_size=1, max_size=8),
    )
    def test_property_allocations_always_sum_exactly(
        self, total_cents: int, weights: list[int]
    ) -> None:
        total = Money(Decimal(total_cents) / 100, USD)
        parts = allocate(total, [(f"p{i}", Decimal(w)) for i, w in enumerate(weights)])
        assert sum((p.amount.cents for p in parts), 0) == total.cents
        assert all(not p.amount.is_negative for p in parts)
