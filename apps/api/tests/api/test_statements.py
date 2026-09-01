"""Reinsurer-statement reconciliation: submit a reinsurer's figures, Cedeon checks
each line against what it holds, and the discrepancies land on the queue."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.support.scenario import confirmed_recovery_candidate

pytestmark = pytest.mark.db


async def _recoverables(client: AsyncClient, candidate_id: str) -> list[dict]:
    return (await client.post(f"/recovery-candidates/{candidate_id}/recoverables")).json()[
        "recoverables"
    ]


class TestStatementReconciliation:
    async def test_a_matching_line_reconciles_clean(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        recs = await _recoverables(client, candidate_id)
        alpha = next(r for r in recs if r["expected_amount"] == "4350000.00")
        # agree it at the expected figure
        await client.post(f"/recoverables/{alpha['id']}", json={"status": "agreed"})
        await client.post(f"/recoverables/{alpha['id']}", json={"agree": "4350000.00"})

        statement = (
            await client.post(
                "/reinsurer-statements",
                json={
                    "label": "Alpha Q3 account",
                    "currency": "USD",
                    "lines": [
                        {"reinsurer_name": "Reinsurer Alpha", "their_agreed": "4350000.00"}
                    ],
                },
            )
        ).json()
        assert statement["open_discrepancies"] == 0
        assert statement["lines"][0]["findings"][0]["kind"] == "clean"
        assert statement["lines"][0]["resolved"] is True

    async def test_a_short_agreement_is_a_discrepancy_on_the_queue(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        await _recoverables(client, candidate_id)

        statement = (
            await client.post(
                "/reinsurer-statements",
                json={
                    "label": "Beta statement",
                    "currency": "USD",
                    "lines": [
                        {"reinsurer_name": "Reinsurer Beta", "their_agreed": "2000000.00"}
                    ],
                },
            )
        ).json()
        assert statement["open_discrepancies"] == 1
        line = statement["lines"][0]
        assert line["findings"][0]["kind"] == "their_agreed_below_expected"
        assert line["matched_recoverable_id"] is not None

        items = (await client.get("/worklist")).json()["items"]
        disc = [i for i in items if i["kind"] == "statement_discrepancy"]
        assert len(disc) == 1
        assert disc[0]["category"] == "exception"
        assert disc[0]["href"] == f"/statements/{statement['id']}"
        assert disc[0]["amount"] == "610000.00"  # 2.61M expected less 2.00M stated

        # resolve it → clears from the queue
        await client.post(
            f"/reinsurer-statements/{statement['id']}/lines/1/resolve"
        )
        items = (await client.get("/worklist")).json()["items"]
        assert not [i for i in items if i["kind"] == "statement_discrepancy"]

    async def test_an_unknown_reinsurer_is_flagged_no_match(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        await _recoverables(client, candidate_id)
        statement = (
            await client.post(
                "/reinsurer-statements",
                json={
                    "label": "Mystery",
                    "currency": "USD",
                    "lines": [{"reinsurer_name": "Reinsurer Zeta", "their_paid": "1000000"}],
                },
            )
        ).json()
        assert statement["lines"][0]["findings"][0]["kind"] == "no_match"
        assert statement["lines"][0]["matched_recoverable_id"] is None

    async def test_statements_list(self, client: AsyncClient, object_store, session) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        await _recoverables(client, candidate_id)
        await client.post(
            "/reinsurer-statements",
            json={
                "label": "S1",
                "currency": "USD",
                "lines": [{"reinsurer_name": "Reinsurer Beta", "their_agreed": "2000000"}],
            },
        )
        listing = (await client.get("/reinsurer-statements")).json()["statements"]
        assert len(listing) == 1
        assert listing[0]["open_discrepancies"] == 1
        assert listing[0]["line_count"] == 1
