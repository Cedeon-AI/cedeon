"""The worklist unions every "needs a human" signal into one ranked list."""

from __future__ import annotations

import datetime as dt

import pytest
from httpx import AsyncClient

from tests.support.auth import register
from tests.support.scenario import (
    committed_hurricane_event,
    confirmed_recovery_candidate,
    validated_golden_treaty,
)

pytestmark = pytest.mark.db


class TestWorklist:
    async def test_empty_for_a_fresh_org(self, client: AsyncClient) -> None:
        await register(client, email="fresh@carrier.example")
        body = (await client.get("/worklist")).json()
        assert body["items"] == []
        assert body["summary"]["open_count"] == 0
        assert body["summary"]["open_recoverable"] == "0"
        assert body["summary"]["largest_open_recovery"] is None

    async def test_a_recovery_awaiting_review_shows_up(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        event_id = await committed_hurricane_event(client)
        await client.post(
            "/recovery-candidates",
            json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
        )

        body = (await client.get("/worklist")).json()
        kinds = [i["kind"] for i in body["items"]]
        assert "recovery_review" in kinds
        item = next(i for i in body["items"] if i["kind"] == "recovery_review")
        assert item["amount"] == "8700000.00"
        assert item["href"].startswith("/recovery-candidates/")
        assert item["urgency"] == sum(t["points"] for t in item["urgency_terms"])
        assert body["summary"]["largest_open_recovery"] == "8700000.00"

    async def test_an_overdue_recoverable_ranks_above_a_plain_review(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        legs = (await client.post(f"/recovery-candidates/{candidate_id}/recoverables")).json()[
            "recoverables"
        ]
        big = max(legs, key=lambda i: i["expected_amount"])
        past_due = (dt.date.today() - dt.timedelta(days=75)).isoformat()
        await client.post(
            f"/recoverables/{big['id']}",
            json={"status": "notified", "due_date": past_due},
        )

        body = (await client.get("/worklist")).json()
        overdue = [i for i in body["items"] if i["kind"] == "recoverable_overdue"]
        assert len(overdue) == 1
        assert overdue[0]["due_in_days"] in (-74, -75, -76)  # date-boundary tolerant
        assert overdue[0]["category"] == "recovery"
        assert overdue[0]["amount"] == "4350000.00"
        assert body["summary"]["overdue_outstanding"] == "4350000.00"
        # it carries a real deadline, so it outranks anything without one
        assert body["items"][0]["kind"] == "recoverable_overdue"

    async def test_items_come_back_ranked_worst_first(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        await client.post(f"/recovery-candidates/{candidate_id}/recoverables")
        body = (await client.get("/worklist")).json()
        urgencies = [i["urgency"] for i in body["items"]]
        assert urgencies == sorted(urgencies, reverse=True)

    async def test_tenant_scoped(
        self, client: AsyncClient, client_factory, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        event_id = await committed_hurricane_event(client)
        await client.post(
            "/recovery-candidates",
            json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
        )
        assert len((await client.get("/worklist")).json()["items"]) >= 1

        other = await client_factory()
        await register(other, email="other@carrier.example", org="Other Carrier")
        assert (await other.get("/worklist")).json()["items"] == []

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        assert (await client.get("/worklist")).status_code == 401
