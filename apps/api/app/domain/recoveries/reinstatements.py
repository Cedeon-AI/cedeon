"""Reinstatement premium — deterministic (docs/PRODUCT.md §5; §7 scope expansion,
2026-09-01).

When a loss erodes an XOL layer, the layer limit is reinstated for later losses in
the period and the cedent owes a *reinstatement premium* for the cover restored.
This is pure arithmetic over validated terms — the layer's deposit premium, the
rate for each reinstatement, and how much of the limit earlier losses in the
period already used. No LLM anywhere: the analyst confirms the terms, the engine
computes the premium.

Standard reinstatement: each reinstatement restores exactly one full layer limit,
and the premium is charged pro-rata as to the amount reinstated by *this* loss
(earlier losses were charged when they happened):

    premium(k) = deposit_premium x (amount_reinstated_by_this_loss(k) / layer_limit)
                 x rate(k) x time_factor

``time_factor`` is 1 for a flat reinstatement, or the unexpired fraction of the
treaty period for a pro-rata-as-to-time reinstatement.

Pure: standard library only (ADR-0010).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum

_ZERO = Decimal("0.00")
_CENT = Decimal("0.01")
_ONE = Decimal("1")


class ReinstatementBasis(StrEnum):
    FLAT = "flat"
    PRO_RATA_TIME = "pro_rata_time"


@dataclass(frozen=True, slots=True)
class ReinstatementCharge:
    order: int  # 1 = first reinstatement
    amount_reinstated: Decimal  # restored by THIS loss (earlier losses charged already)
    rate: Decimal  # e.g. Decimal("1") for "at 100%"
    time_factor: Decimal
    premium: Decimal


@dataclass(frozen=True, slots=True)
class ReinstatementResult:
    reinstatements_available: int
    prior_erosion: Decimal
    this_loss_to_layer: Decimal
    total_erosion: Decimal
    cover_exhausted: bool  # every limit + reinstatement consumed
    charges: list[ReinstatementCharge]
    premium_due: Decimal
    trace: list[str] = field(default_factory=list)


def _q(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_EVEN)


def compute_reinstatement_premium(
    *,
    layer_limit: Decimal,
    deposit_premium: Decimal,
    rates: list[Decimal],
    basis: ReinstatementBasis,
    prior_erosion: Decimal,
    this_loss_to_layer: Decimal,
    unexpired_fraction: Decimal = _ONE,
) -> ReinstatementResult:
    if layer_limit <= _ZERO:
        raise ValueError("layer limit must be positive")
    if deposit_premium < _ZERO:
        raise ValueError("deposit premium must not be negative")
    prior = max(prior_erosion, _ZERO)
    this = max(this_loss_to_layer, _ZERO)
    total = prior + this
    n = len(rates)
    time_factor = (
        _ONE
        if basis is ReinstatementBasis.FLAT
        else max(_ZERO, min(_ONE, unexpired_fraction))
    )

    trace: list[str] = [
        f"layer limit {layer_limit}, deposit premium {deposit_premium}, "
        f"{n} reinstatement(s) at {[str(r) for r in rates]}, basis {basis.value}",
        f"prior erosion {prior} + this loss {this} = {total} cumulative",
    ]
    if basis is ReinstatementBasis.PRO_RATA_TIME:
        trace.append(f"time factor (unexpired period) = {time_factor}")

    charges: list[ReinstatementCharge] = []
    for k, rate in enumerate(rates, start=1):
        # reinstatement k restores erosion in the band [(k-1)·limit, k·limit].
        band_lo = layer_limit * (k - 1)
        band_hi = layer_limit * k
        reinstated = max(_ZERO, min(total, band_hi) - max(prior, band_lo))
        if reinstated <= _ZERO:
            continue
        premium = _q(deposit_premium * (reinstated / layer_limit) * rate * time_factor)
        charges.append(
            ReinstatementCharge(
                order=k,
                amount_reinstated=_q(reinstated),
                rate=rate,
                time_factor=time_factor,
                premium=premium,
            )
        )
        trace.append(
            f"reinstatement {k}: {_q(reinstated)} reinstated / {layer_limit} "
            f"x {deposit_premium} x {rate} x {time_factor} = {premium}"
        )

    premium_due = _q(sum((c.premium for c in charges), _ZERO))
    exhausted = total >= layer_limit * (n + 1)
    if exhausted:
        trace.append(f"cover exhausted — {total} used of {layer_limit * (n + 1)} available")
    trace.append(f"reinstatement premium due (this loss): {premium_due}")

    return ReinstatementResult(
        reinstatements_available=n,
        prior_erosion=_q(prior),
        this_loss_to_layer=_q(this),
        total_erosion=_q(total),
        cover_exhausted=exhausted,
        charges=charges,
        premium_due=premium_due,
        trace=trace,
    )
