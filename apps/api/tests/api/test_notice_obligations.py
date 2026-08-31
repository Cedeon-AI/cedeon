"""Structured notice terms → a deadline computed by deterministic code, surfaced
on the recovery and on the worklist. The AI never computes the date."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from tests.support.notice import run_notice_draft
from tests.support.scenario import (
    committed_hurricane_event,
    confirmed_recovery_candidate,
    validated_golden_treaty,
)

pytestmark = pytest.mark.db


async def _set_notice_term(client: AsyncClient, golden, **body: object) -> None:
    resp = await client.put(
        f"/treaties/{golden.treaty_id}/versions/{golden.version_id}/notice-term",
        json=body,
    )
    assert resp.status_code == 204, resp.text


class TestComputedDeadline:
    async def test_loss_occurrence_trigger_uses_the_date_of_loss(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        await _set_notice_term(
            client,
            golden,
            provision_text="Notice within 30 days of a loss occurrence.",
            period_days=30,
            trigger="loss_occurrence",
            basis="calendar",
        )
        event_id = await committed_hurricane_event(client)
        candidate = (
            await client.post(
                "/recovery-candidates",
                json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
            )
        ).json()

        detail = (await client.get(f"/recovery-candidates/{candidate['id']}")).json()
        ob = detail["notice_obligation"]
        assert ob["has_structured_term"] is True
        assert ob["period_days"] == 30
        assert ob["reference_date"] == "2027-09-14"  # golden loss date
        assert ob["deadline"] == "2027-10-14"
        assert ob["satisfied"] is False

    async def test_knowledge_trigger_follows_the_knowledge_date(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        await _set_notice_term(
            client,
            golden,
            provision_text="Notice within 45 days of knowledge.",
            period_days=45,
            trigger="knowledge_of_loss",
        )
        event_id = await committed_hurricane_event(client)
        candidate = (
            await client.post(
                "/recovery-candidates",
                json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
            )
        ).json()

        # with no knowledge date it falls back to the loss date, with a note
        before = (await client.get(f"/recovery-candidates/{candidate['id']}")).json()[
            "notice_obligation"
        ]
        assert before["deadline"] == "2027-10-29"
        assert before["note"] is not None

        set_resp = await client.post(
            f"/recovery-candidates/{candidate['id']}/knowledge-date",
            json={"knowledge_date": "2027-09-20"},
        )
        assert set_resp.status_code == 200
        after = (await client.get(f"/recovery-candidates/{candidate['id']}")).json()[
            "notice_obligation"
        ]
        assert after["reference_date"] == "2027-09-20"
        assert after["deadline"] == "2027-11-04"

    async def test_free_text_only_term_has_no_deadline(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        await _set_notice_term(
            client, golden, provision_text="Notice as soon as reasonably practicable."
        )
        event_id = await committed_hurricane_event(client)
        candidate = (
            await client.post(
                "/recovery-candidates",
                json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
            )
        ).json()
        ob = (await client.get(f"/recovery-candidates/{candidate['id']}")).json()[
            "notice_obligation"
        ]
        assert ob["has_structured_term"] is False
        assert ob["deadline"] is None
        assert "structured deadline" in ob["note"]


class TestWorklistIntegration:
    async def test_a_due_notice_appears_on_the_worklist_then_clears_when_approved(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        await _set_notice_term(
            client,
            golden,
            provision_text="Notice within 30 days of knowledge.",
            period_days=30,
            trigger="knowledge_of_loss",
        )
        # knowledge 20 days ago → deadline in ~10 days, inside the worklist horizon
        await client.post(
            f"/recovery-candidates/{candidate_id}/knowledge-date",
            json={"knowledge_date": (dt.date.today() - dt.timedelta(days=20)).isoformat()},
        )

        items = (await client.get("/worklist")).json()["items"]
        notice_items = [i for i in items if i["kind"] == "notice_due"]
        assert len(notice_items) == 1
        assert notice_items[0]["due_in_days"] is not None
        assert notice_items[0]["href"].endswith("?section=notice")

        # draft + approve a notice → obligation satisfied → item gone
        await run_notice_draft(session, get_settings(), golden.org_id, uuid.UUID(candidate_id))
        notices = (await client.get(f"/recovery-candidates/{candidate_id}/notices")).json()[
            "notices"
        ]
        approve = await client.post(
            f"/recovery-notices/{notices[0]['id']}/review", json={"decision": "confirm"}
        )
        assert approve.status_code == 200

        detail = (await client.get(f"/recovery-candidates/{candidate_id}")).json()
        assert detail["notice_obligation"]["satisfied"] is True
        items = (await client.get("/worklist")).json()["items"]
        assert [i for i in items if i["kind"] == "notice_due"] == []
