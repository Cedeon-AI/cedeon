"""Run the notice drafter: one typed structured-output call, no tools, no loop."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic_ai import Agent

from app.ai.models import build_model
from app.ai.notice.schema import NoticeDraft
from app.ai.prompts import (
    NOTICE_DRAFTER_INSTRUCTIONS,
    NOTICE_DRAFTER_PROMPT_VERSION,
    NOTICE_DRAFTER_USER_TEMPLATE,
)
from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.recoveries import NoticeContext

log = get_logger(__name__)


@dataclass(slots=True)
class NoticeDraftResult:
    draft: NoticeDraft
    provider: str
    model: str
    prompt_version: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: Decimal | None
    latency_ms: int
    output: dict[str, Any]


async def draft_notice(
    *,
    notice_context: NoticeContext,
    settings: Settings,
    model_spec: str | None = None,
) -> NoticeDraftResult:
    spec = model_spec or settings.notice_drafter_model
    provider = spec.split(":", 1)[0]

    agent: Agent[None, NoticeDraft] = Agent(
        build_model(spec, settings),
        output_type=NoticeDraft,
        instructions=NOTICE_DRAFTER_INSTRUCTIONS,
        name="notice_drafter",
    )
    prompt = NOTICE_DRAFTER_USER_TEMPLATE.format(facts=notice_context.to_prompt())

    started = time.monotonic()
    run = await asyncio.wait_for(agent.run(prompt), timeout=settings.notice_drafter_timeout_seconds)
    latency_ms = int((time.monotonic() - started) * 1000)

    draft = run.output
    usage = run.usage
    cost = getattr(usage, "cost", None)

    log.info(
        "ai.notice_draft",
        model=spec,
        latency_ms=latency_ms,
        kind=notice_context.kind.value,
        used_only_provided_facts=draft.used_only_provided_facts,
    )
    return NoticeDraftResult(
        draft=draft,
        provider=provider,
        model=spec,
        prompt_version=NOTICE_DRAFTER_PROMPT_VERSION,
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        cost_usd=Decimal(str(cost)) if cost is not None else None,
        latency_ms=latency_ms,
        output=draft.model_dump(mode="json"),
    )
