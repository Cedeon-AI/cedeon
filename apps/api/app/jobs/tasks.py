"""Job definitions.

Phase 1 ships only ``ping`` to prove the API → queue → worker path. Real jobs
(document parse, chunk, embed, extract, investigate) arrive from Phase 2.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.jobs.app import procrastinate_app

log = get_logger(__name__)


@procrastinate_app.task(name="ping")
async def ping(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    log.info("job.ping", payload=payload or {})
    return {"pong": True, "echo": payload or {}}
