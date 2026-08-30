"""Async engine and session management.

The engine is created lazily and can be re-pointed (tests, scripts) via
:func:`init_engine`. Routes get a session through the FastAPI dependency in
``app.api.dependencies.context``; the dependency does not auto-commit — services
commit explicitly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine(url: str | None = None, *, echo: bool = False) -> AsyncEngine:
    global _engine, _sessionmaker
    resolved = url or get_settings().database_url
    _engine = create_async_engine(resolved, echo=echo, pool_pre_ping=True, future=True)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, autoflush=False)
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        init_engine()
    assert _engine is not None
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        init_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def session_scope() -> AsyncIterator[AsyncSession]:
    """Yield a session, rolling back on error. Commit is the caller's responsibility."""
    async with get_sessionmaker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
