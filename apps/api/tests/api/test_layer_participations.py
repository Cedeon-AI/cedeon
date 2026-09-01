"""A single layer of an XOL tower can carry its own reinsurer panel — e.g. a top
layer placed with a different market — while the rest of the stack uses the
programme-wide panel."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.support.scenario import committed_hurricane_event, validated_golden_treaty

pytestmark = pytest.mark.db

# L1 pierced for 20M (min(58.7-20, 20)), L2 for 8.7M (min(58.7-50, 50))
_STACK = [("20000000", "20000000"), ("50000000", "50000000")]
_L2_PANEL = [("Reinsurer Delta", "60"), ("Reinsurer Echo", "40")]


async def _alloc_by_reinsurer(client: AsyncClient, candidate_id: str) -> dict[str, str]:
    detail = (await client.get(f"/recovery-candidates/{candidate_id}")).json()
    return {
        a["reinsurer_name"]: a["allocated_recovery"]
        for a in detail["current_calculation"]["allocations"]
    }


class TestLayerPanel:
    async def test_a_layer_panel_overrides_only_that_layer(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(
            client, object_store, session, layers=_STACK, layer_panels={2: _L2_PANEL}
        )

        detail = (await client.get(f"/treaties/{golden.treaty_id}")).json()
        layers = detail["current_version"]["layers"]
        # programme panel unchanged on the version
        assert {p["reinsurer_name"] for p in detail["current_version"]["participations"]} == {
            "Reinsurer Alpha",
            "Reinsurer Beta",
            "Reinsurer Gamma",
        }
        assert layers[0]["participations"] == []  # L1 uses the programme panel
        assert {
            (p["reinsurer_name"], p["placed_share"]) for p in layers[1]["participations"]
        } == {("Reinsurer Delta", "0.600000"), ("Reinsurer Echo", "0.400000")}

        event_id = await committed_hurricane_event(client)
        await client.post(
            "/recovery-candidates",
            json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
        )
        candidates = (await client.get("/recovery-candidates")).json()["candidates"]
        by_layer = {}
        for c in candidates:
            d = (await client.get(f"/recovery-candidates/{c['id']}")).json()
            by_layer[d["current_calculation"]["attachment"]] = c["id"]

        # L1 (20M recovery) → programme panel 50/30/20
        assert await _alloc_by_reinsurer(client, by_layer["20000000.00"]) == {
            "Reinsurer Alpha": "10000000.00",
            "Reinsurer Beta": "6000000.00",
            "Reinsurer Gamma": "4000000.00",
        }
        # L2 (8.7M recovery) → its own panel 60/40
        assert await _alloc_by_reinsurer(client, by_layer["50000000.00"]) == {
            "Reinsurer Delta": "5220000.00",
            "Reinsurer Echo": "3480000.00",
        }

    async def test_panel_is_frozen_after_validation(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session, layers=_STACK)
        resp = await client.put(
            f"/treaties/{golden.treaty_id}/versions/{golden.version_id}/layers/2/participations",
            json={"panel": [{"reinsurer_name": "Reinsurer Delta", "placed_share_percent": "100"}]},
        )
        assert resp.status_code == 409

    async def test_a_layer_panel_over_100_percent_blocks_validation(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(
            client,
            object_store,
            session,
            layers=_STACK,
            layer_panels={2: [("Reinsurer Delta", "70"), ("Reinsurer Echo", "70")]},
        )
        # the panel PUT succeeds row-by-row; validate is where the 140% panel is caught
        detail = (await client.get(f"/treaties/{golden.treaty_id}")).json()
        assert detail["current_version"]["status"] == "needs_validation"

        resp = await client.post(
            f"/treaties/{golden.treaty_id}/versions/{golden.version_id}/validate"
        )
        assert resp.status_code == 422
        assert "layer 2" in resp.json()["detail"].lower()

    async def test_clearing_a_layer_panel_falls_back_to_the_programme_panel(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session, layers=_STACK)
        base = f"/treaties/{golden.treaty_id}/versions"
        # a fresh version can take a panel, then have it cleared
        v2 = (
            await client.post(
                f"/treaties/{golden.treaty_id}/versions",
                json={"note": "endorsement", "source_document_id": None},
            )
        ).json()
        v2_id = v2["current_version"]["id"]
        await client.put(
            f"{base}/{v2_id}/layers/2/participations",
            json={"panel": [{"reinsurer_name": "Reinsurer Delta", "placed_share_percent": "100"}]},
        )
        detail = (await client.get(f"/treaties/{golden.treaty_id}")).json()
        assert len(detail["current_version"]["layers"][1]["participations"]) == 1

        await client.put(f"{base}/{v2_id}/layers/2/participations", json={"panel": []})
        detail = (await client.get(f"/treaties/{golden.treaty_id}")).json()
        assert detail["current_version"]["layers"][1]["participations"] == []
