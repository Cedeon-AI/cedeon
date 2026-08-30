"""Runs the Recovery Investigator agent: bounded, read-only, typed tools only."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.usage import UsageLimits

from app.ai.investigator import tools as t
from app.ai.investigator.schema import RecoveryInvestigation
from app.ai.models import build_model
from app.ai.prompts import (
    RECOVERY_INVESTIGATOR_INSTRUCTIONS,
    RECOVERY_INVESTIGATOR_PROMPT_VERSION,
    RECOVERY_INVESTIGATOR_USER_TEMPLATE,
)
from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.ai import ToolCallStatus

log = get_logger(__name__)


@dataclass(slots=True)
class ToolCallLog:
    ordinal: int
    tool_name: str
    arguments: dict[str, Any]
    result_summary: dict[str, Any]
    status: ToolCallStatus


@dataclass(slots=True)
class InvestigationResult:
    investigation: RecoveryInvestigation
    provider: str
    model: str
    prompt_version: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: Decimal | None
    latency_ms: int
    tool_calls: list[ToolCallLog] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)


def _build_agent(
    model_spec: str, settings: Settings
) -> Agent[t.InvestigatorDeps, RecoveryInvestigation]:
    agent: Agent[t.InvestigatorDeps, RecoveryInvestigation] = Agent(
        build_model(model_spec, settings),
        deps_type=t.InvestigatorDeps,
        output_type=RecoveryInvestigation,
        instructions=RECOVERY_INVESTIGATOR_INSTRUCTIONS,
        name="recovery_investigator",
    )

    @agent.tool
    async def get_recovery_calculation(ctx: RunContext[t.InvestigatorDeps]) -> Any:
        """The deterministic recovery figures — authoritative, never to be recomputed."""
        return await t.get_recovery_calculation(ctx.deps)

    @agent.tool
    async def get_validated_terms(ctx: RunContext[t.InvestigatorDeps]) -> Any:
        """Human-validated treaty terms and the executable layer (attachment / limit / currency)."""
        return await t.get_validated_terms(ctx.deps)

    @agent.tool
    async def get_participants(ctx: RunContext[t.InvestigatorDeps]) -> Any:
        """The reinsurers on this treaty version and their placed share percentages."""
        return await t.get_participants(ctx.deps)

    @agent.tool
    async def get_loss_event(ctx: RunContext[t.InvestigatorDeps]) -> Any:
        """The loss event: name, catastrophe code, date range, per-currency claim totals."""
        return await t.get_loss_event(ctx.deps)

    @agent.tool
    async def list_underlying_losses(ctx: RunContext[t.InvestigatorDeps], limit: int = 50) -> Any:
        """The underlying claim schedule (claim id, date, cause, location, incurred)."""
        return await t.list_underlying_losses(ctx.deps, limit=limit)

    @agent.tool
    async def search_treaty(ctx: RunContext[t.InvestigatorDeps], query: str, k: int = 5) -> Any:
        """Retrieve the treaty passages most relevant to a query (clause-aware chunks, ranked)."""
        return await t.search_treaty(ctx.deps, query=query, k=k)

    return agent


async def run_investigator(
    *,
    deps: t.InvestigatorDeps,
    prompt_context: dict[str, Any],
    settings: Settings,
    model_spec: str | None = None,
) -> InvestigationResult:
    spec = model_spec or settings.recovery_investigator_model
    provider = spec.split(":", 1)[0]
    agent = _build_agent(spec, settings)

    prompt = RECOVERY_INVESTIGATOR_USER_TEMPLATE.format(**prompt_context)
    limits = UsageLimits(
        request_limit=settings.investigator_request_limit,
        tool_calls_limit=settings.investigator_tool_calls_limit,
        total_tokens_limit=settings.investigator_total_tokens_limit,
    )

    started = time.monotonic()
    run = await asyncio.wait_for(
        agent.run(prompt, deps=deps, usage_limits=limits),
        timeout=settings.investigator_timeout_seconds,
    )
    latency_ms = int((time.monotonic() - started) * 1000)

    investigation = run.output.grounded()
    usage = run.usage
    cost = getattr(usage, "cost", None)
    tool_calls = _tool_call_log(run.all_messages())

    log.info(
        "ai.recovery_investigation",
        model=spec,
        latency_ms=latency_ms,
        tool_calls=len(tool_calls),
        findings=len(investigation.findings),
        applicability=investigation.applicability_assessment.value,
        suspected_injection=investigation.suspected_prompt_injection,
    )

    return InvestigationResult(
        investigation=investigation,
        provider=provider,
        model=spec,
        prompt_version=RECOVERY_INVESTIGATOR_PROMPT_VERSION,
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        cost_usd=Decimal(str(cost)) if cost is not None else None,
        latency_ms=latency_ms,
        tool_calls=tool_calls,
        output=investigation.model_dump(mode="json"),
    )


def _tool_call_log(messages: list[Any]) -> list[ToolCallLog]:
    """Pair ToolCallPart (in responses) with ToolReturnPart (in the next request)."""
    calls: dict[str, ToolCallLog] = {}
    ordinal = 0
    for message in messages:
        for part in getattr(message, "parts", []):
            if isinstance(message, ModelResponse) and isinstance(part, ToolCallPart):
                ordinal += 1
                calls[part.tool_call_id] = ToolCallLog(
                    ordinal=ordinal,
                    tool_name=part.tool_name,
                    arguments=_as_dict(part.args),
                    result_summary={},
                    status=ToolCallStatus.OK,
                )
            elif (
                isinstance(message, ModelRequest)
                and isinstance(part, ToolReturnPart)
                and part.tool_call_id in calls
            ):
                entry = calls[part.tool_call_id]
                entry.result_summary = _summarize(part.content)
                if isinstance(part.content, dict) and "error" in part.content:
                    entry.status = ToolCallStatus.ERROR
    return sorted(calls.values(), key=lambda c: c.ordinal)


def _as_dict(args: Any) -> dict[str, Any]:
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        import json

        try:
            parsed = json.loads(args)
            return parsed if isinstance(parsed, dict) else {"_": parsed}
        except json.JSONDecodeError:
            return {"_raw": args}
    return {}


def _summarize(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return {"keys": sorted(content)[:12], "error": content.get("error")}
    if isinstance(content, list):
        return {"count": len(content)}
    text = str(content)
    return {"text": text[:280]}
