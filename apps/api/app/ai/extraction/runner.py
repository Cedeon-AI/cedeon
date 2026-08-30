"""Runs the extraction call and packages the result + telemetry."""

from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic_ai import Agent

from app.ai.extraction.schema import TreatyExtraction
from app.ai.models import build_model
from app.ai.prompts import (
    TREATY_EXTRACTION_INSTRUCTIONS,
    TREATY_EXTRACTION_PROMPT_VERSION,
    TREATY_EXTRACTION_USER_TEMPLATE,
)
from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)

# Guard: keep the document well under the model context window.
_MAX_DOCUMENT_CHARS = 400_000


@dataclass(slots=True)
class ExtractionResult:
    extraction: TreatyExtraction
    provider: str
    model: str
    prompt_version: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: Decimal | None
    latency_ms: int
    output: dict[str, Any]


async def extract_treaty_terms(
    *,
    document_blocks: list[str],
    settings: Settings,
    model_spec: str | None = None,
) -> ExtractionResult:
    spec = model_spec or settings.treaty_extraction_model
    provider = spec.split(":", 1)[0]
    model = build_model(spec, settings)

    agent: Agent[None, TreatyExtraction] = Agent(
        model,
        output_type=TreatyExtraction,
        instructions=TREATY_EXTRACTION_INSTRUCTIONS,
        name="treaty_extraction",
    )

    document = "\n\n".join(document_blocks)[:_MAX_DOCUMENT_CHARS]
    prompt = TREATY_EXTRACTION_USER_TEMPLATE.format(document=document)

    started = time.monotonic()
    run = await agent.run(prompt)
    latency_ms = int((time.monotonic() - started) * 1000)

    extraction = run.output.downgrade_uncited_material_terms()
    usage = run.usage
    cost = getattr(usage, "cost", None)

    log.info(
        "ai.treaty_extraction",
        model=spec,
        latency_ms=latency_ms,
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        terms=len(extraction.terms),
        participations=len(extraction.participations),
        suspected_injection=extraction.suspected_prompt_injection,
    )

    return ExtractionResult(
        extraction=extraction,
        provider=provider,
        model=spec,
        prompt_version=TREATY_EXTRACTION_PROMPT_VERSION,
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        cost_usd=Decimal(str(cost)) if cost is not None else None,
        latency_ms=latency_ms,
        output=extraction.model_dump(mode="json"),
    )
