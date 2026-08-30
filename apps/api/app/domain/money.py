"""Money value object and exact allocation.

Financial-safety rules (see docs/DECISIONS.md ADR-0009):

* Money is ``Decimal`` only. Never ``float``.
* Money is canonically whole-cent (2 decimal places). The constructor rejects
  sub-cent precision so that every rounding decision is explicit and happens at a
  named boundary via :meth:`Money.round`.
* Currency is always explicit. Operations on mismatched currencies raise.
* :func:`allocate` splits an amount across weights so the parts sum **exactly** to
  the whole (largest-remainder penny distribution).

This module is pure: standard library only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_FLOOR, ROUND_HALF_EVEN, Decimal
from typing import Final

CENT: Final = Decimal("0.01")
_ZERO: Final = Decimal("0")


class MoneyError(Exception):
    """Base class for money errors."""


class CurrencyMismatchError(MoneyError):
    """Raised when an operation mixes two currencies."""

    def __init__(self, left: str, right: str) -> None:
        super().__init__(f"currency mismatch: {left} vs {right}")
        self.left = left
        self.right = right


class NegativeMoneyError(MoneyError):
    """Raised when a non-negative amount was required."""


class AllocationError(MoneyError):
    """Raised when an allocation cannot be computed."""


def _normalize_currency(currency: str) -> str:
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
        raise MoneyError(f"currency must be a 3-letter ISO 4217 code, got {currency!r}")
    return currency.upper()


@dataclass(frozen=True, slots=True, order=False)
class Money:
    """An amount in a single currency, canonically stored at whole-cent precision."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        currency = _normalize_currency(self.currency)
        object.__setattr__(self, "currency", currency)

        amount = self.amount
        if not isinstance(amount, Decimal):
            raise MoneyError(f"Money.amount must be Decimal, got {type(amount).__name__}")
        if not amount.is_finite():
            raise MoneyError(f"Money.amount must be finite, got {amount!r}")

        quantized = amount.quantize(CENT, rounding=ROUND_HALF_EVEN)
        if quantized != amount:
            raise MoneyError(
                f"Money.amount {amount} has sub-cent precision; use Money.round(...) "
                "to round explicitly at a calculation boundary"
            )
        object.__setattr__(self, "amount", quantized)

    # --- constructors -------------------------------------------------------

    @classmethod
    def zero(cls, currency: str) -> Money:
        return cls(_ZERO, currency)

    @classmethod
    def round(
        cls,
        amount: Decimal,
        currency: str,
        *,
        rounding: str = ROUND_HALF_EVEN,
    ) -> Money:
        """Round an arbitrary-precision Decimal to whole cents. The one sanctioned
        way to cross a rounding boundary."""
        if not isinstance(amount, Decimal):
            raise MoneyError(f"amount must be Decimal, got {type(amount).__name__}")
        if not amount.is_finite():
            raise MoneyError(f"amount must be finite, got {amount!r}")
        return cls(amount.quantize(CENT, rounding=rounding), currency)

    # --- helpers ----------------------------------------------------------

    def _check(self, other: Money) -> None:
        if not isinstance(other, Money):
            raise MoneyError(f"expected Money, got {type(other).__name__}")
        if self.currency != other.currency:
            raise CurrencyMismatchError(self.currency, other.currency)

    @property
    def cents(self) -> int:
        """The amount as an exact integer number of minor units."""
        return int((self.amount / CENT).to_integral_exact())

    @property
    def is_zero(self) -> bool:
        return self.amount == _ZERO

    @property
    def is_negative(self) -> bool:
        return self.amount < _ZERO

    @property
    def is_positive(self) -> bool:
        return self.amount > _ZERO

    def require_non_negative(self, label: str = "amount") -> Money:
        if self.is_negative:
            raise NegativeMoneyError(f"{label} must be non-negative, got {self}")
        return self

    # --- arithmetic -----------------------------------------------------

    def __add__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    # --- ordering (currency-checked) ----------------------------------

    def __lt__(self, other: Money) -> bool:
        self._check(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        self._check(other)
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        self._check(other)
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        self._check(other)
        return self.amount >= other.amount

    @staticmethod
    def max(a: Money, b: Money) -> Money:
        return a if a >= b else b

    @staticmethod
    def min(a: Money, b: Money) -> Money:
        return a if a <= b else b

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"


@dataclass(frozen=True, slots=True)
class Allocation:
    """One participant's exact share of an allocated total."""

    key: str
    weight: Decimal
    amount: Money


def allocate(total: Money, weights: Sequence[tuple[str, Decimal]]) -> list[Allocation]:
    """Split ``total`` across ``weights`` proportionally, so the parts sum to
    ``total`` **exactly**.

    Uses the largest-remainder method at minor-unit (cent) precision: each part
    gets its floored proportional share, then the leftover cents are handed out
    one at a time to the parts with the largest fractional remainder (ties broken
    by input order).
    """
    total.require_non_negative("allocation total")
    if not weights:
        raise AllocationError("cannot allocate across zero weights")

    keys = [k for k, _ in weights]
    if len(set(keys)) != len(keys):
        raise AllocationError("allocation weight keys must be unique")

    decimal_weights: list[Decimal] = []
    for key, weight in weights:
        if not isinstance(weight, Decimal):
            raise AllocationError(f"weight for {key!r} must be Decimal")
        if not weight.is_finite() or weight < _ZERO:
            raise AllocationError(
                f"weight for {key!r} must be finite and non-negative, got {weight}"
            )
        decimal_weights.append(weight)

    weight_sum = sum(decimal_weights, _ZERO)
    if weight_sum <= _ZERO:
        raise AllocationError("allocation weights must sum to a positive value")

    total_cents = total.cents
    floors: list[int] = []
    remainders: list[Decimal] = []
    for weight in decimal_weights:
        exact = Decimal(total_cents) * weight / weight_sum
        floor = int(exact.to_integral_value(rounding=ROUND_FLOOR))
        floors.append(floor)
        remainders.append(exact - floor)

    leftover = total_cents - sum(floors)
    # Hand out leftover cents to the largest fractional remainders, input order breaks ties.
    order = sorted(range(len(weights)), key=lambda i: (-remainders[i], i))
    for i in order[:leftover]:
        floors[i] += 1

    return [
        Allocation(
            key=keys[i],
            weight=decimal_weights[i],
            amount=Money(Decimal(floors[i]) * CENT, total.currency),
        )
        for i in range(len(weights))
    ]
