"""Endorsements open a new treaty version: the frozen state copies forward, the
old version is superseded, and open recoveries against it surface for re-review."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.support.scenario import committed_hurricane_event, validated_golden_treaty

pytestmark = pytest.mark.db


class TestNewVersion:
    async def test_copies_forward_and_supersedes(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)

        resp = await client.post(
            f"/treaties/{golden.treaty_id}/versions",
            json={"note": "Endorsement 3 — revised occurrence limit"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()

        versions = {v["version_no"]: v for v in body["versions"]}
        assert versions[1]["status"] == "superseded"
        assert versions[2]["status"] == "needs_validation"
        assert body["treaty"]["current_version"]["version_no"] == 2

        v2 = body["current_version"]
        assert [(x["attachment"], x["limit"]) for x in v2["layers"]] == [
            ("50000000.00", "20000000.00")
        ]
        assert {p["reinsurer_name"] for p in v2["participations"]} == {
            "Reinsurer Alpha",
            "Reinsurer Beta",
            "Reinsurer Gamma",
        }

    async def test_the_new_version_can_be_edited_and_revalidated(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        v2 = (
            await client.post(
                f"/treaties/{golden.treaty_id}/versions", json={"note": "Endorsement 4"}
            )
        ).json()["current_version"]

        # the endorsement raised the attachment
        await client.put(
            f"/treaties/{golden.treaty_id}/versions/{v2['id']}/layers",
            json={"currency": "USD", "layers": [{"attachment": "60000000", "limit": "20000000"}]},
        )
        validated = await client.post(f"/treaties/{golden.treaty_id}/versions/{v2['id']}/validate")
        assert validated.status_code == 200
        detail = (await client.get(f"/treaties/{golden.treaty_id}")).json()
        assert detail["current_version"]["status"] == "validated"
        assert detail["current_version"]["layers"][0]["attachment"] == "60000000.00"

    async def test_rejects_a_new_version_before_the_current_is_validated(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session, layers=[("5", "5")])
        # open v2 (needs_validation), then try to open v3 on top of it
        await client.post(f"/treaties/{golden.treaty_id}/versions", json={"note": "e1"})
        resp = await client.post(f"/treaties/{golden.treaty_id}/versions", json={"note": "e2"})
        assert resp.status_code == 409

    async def test_requires_a_note(self, client: AsyncClient, object_store, session) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        resp = await client.post(f"/treaties/{golden.treaty_id}/versions", json={"note": "  "})
        assert resp.status_code == 422


class TestContractChangeOnWorklist:
    async def test_a_recovery_on_a_superseded_version_surfaces_as_contract_change(
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

        await client.post(f"/treaties/{golden.treaty_id}/versions", json={"note": "Endorsement 5"})

        items = (await client.get("/worklist")).json()["items"]
        change = [i for i in items if i["kind"] == "contract_change"]
        assert len(change) == 1
        assert change[0]["category"] == "contract"
        assert change[0]["href"] == f"/recovery-candidates/{candidate['id']}?section=calculation"
        assert change[0]["amount"] == "8700000.00"
