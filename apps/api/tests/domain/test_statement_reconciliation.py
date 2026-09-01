"""Reinsurer-statement reconciliation is deterministic — code finds the gap."""

from __future__ import annotations

from decimal import Decimal

from app.domain.recoveries.statement_reconciliation import (
    MatchedRecoverable,
    StatementFindingKind,
    StatementLine,
    reconcile_statement_line,
)

D = Decimal


def _ours(**kw: object) -> MatchedRecoverable:
    base: dict[str, object] = {
        "reinsurer_name": "Reinsurer Alpha",
        "currency": "USD",
        "expected": D("4350000.00"),
        "our_agreed": D("4350000.00"),
        "our_collected": D("0.00"),
    }
    base.update(kw)
    return MatchedRecoverable(**base)  # type: ignore[arg-type]


def _kinds(findings: list) -> set[StatementFindingKind]:
    return {f.kind for f in findings}


def test_a_clean_line() -> None:
    line = StatementLine("Reinsurer Alpha", "USD", their_agreed=D("4350000.00"))
    findings = reconcile_statement_line(line, _ours())
    assert _kinds(findings) == {StatementFindingKind.CLEAN}


def test_no_match_when_there_is_no_recoverable() -> None:
    line = StatementLine("Reinsurer Zeta", "USD", their_agreed=D("100"))
    findings = reconcile_statement_line(line, None)
    assert _kinds(findings) == {StatementFindingKind.NO_MATCH}


def test_their_agreed_below_ours() -> None:
    line = StatementLine("Reinsurer Alpha", "USD", their_agreed=D("4000000.00"))
    findings = reconcile_statement_line(line, _ours())
    assert findings[0].kind is StatementFindingKind.THEIR_AGREED_BELOW_OURS
    assert findings[0].gap == D("350000.00")


def test_their_agreed_below_expected_when_we_have_not_agreed_yet() -> None:
    line = StatementLine("Reinsurer Alpha", "USD", their_agreed=D("4000000.00"))
    findings = reconcile_statement_line(line, _ours(our_agreed=None))
    assert findings[0].kind is StatementFindingKind.THEIR_AGREED_BELOW_EXPECTED


def test_they_paid_short() -> None:
    line = StatementLine("Reinsurer Alpha", "USD", their_paid=D("3000000.00"))
    findings = reconcile_statement_line(line, _ours(our_collected=D("4350000.00")))
    assert findings[0].kind is StatementFindingKind.THEY_PAID_SHORT
    assert findings[0].gap == D("1350000.00")


def test_they_paid_over() -> None:
    line = StatementLine("Reinsurer Alpha", "USD", their_paid=D("5000000.00"))
    findings = reconcile_statement_line(line, _ours(our_collected=D("4350000.00")))
    assert findings[0].kind is StatementFindingKind.THEY_PAID_OVER


def test_currency_mismatch_short_circuits() -> None:
    line = StatementLine("Reinsurer Alpha", "EUR", their_agreed=D("1"))
    findings = reconcile_statement_line(line, _ours())
    assert _kinds(findings) == {StatementFindingKind.CURRENCY_MISMATCH}


def test_rounding_is_not_a_discrepancy() -> None:
    line = StatementLine("Reinsurer Alpha", "USD", their_agreed=D("4350000.75"))
    findings = reconcile_statement_line(line, _ours())
    assert _kinds(findings) == {StatementFindingKind.CLEAN}


def test_both_an_agreed_and_a_paid_discrepancy_sort_worst_first() -> None:
    line = StatementLine(
        "Reinsurer Alpha", "USD", their_agreed=D("4200000.00"), their_paid=D("1000000.00")
    )
    findings = reconcile_statement_line(
        line, _ours(our_agreed=D("4350000.00"), our_collected=D("4350000.00"))
    )
    assert findings[0].kind is StatementFindingKind.THEY_PAID_SHORT  # 3.35M gap
    assert findings[1].kind is StatementFindingKind.THEIR_AGREED_BELOW_OURS  # 150k gap
