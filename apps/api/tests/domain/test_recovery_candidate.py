"""The recovery-candidate input hash — how staleness is detected."""

from __future__ import annotations

from decimal import Decimal

from app.domain.recoveries import RecoveryCandidateStatus, recovery_input_hash

_BASE = {
    "engine_version": "1.0.0",
    "treaty_version_id": "11111111-1111-1111-1111-111111111111",
    "treaty_layer_id": "22222222-2222-2222-2222-222222222222",
    "loss_event_id": "33333333-3333-3333-3333-333333333333",
    "currency": "USD",
    "gross_loss": Decimal("58700000.00"),
    "attachment": Decimal("50000000.00"),
    "limit": Decimal("20000000.00"),
    "participations": [("alpha", Decimal("0.5")), ("beta", Decimal("0.3"))],
}


def _hash(**overrides: object) -> str:
    return recovery_input_hash(**{**_BASE, **overrides})  # type: ignore[arg-type]


def test_same_inputs_hash_identically() -> None:
    assert _hash() == _hash()


def test_hash_is_insensitive_to_decimal_scale() -> None:
    assert _hash(gross_loss=Decimal("58700000")) == _hash(gross_loss=Decimal("58700000.00"))
    assert _hash(attachment=Decimal("5E+7")) == _hash(attachment=Decimal("50000000.00"))


def test_hash_is_insensitive_to_participation_order() -> None:
    reordered = [("beta", Decimal("0.3")), ("alpha", Decimal("0.5"))]
    assert _hash(participations=reordered) == _hash()


def test_hash_changes_when_any_input_changes() -> None:
    base = _hash()
    assert _hash(gross_loss=Decimal("58700000.01")) != base
    assert _hash(attachment=Decimal("40000000.00")) != base
    assert _hash(limit=Decimal("25000000.00")) != base
    assert _hash(currency="EUR") != base
    assert _hash(engine_version="1.0.1") != base
    assert _hash(loss_event_id="44444444-4444-4444-4444-444444444444") != base
    assert _hash(participations=[("alpha", Decimal("0.6")), ("beta", Decimal("0.3"))]) != base
    assert _hash(participations=[("alpha", Decimal("0.5")), ("gamma", Decimal("0.3"))]) != base


def test_hash_is_hex_sha256() -> None:
    value = _hash()
    assert len(value) == 64
    int(value, 16)  # raises if not hex


def test_status_is_open_flags() -> None:
    assert RecoveryCandidateStatus.NEEDS_REVIEW.is_open
    assert RecoveryCandidateStatus.IN_REVIEW.is_open
    assert not RecoveryCandidateStatus.CONFIRMED.is_open
    assert not RecoveryCandidateStatus.REJECTED.is_open
