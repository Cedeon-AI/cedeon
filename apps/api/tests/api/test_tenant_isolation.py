"""Cross-organization access is refused server-side, by object id, on every core
resource — not merely hidden by the frontend (docs/SECURITY.md §1, ADR-0026)."""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select

from app.db.models.identity import Membership
from app.domain.organizations import Role
from tests.api.test_auth import _register
from tests.support.scenario import committed_hurricane_event, validated_golden_treaty

pytestmark = pytest.mark.db


class TestObjectLevelTenantIsolation:
    async def test_org_b_cannot_reach_org_a_objects_by_id(
        self, client_factory, object_store, session
    ) -> None:
        a = await client_factory()
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
        await a.post(f"/recovery-candidates/{candidate['id']}/review", json={"decision": "confirm"})
        recs = (await a.post(f"/recovery-candidates/{candidate['id']}/recoverables")).json()[
            "recoverables"
        ]
        statement = (
            await a.post(
                "/reinsurer-statements",
                json={
                    "label": "S",
                    "currency": "USD",
                    "lines": [{"reinsurer_name": "Reinsurer Alpha", "their_agreed": "1"}],
                },
            )
        ).json()

        b = await client_factory()
        await _register(b, email="b@b.example", org="Carrier B")

        forbidden = {
            "treaty": f"/treaties/{golden.treaty_id}",
            "loss event": f"/loss-events/{event_id}",
            "recovery": f"/recovery-candidates/{candidate['id']}",
            "recoverable list": f"/recovery-candidates/{candidate['id']}/recoverables",
            "statement": f"/reinsurer-statements/{statement['id']}",
        }
        for label, path in forbidden.items():
            resp = await b.get(path)
            assert resp.status_code == 404, f"{label}: expected 404, got {resp.status_code}"

        # a write against A's object from B's session is refused too
        assert (
            await b.post(
                f"/recovery-candidates/{candidate['id']}/review", json={"decision": "confirm"}
            )
        ).status_code == 404
        assert (
            await b.post(f"/recoverables/{recs[0]['id']}", json={"status": "notified"})
        ).status_code == 404

        # B's own lists are empty — no leakage
        assert (await b.get("/treaties")).json()["treaties"] == []
        assert (await b.get("/recovery-candidates")).json()["candidates"] == []

    async def test_a_viewer_cannot_write(self, client_factory, session) -> None:
        # There is no product path to viewer yet; exercise the write-guard directly.
        a = await client_factory()
        body = await _register(a, email="v-admin@a.example")
        membership = (
            await session.execute(
                select(Membership).where(Membership.user_id == UUID(body["user"]["id"]))
            )
        ).scalar_one()
        membership.role = Role.VIEWER
        await session.commit()

        assert (await a.post("/cedents", json={"name": "X"})).status_code == 403
        assert (await a.get("/treaties")).status_code == 200  # reads still work
