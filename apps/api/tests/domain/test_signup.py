import datetime as dt

from app.domain.organizations import is_redeemable

_NOW = dt.datetime(2026, 9, 1, tzinfo=dt.UTC)


def _kw(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "revoked_at": None,
        "expires_at": None,
        "max_uses": 1,
        "redeemed_count": 0,
        "now": _NOW,
    }
    base.update(overrides)
    return base


def test_fresh_code_is_redeemable() -> None:
    assert is_redeemable(**_kw()) is True  # type: ignore[arg-type]


def test_revoked_code_is_not_redeemable() -> None:
    assert is_redeemable(**_kw(revoked_at=_NOW - dt.timedelta(days=1))) is False  # type: ignore[arg-type]


def test_expired_code_is_not_redeemable() -> None:
    assert is_redeemable(**_kw(expires_at=_NOW - dt.timedelta(seconds=1))) is False  # type: ignore[arg-type]
    assert is_redeemable(**_kw(expires_at=_NOW + dt.timedelta(days=1))) is True  # type: ignore[arg-type]


def test_exhausted_uses_is_not_redeemable() -> None:
    assert is_redeemable(**_kw(max_uses=1, redeemed_count=1)) is False  # type: ignore[arg-type]
    assert is_redeemable(**_kw(max_uses=3, redeemed_count=2)) is True  # type: ignore[arg-type]
