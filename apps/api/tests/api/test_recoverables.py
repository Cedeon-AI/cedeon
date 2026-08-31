"""Collection tracking (ADR-0024): materialize recoverables from a confirmed
recovery, move them toward cash, roll up the portfolio. No AI."""

from __future__ import annotations

import datetime as dt

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.audit import AuditEvent
from tests.support.auth import register
from tests.support.scenario import confirmed_recovery_candidate

pytestmark = pytest.mark.db


class TestRecoverables:
    async def test_materialize_is_idempotent_and_matches_the_split(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)

        r1 = await client.post(f"/recovery-candidates/{candidate_id}/recoverables")
        assert r1.status_code == 200
        items = r1.json()["recoverables"]
        assert len(items) == 3
        assert sorted(i["expected_amount"] for i in items) == [
            "1740000.00",
            "2610000.00",
            "4350000.00",
        ]
        assert {i["status"] for i in items} == {"pending"}
        assert all(i["outstanding"] == i["expected_amount"] for i in items)

        # calling again returns the same rows, no duplicates
        r2 = await client.post(f"/recovery-candidates/{candidate_id}/recoverables")
        assert {i["id"] for i in r2.json()["recoverables"]} == {i["id"] for i in items}

    async def test_cannot_materialize_before_confirmed(
        self, client: AsyncClient, object_store, session
    ) -> None:
        from tests.support.scenario import committed_hurricane_event, validated_golden_treaty

        golden = await validated_golden_treaty(client, object_store, session)
        event_id = await committed_hurricane_event(client)
        candidate = (
            await client.post(
                "/recovery-candidates",
                json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
            )
        ).json()

        resp = await client.post(f"/recovery-candidates/{candidate['id']}/recoverables")
        assert resp.status_code == 409

    async def test_update_flow_notified_agreed_collected_and_summary(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        items = (await client.post(f"/recovery-candidates/{candidate_id}/recoverables")).json()[
            "recoverables"
        ]
        big = max(items, key=lambda i: i["expected_amount"])  # the 4.35M leg

        notified = (
            await client.post(f"/recoverables/{big['id']}", json={"status": "notified"})
        ).json()
        assert notified["status"] == "notified"
        assert notified["notified_at"] is not None

        past_due = (dt.date.today() - dt.timedelta(days=45)).isoformat()
        agreed = (
            await client.post(
                f"/recoverables/{big['id']}",
                json={"status": "agreed", "agreed_amount": "4300000.00", "due_date": past_due},
            )
        ).json()
        assert agreed["agreed_amount"] == "4300000.00"
        assert agreed["outstanding"] == "4300000.00"
        assert agreed["days_overdue"] > 0

        # collect it in full → auto-settles to collected
        settled = (
            await client.post(f"/recoverables/{big['id']}", json={"collect": "4300000.00"})
        ).json()
        assert settled["status"] == "collected"
        assert settled["collected_amount"] == "4300000.00"
        assert settled["outstanding"] == "0.00"
        assert settled["settled_at"] is not None

        summary = (await client.get("/recoverables/summary")).json()
        assert summary["total_expected"] == "8700000.00"
        assert summary["total_collected"] == "4300000.00"
        # 2.61M + 1.74M still pending
        assert summary["total_outstanding"] == "4350000.00"

        # a negative collection is rejected
        bad = await client.post(f"/recoverables/{items[1]['id']}", json={"collect": "-5"})
        assert bad.status_code == 422

    async def test_portfolio_is_tenant_scoped(
        self, client: AsyncClient, client_factory, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        await client.post(f"/recovery-candidates/{candidate_id}/recoverables")
        assert len((await client.get("/recoverables")).json()["recoverables"]) == 3

        other = await client_factory()
        await register(other, email="b@other.example", org="Other Carrier")
        assert (await other.get("/recoverables")).json()["recoverables"] == []
        assert (await other.get("/recoverables/summary")).json()["count"] == 0

    async def test_materialize_writes_an_audit_event(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        await client.post(f"/recovery-candidates/{candidate_id}/recoverables")

        actions = (
            (await session.execute(select(AuditEvent.action).order_by(AuditEvent.occurred_at)))
            .scalars()
            .all()
        )
        assert "recovery.recoverables_materialized" in actions
