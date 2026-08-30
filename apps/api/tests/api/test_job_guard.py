"""Durability: an AI job refuses to start a second run while one is in flight, and
the AI tasks carry a retry strategy (Phase 10)."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.db.models.extraction import AgentRun
from app.domain.ai import AgentRunStatus, AgentType
from app.services.errors import ConflictError
from app.services.investigation import InvestigationService
from tests.support.investigation import golden_result
from tests.support.scenario import committed_hurricane_event, validated_golden_treaty

pytestmark = pytest.mark.db


def _running_run(org_id: uuid.UUID, subject_id: uuid.UUID, *, minutes_ago: int) -> AgentRun:
    started = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=minutes_ago)
    return AgentRun(
        organization_id=org_id,
        agent_type=AgentType.RECOVERY_INVESTIGATOR,
        subject_type="recovery_candidate",
        subject_id=subject_id,
        provider="anthropic",
        model="anthropic:claude-opus-5",
        status=AgentRunStatus.RUNNING,
        input_ref={},
        started_at=started,
    )


async def _candidate(client: AsyncClient, object_store, session) -> tuple[uuid.UUID, uuid.UUID]:
    golden = await validated_golden_treaty(client, object_store, session)
    event_id = await committed_hurricane_event(client)
    candidate = (
        await client.post(
            "/recovery-candidates",
            json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
        )
    ).json()
    return golden.org_id, uuid.UUID(candidate["id"])


async def _fake(**_kw: object):
    return golden_result()


async def test_an_active_run_blocks_a_second_investigation(
    client: AsyncClient, object_store, session
) -> None:
    org_id, candidate_id = await _candidate(client, object_store, session)
    session.add(_running_run(org_id, candidate_id, minutes_ago=1))
    await session.commit()

    service = InvestigationService(session, get_settings(), runner=_fake)  # type: ignore[arg-type]
    with pytest.raises(ConflictError, match="already running"):
        await service.investigate(org_id, candidate_id)


async def test_a_stale_run_does_not_block(client: AsyncClient, object_store, session) -> None:
    org_id, candidate_id = await _candidate(client, object_store, session)
    session.add(_running_run(org_id, candidate_id, minutes_ago=30))  # older than the 15m cutoff
    await session.commit()

    service = InvestigationService(session, get_settings(), runner=_fake)  # type: ignore[arg-type]
    investigation = await service.investigate(org_id, candidate_id)
    assert investigation.status.value == "completed"


def test_ai_tasks_carry_a_retry_strategy() -> None:
    from app.jobs.tasks import (
        draft_recovery_notice,
        extract_treaty,
        investigate_recovery_candidate,
        parse_document,
    )

    for task in (
        extract_treaty,
        investigate_recovery_candidate,
        draft_recovery_notice,
        parse_document,
    ):
        assert task.retry_strategy is not None
        assert task.retry_strategy.max_attempts >= 2  # type: ignore[union-attr]
