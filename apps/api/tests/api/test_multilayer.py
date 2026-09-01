"""A treaty can be a stack of XOL layers, and one loss event opens a recovery
on every layer that responds."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.support.scenario import committed_hurricane_event, validated_golden_treaty

pytestmark = pytest.mark.db

# bottom → top; the golden $58.7M event pierces all three
_STACK = [("5000000", "5000000"), ("20000000", "20000000"), ("50000000", "50000000")]


class TestValidateStack:
    async def test_the_layer_stack_is_sorted_and_frozen(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session, layers=_STACK)
        detail = (await client.get(f"/treaties/{golden.treaty_id}")).json()
        layers = detail["current_version"]["layers"]
        assert [(x["attachment"], x["limit"]) for x in layers] == [
            ("5000000.00", "5000000.00"),
            ("20000000.00", "20000000.00"),
            ("50000000.00", "50000000.00"),
        ]
        assert [x["layer_no"] for x in layers] == [1, 2, 3]

        # frozen once validated
        resp = await client.put(
            f"/treaties/{golden.treaty_id}/versions/{golden.version_id}/layers",
            json={"currency": "USD", "layers": [{"attachment": "1", "limit": "1"}]},
        )
        assert resp.status_code == 409


class TestMultiLayerRecovery:
    async def test_one_event_opens_a_recovery_on_every_responding_layer(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session, layers=_STACK)
        event_id = await committed_hurricane_event(client)

        await client.post(
            "/recovery-candidates",
            json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
        )
        candidates = (await client.get("/recovery-candidates")).json()["candidates"]
        assert len(candidates) == 3

        by_layer = {}
        for c in candidates:
            detail = (await client.get(f"/recovery-candidates/{c['id']}")).json()
            calc = detail["current_calculation"]
            by_layer[calc["attachment"]] = calc["layer_recovery"]
        # L1: min(58.7-5, 5)=5M · L2: min(58.7-20, 20)=20M · L3: min(58.7-50, 50)=8.7M
        assert by_layer == {
            "5000000.00": "5000000.00",
            "20000000.00": "20000000.00",
            "50000000.00": "8700000.00",
        }

    async def test_a_small_event_opens_only_the_bottom_layer(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session, layers=_STACK)
        import csv
        import io

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Claim Ref", "Event", "Loss Date", "Incurred", "Ccy"])
        w.writerow(["S-1", "SMALL", "2027-06-01", "8000000.00", "USD"])  # pierces L1 only
        uploaded = (
            await client.post(
                "/loss-imports", files={"file": ("s.csv", buf.getvalue().encode(), "text/csv")}
            )
        ).json()
        await client.post(
            f"/loss-imports/{uploaded['id']}/mapping",
            json={
                "mapping": {
                    "claim_id": "Claim Ref",
                    "loss_event_identifier": "Event",
                    "date_of_loss": "Loss Date",
                    "gross_incurred": "Incurred",
                    "currency": "Ccy",
                }
            },
        )
        commit = (
            await client.post(
                f"/loss-imports/{uploaded['id']}/commit", json={"event_name": "Small"}
            )
        ).json()

        await client.post(
            "/recovery-candidates",
            json={"treaty_id": golden.treaty_id, "loss_event_id": commit["loss_event_ids"][0]},
        )
        candidates = (await client.get("/recovery-candidates")).json()["candidates"]
        assert len(candidates) == 1
        detail = (await client.get(f"/recovery-candidates/{candidates[0]['id']}")).json()
        assert detail["current_calculation"]["layer_recovery"] == "3000000.00"  # min(8-5, 5)

    async def test_suggestions_screen_every_layer(
        self, client: AsyncClient, object_store, session
    ) -> None:
        await validated_golden_treaty(client, object_store, session, layers=_STACK)
        await committed_hurricane_event(client)
        suggestions = (await client.get("/recovery-candidates/suggestions")).json()["suggestions"]
        # all three layers respond to the golden event
        assert len(suggestions) == 3
        assert sorted(s["indicative_recovery"] for s in suggestions) == [
            "20000000.00",
            "5000000.00",
            "8700000.00",
        ]


class TestProgrammeGrouping:
    async def test_the_tower_groups_as_one_programme_and_the_detail_links_siblings(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session, layers=_STACK)
        event_id = await committed_hurricane_event(client)
        await client.post(
            "/recovery-candidates",
            json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
        )

        listing = (await client.get("/recovery-candidates")).json()
        assert len(listing["candidates"]) == 3
        assert len(listing["programmes"]) == 1
        prog = listing["programmes"][0]
        assert prog["loss_event_name"] == "Hurricane Demo 2027"
        assert [c["layer_no"] for c in prog["candidates"]] == [1, 2, 3]
        assert [c["layer_recovery"] for c in prog["candidates"]] == [
            "5000000.00",
            "20000000.00",
            "8700000.00",
        ]
        # every row carries its programme context
        assert all(c["treaty_name"] for c in listing["candidates"])

        bottom = next(c for c in prog["candidates"] if c["layer_no"] == 1)
        detail = (await client.get(f"/recovery-candidates/{bottom['id']}")).json()
        assert [s["layer_no"] for s in detail["siblings"]] == [2, 3]
        assert detail["candidate"]["layer_recovery"] == "5000000.00"

    async def test_a_single_layer_recovery_is_not_a_programme(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        event_id = await committed_hurricane_event(client)
        await client.post(
            "/recovery-candidates",
            json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
        )
        listing = (await client.get("/recovery-candidates")).json()
        assert listing["programmes"] == []
        assert listing["candidates"][0]["layer_recovery"] == "8700000.00"
