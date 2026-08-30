"""Notice drafter slice: after the candidate is CONFIRMED, draft a notice from a
whitelist of approved facts, let a human edit and approve it. Cedeon never sends."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models.audit import AuditEvent
from app.db.models.extraction import AgentRun, Review
from app.db.models.recoveries import RecoveryNotice
from tests.support.auth import register
from tests.support.notice import run_notice_draft
from tests.support.scenario import (
    committed_hurricane_event,
    confirmed_recovery_candidate,
    validated_golden_treaty,
)

pytestmark = pytest.mark.db


class TestDraft:
    async def test_draft_is_persisted_from_approved_facts_and_audited(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        notice = await run_notice_draft(
            session, get_settings(), golden.org_id, uuid.UUID(candidate_id)
        )

        assert notice.status.value == "draft"
        assert notice.kind.value == "initial_loss_advice"
        assert notice.used_only_provided_facts is True
        assert "8700000.00" in notice.body_markdown
        assert "2027 Property Cat XOL" in notice.body_markdown
        assert notice.recipient["organisation"] == "Reinsurer Alpha"
        assert notice.key_figures["layer_recovery"] == "8700000.00"
        assert notice.context["cedent_name"] == "Demo Specialty"
        assert notice.context["treaty_name"] == "2027 Property Cat XOL"

        detail = (await client.get(f"/recovery-candidates/{candidate_id}/notices")).json()[
            "notices"
        ]
        assert len(detail) == 1
        assert detail[0]["status"] == "draft"

        # the candidate advances to notice_drafted
        candidate = (await client.get(f"/recovery-candidates/{candidate_id}")).json()
        assert candidate["candidate"]["status"] == "notice_drafted"

        run = (
            await session.execute(select(AgentRun).where(AgentRun.id == notice.agent_run_id))
        ).scalar_one()
        assert run.agent_type.value == "notice_drafter"
        assert run.status.value == "succeeded"

        actions = {r.action for r in (await session.execute(select(AuditEvent))).scalars().all()}
        assert "recovery_candidate.notice_drafted" in actions

    async def test_cannot_draft_before_the_candidate_is_confirmed(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        event_id = await committed_hurricane_event(client)
        candidate = (
            await client.post(
                "/recovery-candidates",
                json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
            )
        ).json()
        resp = await client.post(
            f"/recovery-candidates/{candidate['id']}/notices",
            json={
                "kind": "initial_loss_advice",
                "recipient": {"name": "X", "organisation": "Y"},
            },
        )
        assert resp.status_code == 409
        assert "confirm the recovery candidate" in resp.text

    async def test_redrafting_supersedes_the_prior_notice_of_that_kind(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        first = await run_notice_draft(
            session, get_settings(), golden.org_id, uuid.UUID(candidate_id)
        )
        second = await run_notice_draft(
            session, get_settings(), golden.org_id, uuid.UUID(candidate_id)
        )
        assert first.id != second.id

        rows = (
            (
                await session.execute(
                    select(RecoveryNotice).where(
                        RecoveryNotice.recovery_candidate_id == uuid.UUID(candidate_id)
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2
        by_id = {r.id: r for r in rows}
        assert by_id[first.id].superseded_at is not None
        assert by_id[first.id].status.value == "superseded"
        assert by_id[second.id].superseded_at is None


class TestReview:
    async def test_edit_records_before_after_in_place(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        notice = await run_notice_draft(
            session, get_settings(), golden.org_id, uuid.UUID(candidate_id)
        )
        original = notice.body_markdown

        resp = await client.post(
            f"/recovery-notices/{notice.id}/review",
            json={
                "decision": "edit",
                "body_markdown": original + "\n\nP.S. Our claim reference is DEMO-2027-001.",
                "reason": "add the claim reference",
            },
        )
        assert resp.status_code == 200, resp.text
        assert "DEMO-2027-001" in resp.json()["body_markdown"]
        assert resp.json()["status"] == "draft"  # editing a draft keeps it a draft

        review = (
            (await session.execute(select(Review).where(Review.subject_id == notice.id)))
            .scalars()
            .one()
        )
        assert review.decision.value == "edit"
        assert review.value_before["body_markdown"] == original

    async def test_approve_freezes_the_notice(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        notice = await run_notice_draft(
            session, get_settings(), golden.org_id, uuid.UUID(candidate_id)
        )
        approved = (
            await client.post(f"/recovery-notices/{notice.id}/review", json={"decision": "confirm"})
        ).json()
        assert approved["status"] == "approved"
        assert approved["approved_at"]

        # a frozen notice cannot be reviewed further
        assert (
            await client.post(
                f"/recovery-notices/{notice.id}/review",
                json={"decision": "edit", "body_markdown": "changed"},
            )
        ).status_code == 409

    async def test_no_send_endpoint_exists(self, client: AsyncClient) -> None:
        # There is deliberately no way to send a notice from Cedeon (AI_ARCH §2c).
        schema = (await client.get("/openapi.json")).json()
        notice_ops = [
            op.get("operationId", "")
            for path, methods in schema["paths"].items()
            if "notice" in path.lower()
            for op in methods.values()
        ]
        assert notice_ops
        assert not any("send" in op.lower() for op in notice_ops)


class TestEndpoint:
    async def test_post_enqueues_the_drafter_job(
        self, client: AsyncClient, object_store, session, notice_calls
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        resp = await client.post(
            f"/recovery-candidates/{candidate_id}/notices",
            json={
                "kind": "reinsurer_notification",
                "recipient": {"name": "Jane U.", "organisation": "Reinsurer Beta"},
            },
        )
        assert resp.status_code == 202
        assert len(notice_calls) == 1
        assert notice_calls[0]["kind"] == "reinsurer_notification"
        assert str(notice_calls[0]["candidate"]) == candidate_id


class TestTenantIsolation:
    async def test_other_org_cannot_read_or_review(
        self, client_factory, object_store, session
    ) -> None:
        a = await client_factory()
        b = await client_factory()
        golden, candidate_id = await confirmed_recovery_candidate(
            a, object_store, session, email="a@a.example", org="Carrier A"
        )
        notice = await run_notice_draft(
            session, get_settings(), golden.org_id, uuid.UUID(candidate_id)
        )

        await register(b, org="Carrier B", email="b@b.example")
        assert (await b.get(f"/recovery-notices/{notice.id}")).status_code == 404
        assert (
            await b.post(f"/recovery-notices/{notice.id}/review", json={"decision": "confirm"})
        ).status_code == 404
        assert (await b.get(f"/recovery-candidates/{candidate_id}/notices")).json()["notices"] == []
