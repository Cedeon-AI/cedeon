"""Shared test fixtures.

Pure-domain tests (``tests/domain``) need nothing external. Tests that request
``client`` / ``session`` pull in a session-wide PostgreSQL container (pgvector
image), migrated once with Alembic and truncated between tests.
"""

from __future__ import annotations

import os

# Disable the Ryuk reaper: it bind-mounts the docker socket, which Docker Desktop's
# per-user socket path does not support. Our fixtures stop containers explicitly.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from testcontainers.community.postgres import PostgresContainer

API_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def _database() -> Iterator[dict[str, str]]:
    with PostgresContainer(
        "pgvector/pgvector:pg16", username="cedeon", password="cedeon", dbname="cedeon"
    ) as pg:
        host = pg.get_container_host_ip()
        port = pg.get_exposed_port(5432)
        async_url = f"postgresql+asyncpg://cedeon:cedeon@{host}:{port}/cedeon"
        sync_url = f"postgresql+psycopg://cedeon:cedeon@{host}:{port}/cedeon"

        os.environ["CEDEON_ENV"] = "test"
        os.environ["CEDEON_SESSION_SECRET"] = "test-secret-" + "x" * 48
        os.environ["CEDEON_DATABASE_URL"] = async_url
        os.environ["CEDEON_DATABASE_URL_SYNC"] = sync_url
        os.environ["CEDEON_LOG_LEVEL"] = "WARNING"

        from app.core.config import get_settings

        get_settings.cache_clear()

        cfg = Config()
        cfg.set_main_option("script_location", str(API_DIR / "app" / "db" / "migrations"))
        cfg.set_main_option("sqlalchemy.url", sync_url)
        command.upgrade(cfg, "head")

        yield {"async_url": async_url, "sync_url": sync_url}


@pytest_asyncio.fixture(scope="session")
async def _engine(_database: dict[str, str]) -> AsyncIterator[None]:
    from app.db.session import dispose_engine, init_engine

    init_engine(_database["async_url"])
    yield
    await dispose_engine()


@pytest_asyncio.fixture
async def db(_engine: None) -> AsyncIterator[None]:
    """Requested (directly or transitively) by every test that touches Postgres.
    Truncates all tables on teardown for isolation."""
    from app.db.models import Base
    from app.db.session import get_engine

    yield
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with get_engine().begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def object_store(tmp_path: Path):
    from app.storage.filesystem import FilesystemObjectStore

    return FilesystemObjectStore(tmp_path / "objectstore")


@pytest.fixture
def parse_calls() -> list[tuple[object, object]]:
    return []


@pytest.fixture
def extract_calls() -> list[tuple[object, object]]:
    return []


@pytest.fixture
def investigate_calls() -> list[tuple[object, object, object]]:
    return []


@pytest.fixture
def app(db: None, object_store, parse_calls, extract_calls, investigate_calls):
    from app.api.dependencies.context import (
        get_extract_enqueuer,
        get_investigate_enqueuer,
        get_object_store,
        get_parse_enqueuer,
    )
    from app.main import create_app

    application = create_app()
    application.dependency_overrides[get_object_store] = lambda: object_store

    async def _record_parse(organization_id: object, document_id: object) -> None:
        parse_calls.append((organization_id, document_id))

    async def _record_extract(organization_id: object, version_id: object) -> None:
        extract_calls.append((organization_id, version_id))

    async def _record_investigate(
        organization_id: object, candidate_id: object, actor_id: object = None
    ) -> None:
        investigate_calls.append((organization_id, candidate_id, actor_id))

    application.dependency_overrides[get_parse_enqueuer] = lambda: _record_parse
    application.dependency_overrides[get_extract_enqueuer] = lambda: _record_extract
    application.dependency_overrides[get_investigate_enqueuer] = lambda: _record_investigate
    return application


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def client_factory(app):
    """Make independent clients (separate cookie jars) against the same app."""
    created: list[AsyncClient] = []

    async def _make() -> AsyncClient:
        ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
        created.append(ac)
        return ac

    yield _make
    for ac in created:
        await ac.aclose()


@pytest_asyncio.fixture
async def session(db: None) -> AsyncIterator[object]:
    from app.db.session import get_sessionmaker

    async with get_sessionmaker()() as s:
        yield s
