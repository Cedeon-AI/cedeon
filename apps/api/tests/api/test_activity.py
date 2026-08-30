"""The activity / observability surface: AI runs, the audit feed, AI spend."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from tests.support.auth import register
from tests.support.investigation import run_investigation
from tests.support.notice import run_notice_draft
from tests.support.scenario import confirmed_recovery_candidate

pytestmark = pytest.mark.db


async def _org_with_ai_history(client: AsyncClient, object_store, session, **kw) -> str:
    golden, candidate_id = await confirmed_recovery_candidate(client, object_store, session, **kw)
    await run_investigation(session, get_settings(), golden.org_id, uuid.UUID(candidate_id))
    await run_notice_draft(session, get_settings(), golden.org_id, uuid.UUID(candidate_id))
    return candidate_id


class TestAgentRuns:
    async def test_lists_runs_newest_first_with_telemetry(
        self, client: AsyncClient, object_store, session
    ) -> None:
        await _org_with_ai_history(client, object_store, session)

        runs = (await client.get("/activity/agent-runs")).json()["runs"]
        # the golden scenario also runs a faked extraction → 3 agent runs
        types = [r["agent_type"] for r in runs]
        assert "recovery_investigator" in types
        assert "notice_drafter" in types
        assert all(r["status"] == "succeeded" for r in runs)
        assert runs == sorted(runs, key=lambda r: r["created_at"], reverse=True)

        one = runs[0]
        assert one["model"]
        assert one["input_tokens"] is not None
        assert one["latency_ms"] is not None

    async def test_filter_by_agent_type_and_status(
        self, client: AsyncClient, object_store, session
    ) -> None:
        await _org_with_ai_history(client, object_store, session)
        investigator = (
            await client.get("/activity/agent-runs?agent_type=recovery_investigator")
        ).json()["runs"]
        assert investigator and all(
            r["agent_type"] == "recovery_investigator" for r in investigator
        )
        failed = (await client.get("/activity/agent-runs?status=failed")).json()["runs"]
        assert failed == []

    async def test_detail_carries_tool_calls_and_output(
        self, client: AsyncClient, object_store, session
    ) -> None:
        await _org_with_ai_history(client, object_store, session)
        runs = (await client.get("/activity/agent-runs")).json()["runs"]
        investigator = next(r for r in runs if r["agent_type"] == "recovery_investigator")

        detail = (await client.get(f"/activity/agent-runs/{investigator['id']}")).json()
        assert detail["output"] is not None
        assert {c["tool_name"] for c in detail["tool_calls"]} == {
            "get_recovery_calculation",
            "search_treaty",
        }

    async def test_unknown_run_is_404(self, client: AsyncClient) -> None:
        await register(client, email="x@carrier.example")
        assert (await client.get(f"/activity/agent-runs/{uuid.uuid4()}")).status_code == 404


class TestAuditFeed:
    async def test_feed_shows_transitions_and_filters_by_action(
        self, client: AsyncClient, object_store, session
    ) -> None:
        await _org_with_ai_history(client, object_store, session)

        feed = (await client.get("/activity/audit?limit=200")).json()["events"]
        actions = {e["action"] for e in feed}
        assert {"recovery_candidate.created", "recovery_candidate.investigated"} <= actions
        assert feed == sorted(feed, key=lambda e: e["occurred_at"], reverse=True)

        one_action = (
            await client.get("/activity/audit?action=recovery_candidate.investigated")
        ).json()["events"]
        assert one_action and all(
            e["action"] == "recovery_candidate.investigated" for e in one_action
        )

    async def test_filter_by_actor_type(self, client: AsyncClient, object_store, session) -> None:
        await _org_with_ai_history(client, object_store, session)
        agent_events = (await client.get("/activity/audit?actor_type=agent")).json()["events"]
        assert agent_events and all(e["actor_type"] == "agent" for e in agent_events)


class TestAiSpend:
    async def test_totals_sum_the_run_telemetry(
        self, client: AsyncClient, object_store, session
    ) -> None:
        await _org_with_ai_history(client, object_store, session)
        runs = (await client.get("/activity/agent-runs")).json()["runs"]
        spend = (await client.get("/activity/ai-spend")).json()

        assert spend["totals"]["runs"] == len(runs)
        assert spend["totals"]["input_tokens"] == sum(r["input_tokens"] or 0 for r in runs)
        assert {t["agent_type"] for t in spend["by_type"]} >= {
            "recovery_investigator",
            "notice_drafter",
        }
        assert len(spend["by_day"]) >= 1
        # the golden fakes carry non-zero cost
        assert float(spend["totals"]["cost_usd"]) > 0


class TestTenantIsolation:
    async def test_other_org_sees_only_its_own_activity(
        self, client_factory, object_store, session
    ) -> None:
        a = await client_factory()
        b = await client_factory()
        await _org_with_ai_history(a, object_store, session, email="a@a.example", org="Carrier A")
        await register(b, org="Carrier B", email="b@b.example")

        assert (await b.get("/activity/agent-runs")).json()["runs"] == []
        assert (await b.get("/activity/ai-spend")).json()["totals"]["runs"] == 0
        # B sees its own registration audit, but nothing from A
        b_actions = {e["action"] for e in (await b.get("/activity/audit")).json()["events"]}
        assert "recovery_candidate.investigated" not in b_actions
        assert "recovery_candidate.created" not in b_actions
