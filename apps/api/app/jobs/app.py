"""The Procrastinate application.

Worker:  ``procrastinate --app=app.jobs.app.procrastinate_app worker``
Schema:  ``procrastinate --app=app.jobs.app.procrastinate_app schema --apply``
"""

from __future__ import annotations

from procrastinate import App, PsycopgConnector

from app.core.config import get_settings


def _conninfo() -> str:
    # Procrastinate wants a libpq connection string, not a SQLAlchemy URL.
    return (
        get_settings()
        .database_url_sync.replace("postgresql+psycopg://", "postgresql://")
        .replace("postgresql+psycopg2://", "postgresql://")
    )


procrastinate_app = App(
    connector=PsycopgConnector(conninfo=_conninfo()),
    import_paths=["app.jobs.tasks"],
)
