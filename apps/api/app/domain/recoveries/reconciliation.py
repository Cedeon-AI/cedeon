"""Reconciliation intelligence — the first Exception module.

Deterministic checks over the amounts Cedeon already holds for one recoverable:
the calculated ``expected`` against the human-entered ``agreed`` / ``billed`` /
``collected``. Code finds the mismatch; a human resolves it. No AI, no external
statement ingest yet — that is the larger reconciliation module (PRODUCT §1a).

Pure: standard library only (ADR-0010).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.domain.recoveries.collection import RecoverableStatus

# Gaps at or below this are rounding, not exceptions.
_MATERIALITY = Decimal("1.00")
_ZERO = Decimal("0.00")


class ReconcileKind(StrEnum):
    AGREED_BELOW_EXPECTED = "agreed_below_expected"
    AGREED_ABOVE_EXPECTED = "agreed_above_expected"
    BILLED_NOT_AGREED = "billed_not_agreed"
    COLLECTED_OVER_BILLED = "collected_over_billed"
    COLLECTED_SHORT = "collected_short"
    BILLED_WITHOUT_AGREEMENT = "billed_without_agreement"


@dataclass(frozen=True, slots=True)
class ReconcileFinding:
    kind: ReconcileKind
    text: str
    left: Decimal
    right: Decimal

    @property
    def gap(self) -> Decimal:
        return abs(self.left - self.right)


@dataclass(frozen=True, slots=True)
class RecoverableAmounts:
    status: RecoverableStatus
    currency: str
    expected: Decimal
    agreed: Decimal | None
    billed: Decimal | None
    collected: Decimal


def _money(value: Decimal) -> str:
    return f"{value:,.2f}"


def reconcile(r: RecoverableAmounts) -> list[ReconcileFinding]:
    """Every material mismatch on this leg, worst gap first. Written-off legs are
    a deliberate human decision — not reconciled."""
    if r.status is RecoverableStatus.WRITTEN_OFF:
        return []

    out: list[ReconcileFinding] = []
    ccy = r.currency

    if r.agreed is not None:
        delta = r.agreed - r.expected
        if delta <= -_MATERIALITY:
            out.append(
                ReconcileFinding(
                    ReconcileKind.AGREED_BELOW_EXPECTED,
                    f"Reinsurer agreed {ccy} {_money(r.agreed)} against Cedeon's "
                    f"{ccy} {_money(r.expected)} — {ccy} {_money(-delta)} short. "
                    "Check the calculation basis or a partial settlement.",
                    left=r.expected,
                    right=r.agreed,
                )
            )
        elif delta >= _MATERIALITY:
            out.append(
                ReconcileFinding(
                    ReconcileKind.AGREED_ABOVE_EXPECTED,
                    f"Agreed {ccy} {_money(r.agreed)} exceeds the calculated "
                    f"{ccy} {_money(r.expected)} by {ccy} {_money(delta)} — confirm the figure.",
                    left=r.expected,
                    right=r.agreed,
                )
            )

    if r.billed is not None and r.agreed is not None and abs(r.billed - r.agreed) >= _MATERIALITY:
        out.append(
            ReconcileFinding(
                ReconcileKind.BILLED_NOT_AGREED,
                f"Billed {ccy} {_money(r.billed)} but agreed {ccy} {_money(r.agreed)} — "
                f"{ccy} {_money(abs(r.billed - r.agreed))} difference.",
                left=r.agreed,
                right=r.billed,
            )
        )

    if r.billed is not None and r.agreed is None and r.billed >= _MATERIALITY:
        out.append(
            ReconcileFinding(
                ReconcileKind.BILLED_WITHOUT_AGREEMENT,
                f"Billed {ccy} {_money(r.billed)} with no agreed figure recorded — "
                "capture what the reinsurer agreed.",
                left=_ZERO,
                right=r.billed,
            )
        )

    basis = r.billed if r.billed is not None else r.agreed
    if basis is not None:
        if r.collected - basis >= _MATERIALITY:
            out.append(
                ReconcileFinding(
                    ReconcileKind.COLLECTED_OVER_BILLED,
                    f"Collected {ccy} {_money(r.collected)} against {ccy} {_money(basis)} "
                    f"— {ccy} {_money(r.collected - basis)} over. Check for a duplicate receipt.",
                    left=basis,
                    right=r.collected,
                )
            )
        elif r.status is RecoverableStatus.COLLECTED and basis - r.collected >= _MATERIALITY:
            out.append(
                ReconcileFinding(
                    ReconcileKind.COLLECTED_SHORT,
                    f"Marked collected but {ccy} {_money(r.collected)} received against "
                    f"{ccy} {_money(basis)} — {ccy} {_money(basis - r.collected)} unpaid.",
                    left=basis,
                    right=r.collected,
                )
            )

    out.sort(key=lambda f: f.gap, reverse=True)
    return out
