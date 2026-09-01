"""Reconciliation intelligence (the first Exception module): Cedeon's calculated
figure vs the human-entered agreed / billed / collected — code finds the gap."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.support.scenario import confirmed_recovery_candidate

pytestmark = pytest.mark.db


async def _biggest_leg(client: AsyncClient, candidate_id: str) -> dict:
    legs = (await client.post(f"/recovery-candidates/{candidate_id}/recoverables")).json()[
        "recoverables"
    ]
    return max(legs, key=lambda i: i["expected_amount"])  # the 4,350,000 leg


class TestReconciliation:
    async def test_a_clean_leg_has_no_findings(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        leg = await _biggest_leg(client, candidate_id)
        assert leg["reconciliation"] == []

    async def test_agreed_below_expected_surfaces_on_the_leg_and_the_worklist(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        leg = await _biggest_leg(client, candidate_id)

        updated = (
            await client.post(
                f"/recoverables/{leg['id']}",
                json={"status": "agreed", "agreed_amount": "4000000.00"},
            )
        ).json()
        assert len(updated["reconciliation"]) == 1
        assert updated["reconciliation"][0]["kind"] == "agreed_below_expected"
        assert updated["reconciliation"][0]["gap"] == "350000.00"

        items = (await client.get("/worklist")).json()["items"]
        recon = [i for i in items if i["kind"] == "reconciliation_mismatch"]
        assert len(recon) == 1
        assert recon[0]["category"] == "exception"
        assert recon[0]["amount"] == "350000.00"
        assert recon[0]["href"].endswith("?section=collection")

    async def test_marked_collected_but_short(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        leg = await _biggest_leg(client, candidate_id)

        await client.post(
            f"/recoverables/{leg['id']}",
            json={"status": "agreed", "agreed_amount": "4350000.00"},
        )
        await client.post(f"/recoverables/{leg['id']}", json={"status": "billed"})
        # collect less than billed, then force the status to collected
        await client.post(f"/recoverables/{leg['id']}", json={"collect": "4100000.00"})
        updated = (
            await client.post(f"/recoverables/{leg['id']}", json={"status": "collected"})
        ).json()

        kinds = {f["kind"] for f in updated["reconciliation"]}
        assert "collected_short" in kinds

    async def test_a_partial_payment_mid_flow_is_not_an_exception(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        leg = await _biggest_leg(client, candidate_id)
        await client.post(
            f"/recoverables/{leg['id']}",
            json={"status": "agreed", "agreed_amount": "4350000.00"},
        )
        await client.post(f"/recoverables/{leg['id']}", json={"status": "billed"})
        updated = (
            await client.post(f"/recoverables/{leg['id']}", json={"collect": "1000000.00"})
        ).json()
        assert updated["status"] == "billed"  # not fully collected
        assert updated["reconciliation"] == []
