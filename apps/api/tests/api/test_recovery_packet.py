"""Recovery Packet slice: assemble the reviewed artifact, version it, review it.
Every statement is classified FACT / CALCULATION / AI_INTERPRETATION / HUMAN_DECISION."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models.audit import AuditEvent
from app.db.models.extraction import Review
from tests.support.auth import register
from tests.support.investigation import run_investigation
from tests.support.scenario import committed_hurricane_event, validated_golden_treaty

pytestmark = pytest.mark.db


async def _candidate_with_investigation(
    client: AsyncClient, object_store, session
) -> tuple[str, str]:
    golden = await validated_golden_treaty(client, object_store, session)
    event_id = await committed_hurricane_event(client)
    candidate = (
        await client.post(
            "/recovery-candidates",
            json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
        )
    ).json()
    await run_investigation(session, get_settings(), golden.org_id, uuid.UUID(candidate["id"]))
    return str(golden.org_id), candidate["id"]


def _classes(version: dict) -> set[str]:
    return {
        s["statement_class"]
        for section in version["content"]["sections"]
        for s in section["statements"]
    }


def _statement(version: dict, key: str) -> dict | None:
    for section in version["content"]["sections"]:
        for s in section["statements"]:
            if s["key"] == key:
                return s
    return None


class TestGenerate:
    async def test_packet_has_all_four_statement_classes_and_the_golden_figure(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await _candidate_with_investigation(client, object_store, session)

        resp = await client.post(f"/recovery-candidates/{candidate_id}/packet")
        assert resp.status_code == 201, resp.text
        generated = resp.json()
        assert generated["version"]["version_no"] == 1
        assert generated["version"]["status"] == "draft"

        version = generated["version"]
        assert _classes(version) == {
            "fact",
            "calculation",
            "ai_interpretation",
            "human_decision",
        }

        layer = _statement(version, "calc.layer_recovery")
        assert layer is not None
        assert layer["statement_class"] == "calculation"
        assert "8700000.00" in layer["text"]

        alloc = _statement(version, "calc.alloc.Reinsurer Alpha")
        assert alloc is not None
        assert "4350000.00" in alloc["text"]

        # the investigation's cited finding carries its citation into the packet
        finding = next(
            s
            for section in version["content"]["sections"]
            for s in section["statements"]
            if s["key"].startswith("inv.finding.")
        )
        assert finding["statement_class"] == "ai_interpretation"
        assert finding["citation"] is not None

    async def test_get_returns_current_version_and_history(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await _candidate_with_investigation(client, object_store, session)
        await client.post(f"/recovery-candidates/{candidate_id}/packet")

        detail = (await client.get(f"/recovery-candidates/{candidate_id}/packet")).json()
        assert detail["current_version"]["version_no"] == 1
        assert [v["version_no"] for v in detail["versions"]] == [1]
        assert detail["recovery_candidate_id"] == candidate_id

    async def test_regenerating_supersedes_the_prior_version(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await _candidate_with_investigation(client, object_store, session)
        await client.post(f"/recovery-candidates/{candidate_id}/packet")
        v2 = (await client.post(f"/recovery-candidates/{candidate_id}/packet")).json()
        assert v2["version"]["version_no"] == 2

        detail = (await client.get(f"/recovery-candidates/{candidate_id}/packet")).json()
        assert detail["current_version"]["version_no"] == 2
        by_no = {v["version_no"]: v for v in detail["versions"]}
        assert by_no[1]["superseded"] is True
        assert by_no[1]["status"] == "superseded"
        assert by_no[2]["superseded"] is False

    async def test_html_endpoint_renders_the_packet(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await _candidate_with_investigation(client, object_store, session)
        gen = (await client.post(f"/recovery-candidates/{candidate_id}/packet")).json()
        resp = await client.get(
            f"/recovery-packets/{gen['packet_id']}/versions/{gen['version']['id']}/html"
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        assert "8700000.00" in resp.text
        assert "AI INTERPRETATION" in resp.text

    async def test_packet_before_calculation_is_not_generable(
        self, client: AsyncClient, object_store, session
    ) -> None:
        await register(client, email="early@carrier.example")
        resp = await client.post(f"/recovery-candidates/{uuid.uuid4()}/packet")
        assert resp.status_code == 404

    async def test_get_before_generate_is_404(
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
        assert (
            await client.get(f"/recovery-candidates/{candidate['id']}/packet")
        ).status_code == 404


class TestReview:
    async def test_approve_records_status_review_and_audit(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await _candidate_with_investigation(client, object_store, session)
        gen = (await client.post(f"/recovery-candidates/{candidate_id}/packet")).json()
        pid, vid = gen["packet_id"], gen["version"]["id"]

        resp = await client.post(
            f"/recovery-packets/{pid}/versions/{vid}/review",
            json={"decision": "confirm", "reason": "ties to the treaty and schedule"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "approved"
        assert resp.json()["approved_at"]

        # already approved → further review is a conflict
        assert (
            await client.post(
                f"/recovery-packets/{pid}/versions/{vid}/review", json={"decision": "reject"}
            )
        ).status_code == 409

        reviews = (
            (await session.execute(select(Review).where(Review.subject_id == uuid.UUID(vid))))
            .scalars()
            .all()
        )
        assert [r.decision.value for r in reviews] == ["confirm"]

        actions = {r.action for r in (await session.execute(select(AuditEvent))).scalars().all()}
        assert "recovery_packet.reviewed" in actions

    async def test_edit_records_before_after_and_makes_a_new_version(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await _candidate_with_investigation(client, object_store, session)
        gen = (await client.post(f"/recovery-candidates/{candidate_id}/packet")).json()
        pid, vid = gen["packet_id"], gen["version"]["id"]
        original = _statement(gen["version"], "summary.event")["text"]

        resp = await client.post(
            f"/recovery-packets/{pid}/versions/{vid}/review",
            json={
                "decision": "edit",
                "statement_key": "summary.event",
                "value": "Loss event: Hurricane Demo 2027 (per broker advice 2027-09-20).",
                "reason": "add the broker reference",
            },
        )
        assert resp.status_code == 200, resp.text
        new_version = resp.json()
        assert new_version["version_no"] == 2

        edited = _statement(new_version, "summary.event")
        assert edited["edited_by_human"] is True
        assert "broker advice" in edited["text"]
        assert edited["detail"]["original_text"] == original

        detail = (await client.get(f"/recovery-candidates/{candidate_id}/packet")).json()
        assert "summary.event" in detail["human_overrides"]

        review = (
            (await session.execute(select(Review).where(Review.subject_id == uuid.UUID(vid))))
            .scalars()
            .one()
        )
        assert review.decision.value == "edit"
        assert review.value_before["text"] == original

    async def test_request_info_keeps_the_version_a_draft(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await _candidate_with_investigation(client, object_store, session)
        gen = (await client.post(f"/recovery-candidates/{candidate_id}/packet")).json()
        pid, vid = gen["packet_id"], gen["version"]["id"]
        resp = await client.post(
            f"/recovery-packets/{pid}/versions/{vid}/review",
            json={"decision": "request_info", "reason": "need the adjuster report"},
        )
        assert resp.json()["status"] == "draft"
        assert resp.json()["review_note"] == "need the adjuster report"

    async def test_reviewing_a_superseded_version_is_rejected(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await _candidate_with_investigation(client, object_store, session)
        v1 = (await client.post(f"/recovery-candidates/{candidate_id}/packet")).json()
        await client.post(f"/recovery-candidates/{candidate_id}/packet")  # v2 supersedes v1
        resp = await client.post(
            f"/recovery-packets/{v1['packet_id']}/versions/{v1['version']['id']}/review",
            json={"decision": "confirm"},
        )
        assert resp.status_code == 409


class TestTenantIsolation:
    async def test_other_org_cannot_read_or_review(
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
        gen = (await a.post(f"/recovery-candidates/{candidate['id']}/packet")).json()

        await register(b, org="Carrier B", email="b@b.example")
        assert (await b.get(f"/recovery-candidates/{candidate['id']}/packet")).status_code == 404
        assert (
            await b.post(
                f"/recovery-packets/{gen['packet_id']}/versions/{gen['version']['id']}/review",
                json={"decision": "confirm"},
            )
        ).status_code == 404
