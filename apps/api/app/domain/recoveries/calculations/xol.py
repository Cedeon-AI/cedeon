"""Per-occurrence excess-of-loss recovery — the only treaty structure in the MVP.

    amount_above_attachment = max(gross_event_loss - attachment, 0)
    layer_recovery          = min(amount_above_attachment, limit)
    participant_recovery[i] = layer_recovery x (share[i] / Σ share)   -- penny-exact

Pure. Standard library + `app.domain.money` only. No AI, no I/O. Bump
``ENGINE_VERSION`` on any behavioural change (ADR-0010).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.domain.money import Allocation, Money, allocate

ENGINE_VERSION = "1.0.0"

# Placed shares are allowed to overshoot 100% by this much (rounding in source data).
_SHARE_TOLERANCE = Decimal("0.0005")
_ONE = Decimal("1")
_ZERO = Decimal("0")


class CalculationError(Exception):
    """Raised on invalid calculation inputs. Never swallowed — a bad number must fail loud."""


@dataclass(frozen=True, slots=True)
class CalcStep:
    label: str
    expression: str
    result: str


@dataclass(frozen=True, slots=True)
class XolRecoveryResult:
    currency: str
    gross_loss: Money
    attachment: Money
    limit: Money
    amount_above_attachment: Money
    layer_recovery: Money
    engine_version: str
    trace: tuple[CalcStep, ...]


@dataclass(frozen=True, slots=True)
class Participation:
    key: str
    label: str
    share: Decimal  # in [0, 1]


@dataclass(frozen=True, slots=True)
class ParticipantAllocation:
    key: str
    label: str
    share: Decimal
    amount: Money


@dataclass(frozen=True, slots=True)
class RecoveryCalculation:
    xol: XolRecoveryResult
    allocations: tuple[ParticipantAllocation, ...]
    cedent_retention: Money
    engine_version: str

    @property
    def layer_recovery(self) -> Money:
        return self.xol.layer_recovery

    @property
    def total_ceded(self) -> Money:
        return self.layer_recovery - self.cedent_retention


def calculate_xol_recovery(gross_loss: Money, attachment: Money, limit: Money) -> XolRecoveryResult:
    currency = gross_loss.currency
    if attachment.currency != currency or limit.currency != currency:
        raise CalculationError(
            "gross loss, attachment and limit must share one currency "
            f"(got {gross_loss.currency}, {attachment.currency}, {limit.currency})"
        )

    if gross_loss.is_negative:
        raise CalculationError(f"gross loss must be non-negative, got {gross_loss}")
    if attachment.is_negative:
        raise CalculationError(f"attachment must be non-negative, got {attachment}")
    if not limit.is_positive:
        raise CalculationError(f"limit must be greater than zero, got {limit}")

    zero = Money.zero(currency)
    above = Money.max(gross_loss - attachment, zero)
    layer_recovery = Money.min(above, limit)

    trace = (
        CalcStep("gross event loss", str(gross_loss.amount), str(gross_loss.amount)),
        CalcStep(
            "amount above attachment",
            f"max({gross_loss.amount} - {attachment.amount}, 0)",
            str(above.amount),
        ),
        CalcStep(
            "layer recovery",
            f"min({above.amount}, {limit.amount})",
            str(layer_recovery.amount),
        ),
    )
    return XolRecoveryResult(
        currency=currency,
        gross_loss=gross_loss,
        attachment=attachment,
        limit=limit,
        amount_above_attachment=above,
        layer_recovery=layer_recovery,
        engine_version=ENGINE_VERSION,
        trace=trace,
    )


def allocate_recovery(
    layer_recovery: Money, participations: Sequence[Participation]
) -> list[ParticipantAllocation]:
    """Split ``layer_recovery`` across participants: each gets
    ``layer_recovery x share``, penny-exact, summing to
    ``round(layer_recovery x Σ share)``."""
    if not participations:
        return []

    keys = [p.key for p in participations]
    if len(set(keys)) != len(keys):
        raise CalculationError("participation keys must be unique")

    share_sum = _ZERO
    for participation in participations:
        if not isinstance(participation.share, Decimal):
            raise CalculationError(f"share for {participation.key!r} must be Decimal")
        if not participation.share.is_finite() or participation.share < _ZERO:
            raise CalculationError(
                f"share for {participation.key!r} must be finite and non-negative, "
                f"got {participation.share}"
            )
        share_sum += participation.share
    if share_sum > _ONE + _SHARE_TOLERANCE:
        raise CalculationError(f"placed shares sum to {share_sum} (> 100%)")
    if share_sum == _ZERO:
        raise CalculationError("placed shares sum to zero")

    ceded_share = min(share_sum, _ONE)
    ceded_total = Money.round(layer_recovery.amount * ceded_share, layer_recovery.currency)

    parts: list[Allocation] = allocate(ceded_total, [(p.key, p.share) for p in participations])
    by_key = {p.key: p for p in participations}
    return [
        ParticipantAllocation(
            key=part.key,
            label=by_key[part.key].label,
            share=by_key[part.key].share,
            amount=part.amount,
        )
        for part in parts
    ]


def calculate_recovery(
    *,
    gross_loss: Money,
    attachment: Money,
    limit: Money,
    participations: Sequence[Participation],
) -> RecoveryCalculation:
    xol = calculate_xol_recovery(gross_loss, attachment, limit)
    allocations = allocate_recovery(xol.layer_recovery, participations)
    ceded = sum((a.amount for a in allocations), Money.zero(xol.currency))
    return RecoveryCalculation(
        xol=xol,
        allocations=tuple(allocations),
        cedent_retention=xol.layer_recovery - ceded,
        engine_version=ENGINE_VERSION,
    )
