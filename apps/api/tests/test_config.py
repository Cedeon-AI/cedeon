"""The settings validator does two deployment-critical jobs: normalise a managed
platform's injected values, and refuse an unsafe production config (ADR-0027/0028)."""

import pytest

from app.core.config import Settings

_PROD = {
    "env": "production",
    "session_secret": "s" * 40,
    "signup_mode": "code",
    "database_url": "postgresql+asyncpg://u:p@db.internal/cedeon",
}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # conftest exports CEDEON_* for the test database; drop the ones these cases assert on.
    for key in (
        "CEDEON_ENV",
        "CEDEON_SESSION_SECRET",
        "CEDEON_DATABASE_URL",
        "CEDEON_DATABASE_URL_SYNC",
        "CEDEON_SIGNUP_MODE",
        "CEDEON_PUBLIC_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


class TestUrlNormalisation:
    def test_bare_postgres_url_gets_the_drivers(self) -> None:
        s = _settings(database_url="postgres://u:p@host:5432/db")
        assert s.database_url == "postgresql+asyncpg://u:p@host:5432/db"
        assert s.database_url_sync == "postgresql+psycopg://u:p@host:5432/db"

    def test_explicit_sync_url_is_left_alone(self) -> None:
        s = _settings(
            database_url="postgresql+asyncpg://u:p@h/db",
            database_url_sync="postgresql+psycopg://u:p@h/db",
        )
        assert s.database_url_sync == "postgresql+psycopg://u:p@h/db"

    def test_scheme_less_public_base_url_becomes_https(self) -> None:
        assert _settings(public_base_url="cedeon-web.onrender.com").public_base_url == (
            "https://cedeon-web.onrender.com"
        )
        assert _settings(public_base_url="http://localhost:3000").public_base_url == (
            "http://localhost:3000"
        )


class TestProductionGuards:
    def test_open_signup_is_refused_in_production(self) -> None:
        with pytest.raises(ValueError, match="SIGNUP_MODE"):
            _settings(**{**_PROD, "signup_mode": "open"})

    def test_dev_session_secret_is_refused_in_production(self) -> None:
        with pytest.raises(ValueError, match="SESSION_SECRET"):
            _settings(
                env="production",
                signup_mode="code",
                database_url="postgresql+asyncpg://u:p@db.internal/cedeon",
            )

    def test_localhost_db_is_refused_in_production(self) -> None:
        with pytest.raises(ValueError, match="localhost"):
            _settings(**{**_PROD, "database_url": "postgresql+asyncpg://u:p@localhost/db"})

    def test_a_sound_production_config_is_accepted(self) -> None:
        assert _settings(**_PROD).is_production
