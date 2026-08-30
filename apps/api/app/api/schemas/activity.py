from __future__ import annotations

import datetime as dt
from decimal import Decimal
from uuid import UUID

from app.api.schemas import ApiModel
from app.domain.ai import AgentRunStatus, AgentType


class AgentRunSummary(ApiModel):
    id: UUID
    agent_type: AgentType
    subject_type: str
    subject_id: UUID | None
    provider: str
    model: str
    prompt_version: str | None
    status: AgentRunStatus
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: Decimal | None
    latency_ms: int | None
    error: str | None
    started_at: dt.datetime
    finished_at: dt.datetime | None
    created_at: dt.datetime
    correlation_id: str | None


class AgentRunList(ApiModel):
    runs: list[AgentRunSummary]


class ActivityToolCallOut(ApiModel):
    ordinal: int
    tool_name: str
    arguments: dict
    result_summary: dict
    status: str
    latency_ms: int | None


class AgentRunDetail(ApiModel):
    run: AgentRunSummary
    input_ref: dict
    output: dict | None
    tool_calls: list[ActivityToolCallOut]


class AuditEventOut(ApiModel):
    id: UUID
    occurred_at: dt.datetime
    actor_type: str
    actor_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    summary: str
    payload: dict
    correlation_id: str | None


class AuditFeed(ApiModel):
    events: list[AuditEventOut]


class SpendByTypeOut(ApiModel):
    agent_type: str
    runs: int
    succeeded: int
    failed: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    avg_latency_ms: int | None


class SpendByDayOut(ApiModel):
    day: str
    runs: int
    cost_usd: Decimal


class SpendTotalsOut(ApiModel):
    runs: int
    succeeded: int
    failed: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


class AiSpendResponse(ApiModel):
    since: dt.datetime
    totals: SpendTotalsOut
    by_type: list[SpendByTypeOut]
    by_day: list[SpendByDayOut]
