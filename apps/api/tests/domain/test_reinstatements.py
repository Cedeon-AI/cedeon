"""Reinstatement premium is deterministic arithmetic over validated terms."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.recoveries.reinstatements import (
    ReinstatementBasis,
    compute_reinstatement_premium,
)

D = Decimal
LIMIT = D("20000000")
DEPOSIT = D("2000000")


def _run(**kw: object) -> object:
    base: dict[str, object] = {
        "layer_limit": LIMIT,
        "deposit_premium": DEPOSIT,
        "rates": [D("1"), D("1")],
        "basis": ReinstatementBasis.FLAT,
        "prior_erosion": D("0"),
        "this_loss_to_layer": D("0"),
    }
    base.update(kw)
    return compute_reinstatement_premium(**base)  # type: ignore[arg-type]


class TestFlat:
    def test_a_full_limit_loss_triggers_one_full_reinstatement(self) -> None:
        r = _run(this_loss_to_layer=LIMIT)
        # 20M reinstated / 20M x 2M deposit x 100% x 1 = 2,000,000
        assert r.premium_due == D("2000000.00")
        assert [c.order for c in r.charges] == [1]
        assert r.charges[0].amount_reinstated == D("20000000.00")
        assert not r.cover_exhausted

    def test_a_partial_loss_charges_pro_rata_as_to_amount(self) -> None:
        r = _run(this_loss_to_layer=D("8700000"))
        # 8.7M / 20M x 2M = 870,000
        assert r.premium_due == D("870000.00")

    def test_prior_erosion_this_period_is_not_recharged(self) -> None:
        # 12M already used; this loss adds a full 20M → total 32M
        r = _run(prior_erosion=D("12000000"), this_loss_to_layer=LIMIT)
        # reinstatement 1 band [0, 20M]: this loss reinstates 20M - 12M = 8M
        # reinstatement 2 band [20M, 40M]: this loss reinstates 32M - 20M = 12M
        assert [c.amount_reinstated for c in r.charges] == [D("8000000.00"), D("12000000.00")]
        assert r.premium_due == D("2000000.00")  # (8 + 12)/20 x 2M

    def test_a_loss_wholly_inside_the_second_band(self) -> None:
        r = _run(prior_erosion=LIMIT, this_loss_to_layer=D("10000000"))
        assert [c.order for c in r.charges] == [2]
        assert r.charges[0].amount_reinstated == D("10000000.00")
        assert r.premium_due == D("1000000.00")

    def test_cover_exhausted_when_every_reinstatement_is_used(self) -> None:
        r = _run(prior_erosion=D("40000000"), this_loss_to_layer=LIMIT)
        assert r.cover_exhausted  # 60M used of 60M available (limit + 2 reinstatements)
        assert r.premium_due == D("0.00")  # nothing left to reinstate

    def test_no_loss_means_no_premium(self) -> None:
        r = _run(this_loss_to_layer=D("0"))
        assert r.premium_due == D("0.00")
        assert r.charges == []

    def test_a_free_first_reinstatement(self) -> None:
        r = _run(rates=[D("0"), D("1")], this_loss_to_layer=LIMIT)
        assert r.premium_due == D("0.00")
        assert r.charges[0].rate == D("0")


class TestProRataTime:
    def test_time_factor_scales_the_premium(self) -> None:
        r = _run(
            basis=ReinstatementBasis.PRO_RATA_TIME,
            this_loss_to_layer=LIMIT,
            unexpired_fraction=D("0.25"),
        )
        assert r.premium_due == D("500000.00")  # 2M x 100% x 0.25

    def test_time_factor_is_clamped_to_zero_one(self) -> None:
        over = _run(
            basis=ReinstatementBasis.PRO_RATA_TIME,
            this_loss_to_layer=LIMIT,
            unexpired_fraction=D("1.5"),
        )
        assert over.premium_due == D("2000000.00")
        under = _run(
            basis=ReinstatementBasis.PRO_RATA_TIME,
            this_loss_to_layer=LIMIT,
            unexpired_fraction=D("-0.2"),
        )
        assert under.premium_due == D("0.00")


class TestGuards:
    def test_zero_limit_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="limit"):
            _run(layer_limit=D("0"))

    def test_negative_deposit_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="deposit"):
            _run(deposit_premium=D("-1"))

    def test_no_reinstatements_means_no_charges_and_exhausted_on_a_full_loss(self) -> None:
        r = _run(rates=[], this_loss_to_layer=LIMIT)
        assert r.premium_due == D("0.00")
        assert r.charges == []
        assert r.cover_exhausted
