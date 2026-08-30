"""Liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.api.dependencies.context import DbSession, ObjectStoreDep
from app.core.logging import get_logger

router = APIRouter(tags=["health"])
log = get_logger(__name__)


@router.get("/healthz", summary="Liveness probe", operation_id="healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get(
    "/readyz",
    summary="Readiness probe (database + object store)",
    operation_id="readyz",
)
async def readyz(session: DbSession, store: ObjectStoreDep) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    # A cheap reachability probe: a missing key returns False; an unreachable
    # backend raises, which the handler turns into a 500 → not ready.
    await store.exists("__readyz_probe__")
    return {"status": "ready"}
