"""Cedeon proposes a recovery when a validated treaty looks like it responds to a
loss event nobody has opened one for. Deterministic screen; a human promotes it."""

from __future__ import annotations

import csv
import io

import pytest
from httpx import AsyncClient

from tests.support.scenario import committed_hurricane_event, validated_golden_treaty

pytestmark = pytest.mark.db


class TestSuggestions:
    async def test_the_golden_event_is_suggested_against_the_golden_treaty(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        await committed_hurricane_event(client)

        body = (await client.get("/recovery-candidates/suggestions")).json()
        assert len(body["suggestions"]) == 1
        s = body["suggestions"][0]
        assert s["treaty_id"] == golden.treaty_id
        assert s["indicative_recovery"] == "8700000.00"
        assert s["gross"] == "58700000.00"

        items = (await client.get("/worklist")).json()["items"]
        suggested = [i for i in items if i["kind"] == "suggested_recovery"]
        assert len(suggested) == 1
        assert suggested[0]["amount"] == "8700000.00"
        assert suggested[0]["href"] == "/recovery-candidates/new"

    async def test_opening_the_recovery_clears_the_suggestion(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        event_id = await committed_hurricane_event(client)
        assert (
            len((await client.get("/recovery-candidates/suggestions")).json()["suggestions"]) == 1
        )

        await client.post(
            "/recovery-candidates",
            json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
        )
        assert (await client.get("/recovery-candidates/suggestions")).json()["suggestions"] == []
        items = (await client.get("/worklist")).json()["items"]
        assert [i for i in items if i["kind"] == "suggested_recovery"] == []

    async def test_an_event_below_the_attachment_is_not_suggested(
        self, client: AsyncClient, object_store, session
    ) -> None:
        await validated_golden_treaty(client, object_store, session)

        small = io.StringIO()
        w = csv.writer(small)
        w.writerow(["Claim Ref", "Event", "Loss Date", "Incurred", "Ccy"])
        w.writerow(["S-1", "SMALL-2027", "2027-06-01", "2000000.00", "USD"])
        uploaded = (
            await client.post(
                "/loss-imports", files={"file": ("s.csv", small.getvalue().encode(), "text/csv")}
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
        await client.post(
            f"/loss-imports/{uploaded['id']}/commit", json={"event_name": "Small One"}
        )

        assert (await client.get("/recovery-candidates/suggestions")).json()["suggestions"] == []

    async def test_tenant_scoped(
        self, client: AsyncClient, client_factory, object_store, session
    ) -> None:
        await validated_golden_treaty(client, object_store, session)
        await committed_hurricane_event(client)
        assert (
            len((await client.get("/recovery-candidates/suggestions")).json()["suggestions"]) == 1
        )

        from tests.support.auth import register

        other = await client_factory()
        await register(other, email="other@carrier.example", org="Other Carrier")
        assert (await other.get("/recovery-candidates/suggestions")).json()["suggestions"] == []
