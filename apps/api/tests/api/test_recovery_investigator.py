"""Recovery Investigator slice: a bounded, read-only agent investigates a
candidate, its output is grounded and persisted, it never computes the recovery."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models.audit import AuditEvent
from app.db.models.extraction import AgentRun, ToolCall
from app.db.models.recoveries import RecoveryInvestigation
from tests.support.auth import register
from tests.support.investigation import run_investigation
from tests.support.scenario import committed_hurricane_event, validated_golden_treaty

pytestmark = pytest.mark.db


async def _candidate(client: AsyncClient, object_store, session) -> tuple[str, str]:
    golden = await validated_golden_treaty(client, object_store, session)
    event_id = await committed_hurricane_event(client)
    candidate = (
        await client.post(
            "/recovery-candidates",
            json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
        )
    ).json()
    return str(golden.org_id), candidate["id"]


class TestInvestigation:
    async def test_investigation_is_persisted_grounded_and_audited(
        self, client: AsyncClient, object_store, session
    ) -> None:
        org_id, candidate_id = await _candidate(client, object_store, session)
        investigation = await run_investigation(
            session, get_settings(), uuid.UUID(org_id), uuid.UUID(candidate_id)
        )

        assert investigation.status.value == "completed"
        assert investigation.applicability_assessment.value == "supported"
        assert investigation.suspected_prompt_injection is False

        detail = (await client.get(f"/recovery-candidates/{candidate_id}")).json()
        assert len(detail["investigations"]) == 1
        inv = detail["investigations"][0]
        assert inv["status"] == "completed"
        assert inv["applicability_assessment"] == "supported"
        assert inv["agent_run_id"]

        kinds = {f["kind"] for f in inv["findings"]}
        # the two real citations resolve; the fabricated-quote finding is downgraded
        clause = next(f for f in inv["findings"] if "Article IV" in f["text"])
        assert clause["kind"] == "relevant_clause"
        assert "50,000,000" in clause["citation"]["quoted_text"]
        assert clause["citation"]["page_number"] == 2

        downgraded = next(f for f in inv["findings"] if "subrogation" in f["text"])
        assert downgraded["kind"] == "ambiguity"
        assert downgraded["citation"] is None
        assert downgraded["text"].startswith("[unverified]")

        assert "missing_information" in kinds  # uncited, but allowed to stay

        actions = {
            row.action for row in (await session.execute(select(AuditEvent))).scalars().all()
        }
        assert "recovery_candidate.investigated" in actions

    async def test_agent_run_and_tool_calls_are_recorded(
        self, client: AsyncClient, object_store, session
    ) -> None:
        org_id, candidate_id = await _candidate(client, object_store, session)
        investigation = await run_investigation(
            session, get_settings(), uuid.UUID(org_id), uuid.UUID(candidate_id)
        )

        run = (
            await session.execute(select(AgentRun).where(AgentRun.id == investigation.agent_run_id))
        ).scalar_one()
        assert run.agent_type.value == "recovery_investigator"
        assert run.status.value == "succeeded"
        assert run.output is not None

        calls = (
            (await session.execute(select(ToolCall).where(ToolCall.agent_run_id == run.id)))
            .scalars()
            .all()
        )
        assert {c.tool_name for c in calls} == {"get_recovery_calculation", "search_treaty"}

        listed = (
            await client.get(f"/recovery-candidates/{candidate_id}/agent-runs/{run.id}/tool-calls")
        ).json()
        assert [c["ordinal"] for c in listed["tool_calls"]] == [1, 2]

    async def test_reinvestigating_supersedes_the_prior_one(
        self, client: AsyncClient, object_store, session
    ) -> None:
        org_id, candidate_id = await _candidate(client, object_store, session)
        await run_investigation(session, get_settings(), uuid.UUID(org_id), uuid.UUID(candidate_id))
        await run_investigation(session, get_settings(), uuid.UUID(org_id), uuid.UUID(candidate_id))

        rows = (
            (
                await session.execute(
                    select(RecoveryInvestigation).where(
                        RecoveryInvestigation.recovery_candidate_id == uuid.UUID(candidate_id)
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2
        assert sum(1 for r in rows if r.superseded_at is None) == 1

        detail = (await client.get(f"/recovery-candidates/{candidate_id}")).json()
        assert detail["investigations"][0]["superseded"] is False
        assert detail["investigations"][1]["superseded"] is True


class TestInvestigateEndpoint:
    async def test_investigate_enqueues_a_job(
        self, client: AsyncClient, object_store, session, investigate_calls
    ) -> None:
        _, candidate_id = await _candidate(client, object_store, session)
        resp = await client.post(f"/recovery-candidates/{candidate_id}/investigate")
        assert resp.status_code == 202
        assert len(investigate_calls) == 1
        assert str(investigate_calls[0][1]) == candidate_id

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/recovery-candidates/00000000-0000-0000-0000-000000000000/investigate"
        )
        assert resp.status_code == 401

    async def test_unknown_candidate_is_404(self, client: AsyncClient) -> None:
        await register(client, email="x@carrier.example")
        resp = await client.post(
            "/recovery-candidates/00000000-0000-0000-0000-000000000000/investigate"
        )
        assert resp.status_code == 404


class TestTenantIsolation:
    async def test_other_org_cannot_read_investigations(
        self, client_factory, object_store, session
    ) -> None:
        a = await client_factory()
        b = await client_factory()
        golden = await validated_golden_treaty(
            a, object_store, session, email="a@a.example", org="Carrier A"
        )
        event_id = await committed_hurricane_event(a)
        candidate = (
            await a.post(
                "/recovery-candidates",
                json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
            )
        ).json()
        await run_investigation(session, get_settings(), golden.org_id, uuid.UUID(candidate["id"]))

        await register(b, org="Carrier B", email="b@b.example")
        assert (await b.get(f"/recovery-candidates/{candidate['id']}")).status_code == 404
