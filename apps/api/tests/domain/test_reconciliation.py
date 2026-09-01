"""Reconciliation is deterministic — code finds the mismatch, a human resolves it."""

from __future__ import annotations

from decimal import Decimal

from app.domain.recoveries.collection import RecoverableStatus
from app.domain.recoveries.reconciliation import (
    ReconcileKind,
    RecoverableAmounts,
    reconcile,
)

D = Decimal


def _amounts(**kw: object) -> RecoverableAmounts:
    base = {
        "status": RecoverableStatus.AGREED,
        "currency": "USD",
        "expected": D("1000000.00"),
        "agreed": None,
        "billed": None,
        "collected": D("0.00"),
    }
    base.update(kw)
    return RecoverableAmounts(**base)  # type: ignore[arg-type]


def _kinds(r: RecoverableAmounts) -> set[ReconcileKind]:
    return {f.kind for f in reconcile(r)}


class TestReconcile:
    def test_a_clean_leg_has_no_findings(self) -> None:
        r = _amounts(agreed=D("1000000.00"), billed=D("1000000.00"), collected=D("1000000.00"))
        assert reconcile(r) == []

    def test_rounding_is_not_an_exception(self) -> None:
        assert reconcile(_amounts(agreed=D("999999.50"))) == []

    def test_agreed_below_expected(self) -> None:
        r = _amounts(agreed=D("800000.00"))
        findings = reconcile(r)
        assert findings[0].kind is ReconcileKind.AGREED_BELOW_EXPECTED
        assert findings[0].gap == D("200000.00")
        assert "200,000.00 short" in findings[0].text

    def test_agreed_above_expected(self) -> None:
        assert _kinds(_amounts(agreed=D("1100000.00"))) == {ReconcileKind.AGREED_ABOVE_EXPECTED}

    def test_billed_differs_from_agreed(self) -> None:
        assert ReconcileKind.BILLED_NOT_AGREED in _kinds(
            _amounts(agreed=D("1000000.00"), billed=D("950000.00"))
        )

    def test_billed_without_an_agreed_figure(self) -> None:
        assert _kinds(_amounts(billed=D("500000.00"))) == {ReconcileKind.BILLED_WITHOUT_AGREEMENT}

    def test_collected_more_than_billed(self) -> None:
        assert ReconcileKind.COLLECTED_OVER_BILLED in _kinds(
            _amounts(agreed=D("1000000.00"), billed=D("1000000.00"), collected=D("1200000.00"))
        )

    def test_marked_collected_but_short(self) -> None:
        r = _amounts(
            status=RecoverableStatus.COLLECTED,
            agreed=D("1000000.00"),
            billed=D("1000000.00"),
            collected=D("900000.00"),
        )
        assert ReconcileKind.COLLECTED_SHORT in _kinds(r)

    def test_a_short_collection_mid_flow_is_not_flagged(self) -> None:
        # still BILLED, partial payment expected — not an exception yet
        r = _amounts(
            status=RecoverableStatus.BILLED,
            agreed=D("1000000.00"),
            billed=D("1000000.00"),
            collected=D("400000.00"),
        )
        assert ReconcileKind.COLLECTED_SHORT not in _kinds(r)

    def test_written_off_legs_are_not_reconciled(self) -> None:
        r = _amounts(status=RecoverableStatus.WRITTEN_OFF, agreed=D("1.00"))
        assert reconcile(r) == []

    def test_findings_come_back_worst_gap_first(self) -> None:
        r = _amounts(agreed=D("700000.00"), billed=D("690000.00"), collected=D("0.00"))
        findings = reconcile(r)
        assert [f.gap for f in findings] == sorted((f.gap for f in findings), reverse=True)
