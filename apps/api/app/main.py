"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app import __version__
from app.api.errors import register_error_handlers
from app.api.middleware import CorrelationIdMiddleware
from app.api.routes import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.core.telemetry import configure_telemetry, instrument_fastapi
from app.db.session import dispose_engine, init_engine

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    init_engine()
    log.info("api.startup", env=settings.env, version=__version__)
    try:
        yield
    finally:
        await dispose_engine()
        log.info("api.shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)
    configure_telemetry(settings)

    app = FastAPI(
        title="Cedeon API",
        version=__version__,
        summary="Reinsurance intelligence from contract to recovery.",
        lifespan=lifespan,
        redoc_url=None,
    )

    app.add_middleware(CorrelationIdMiddleware)
    if settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_error_handlers(app)
    instrument_fastapi(app)
    app.include_router(api_router)
    return app


app = create_app()
