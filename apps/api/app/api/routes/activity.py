"""Activity / observability: what the AI did (agent_runs + tool_calls), what
happened (audit feed), and what it cost (AI spend). Read-only (Phase 10)."""

from __future__ import annotations

import datetime as dt
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies.context import AuthedContext, DbSession
from app.api.schemas.activity import (
    ActivityToolCallOut,
    AgentRunDetail,
    AgentRunList,
    AgentRunSummary,
    AiSpendResponse,
    AuditEventOut,
    AuditFeed,
    SpendByDayOut,
    SpendByTypeOut,
    SpendTotalsOut,
)
from app.db.models.audit import AuditEvent
from app.db.models.extraction import AgentRun, ToolCall
from app.domain.ai import AgentRunStatus, AgentType
from app.services.activity import ActivityService

router = APIRouter(prefix="/activity", tags=["activity"])


def _run_summary(run: AgentRun) -> AgentRunSummary:
    return AgentRunSummary(
        id=run.id,
        agent_type=run.agent_type,
        subject_type=run.subject_type,
        subject_id=run.subject_id,
        provider=run.provider,
        model=run.model,
        prompt_version=run.prompt_version,
        status=run.status,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        cost_usd=run.cost_usd,
        latency_ms=run.latency_ms,
        error=run.error,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        correlation_id=run.correlation_id,
    )


def _tool_call_out(call: ToolCall) -> ActivityToolCallOut:
    return ActivityToolCallOut(
        ordinal=call.ordinal,
        tool_name=call.tool_name,
        arguments=dict(call.arguments),
        result_summary=dict(call.result_summary),
        status=call.status.value,
        latency_ms=call.latency_ms,
    )


def _audit_out(event: AuditEvent) -> AuditEventOut:
    return AuditEventOut(
        id=event.id,
        occurred_at=event.occurred_at,
        actor_type=event.actor_type.value,
        actor_id=event.actor_id,
        action=event.action,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        summary=event.summary,
        payload=dict(event.payload),
        correlation_id=event.correlation_id,
    )


@router.get("/agent-runs", response_model=AgentRunList, operation_id="listAgentRuns")
async def list_agent_runs(
    context: AuthedContext,
    session: DbSession,
    agent_type: Annotated[AgentType | None, Query()] = None,
    run_status: Annotated[AgentRunStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before: Annotated[dt.datetime | None, Query()] = None,
) -> AgentRunList:
    runs = await ActivityService(session).agent_runs(
        context, agent_type=agent_type, status=run_status, limit=limit, before=before
    )
    return AgentRunList(runs=[_run_summary(r) for r in runs])


@router.get("/agent-runs/{run_id}", response_model=AgentRunDetail, operation_id="getAgentRun")
async def get_agent_run(run_id: UUID, context: AuthedContext, session: DbSession) -> AgentRunDetail:
    run, tools = await ActivityService(session).agent_run_detail(context, run_id)
    return AgentRunDetail(
        run=_run_summary(run),
        input_ref=dict(run.input_ref),
        output=run.output,
        tool_calls=[_tool_call_out(t) for t in tools],
    )


@router.get("/audit", response_model=AuditFeed, operation_id="listAuditEvents")
async def list_audit_events(
    context: AuthedContext,
    session: DbSession,
    action: Annotated[str | None, Query(max_length=100)] = None,
    actor_type: Annotated[str | None, Query(max_length=16)] = None,
    entity_type: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before: Annotated[dt.datetime | None, Query()] = None,
) -> AuditFeed:
    events = await ActivityService(session).audit_feed(
        context,
        action=action,
        actor_type=actor_type,
        entity_type=entity_type,
        limit=limit,
        before=before,
    )
    return AuditFeed(events=[_audit_out(e) for e in events])


@router.get("/ai-spend", response_model=AiSpendResponse, operation_id="getAiSpend")
async def get_ai_spend(
    context: AuthedContext,
    session: DbSession,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> AiSpendResponse:
    spend = await ActivityService(session).ai_spend(context, days=days)
    return AiSpendResponse(
        since=spend.since,
        totals=SpendTotalsOut(
            runs=spend.totals.runs,
            succeeded=spend.totals.succeeded,
            failed=spend.totals.failed,
            input_tokens=spend.totals.input_tokens,
            output_tokens=spend.totals.output_tokens,
            cost_usd=spend.totals.cost_usd,
        ),
        by_type=[
            SpendByTypeOut(
                agent_type=t.agent_type,
                runs=t.runs,
                succeeded=t.succeeded,
                failed=t.failed,
                input_tokens=t.input_tokens,
                output_tokens=t.output_tokens,
                cost_usd=t.cost_usd,
                avg_latency_ms=t.avg_latency_ms,
            )
            for t in spend.by_type
        ],
        by_day=[SpendByDayOut(day=d.day, runs=d.runs, cost_usd=d.cost_usd) for d in spend.by_day],
    )
