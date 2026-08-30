"""Liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.api.dependencies.context import DbSession

router = APIRouter(tags=["health"])


@router.get("/healthz", summary="Liveness probe", operation_id="healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/readyz", summary="Readiness probe (checks the database)", operation_id="readyz")
async def readyz(session: DbSession) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready"}
