"""Reinsurer-statement reconciliation — the larger Exception module (PRODUCT §1a).

Given what a reinsurer says it has agreed / paid on one recoverable, and what
Cedeon holds (the calculated ``expected`` plus the human-entered ``agreed`` /
``collected``), find where the two views disagree. Deterministic; a human resolves
each finding. No AI.

Pure: standard library only (ADR-0010).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

_MATERIALITY = Decimal("1.00")


class StatementFindingKind(StrEnum):
    NO_MATCH = "no_match"
    CLEAN = "clean"
    CURRENCY_MISMATCH = "currency_mismatch"
    THEIR_AGREED_BELOW_OURS = "their_agreed_below_ours"
    THEIR_AGREED_ABOVE_OURS = "their_agreed_above_ours"
    THEIR_AGREED_BELOW_EXPECTED = "their_agreed_below_expected"
    THEY_PAID_SHORT = "they_paid_short"
    THEY_PAID_OVER = "they_paid_over"


@dataclass(frozen=True, slots=True)
class StatementLine:
    reinsurer_name: str
    currency: str
    reference: str | None = None
    their_agreed: Decimal | None = None
    their_paid: Decimal | None = None


@dataclass(frozen=True, slots=True)
class MatchedRecoverable:
    reinsurer_name: str
    currency: str
    expected: Decimal
    our_agreed: Decimal | None
    our_collected: Decimal


@dataclass(frozen=True, slots=True)
class StatementFinding:
    kind: StatementFindingKind
    text: str
    ours: Decimal | None
    theirs: Decimal | None

    @property
    def gap(self) -> Decimal | None:
        if self.ours is None or self.theirs is None:
            return None
        return abs(self.ours - self.theirs)

    @property
    def is_discrepancy(self) -> bool:
        return self.kind not in (StatementFindingKind.CLEAN,)


def _material(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) > _MATERIALITY


def reconcile_statement_line(
    their: StatementLine, ours: MatchedRecoverable | None
) -> list[StatementFinding]:
    if ours is None:
        return [
            StatementFinding(
                kind=StatementFindingKind.NO_MATCH,
                text=(
                    f"{their.reinsurer_name}: no recoverable matches this statement line"
                    + (f" (reference {their.reference})" if their.reference else "")
                ),
                ours=None,
                theirs=their.their_agreed if their.their_agreed is not None else their.their_paid,
            )
        ]

    findings: list[StatementFinding] = []

    if their.currency.upper() != ours.currency.upper():
        findings.append(
            StatementFinding(
                kind=StatementFindingKind.CURRENCY_MISMATCH,
                text=f"statement is in {their.currency}, the recoverable is in {ours.currency}",
                ours=None,
                theirs=None,
            )
        )
        return findings

    if their.their_agreed is not None:
        if ours.our_agreed is not None and _material(their.their_agreed, ours.our_agreed):
            below = their.their_agreed < ours.our_agreed
            findings.append(
                StatementFinding(
                    kind=(
                        StatementFindingKind.THEIR_AGREED_BELOW_OURS
                        if below
                        else StatementFindingKind.THEIR_AGREED_ABOVE_OURS
                    ),
                    text=(
                        f"reinsurer agreed {their.their_agreed}, we recorded {ours.our_agreed} "
                        f"({'their' if below else 'our'} figure is lower)"
                    ),
                    ours=ours.our_agreed,
                    theirs=their.their_agreed,
                )
            )
        elif their.their_agreed < ours.expected - _MATERIALITY:
            findings.append(
                StatementFinding(
                    kind=StatementFindingKind.THEIR_AGREED_BELOW_EXPECTED,
                    text=(
                        f"reinsurer agreed {their.their_agreed}, below the calculated "
                        f"expected {ours.expected}"
                    ),
                    ours=ours.expected,
                    theirs=their.their_agreed,
                )
            )

    if their.their_paid is not None and _material(their.their_paid, ours.our_collected):
        short = their.their_paid < ours.our_collected
        findings.append(
            StatementFinding(
                kind=(
                    StatementFindingKind.THEY_PAID_SHORT
                    if short
                    else StatementFindingKind.THEY_PAID_OVER
                ),
                text=(
                    f"reinsurer shows paid {their.their_paid}, we recorded collected "
                    f"{ours.our_collected}"
                ),
                ours=ours.our_collected,
                theirs=their.their_paid,
            )
        )

    if not findings:
        return [
            StatementFinding(
                kind=StatementFindingKind.CLEAN,
                text="the reinsurer's figures match what we hold",
                ours=ours.our_agreed if ours.our_agreed is not None else ours.expected,
                theirs=their.their_agreed if their.their_agreed is not None else their.their_paid,
            )
        ]
    # worst gap first
    findings.sort(key=lambda f: f.gap or Decimal("0"), reverse=True)
    return findings
