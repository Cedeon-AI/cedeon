"""The hours-clause occurrence proposal is assistive — it groups the claims and
leaves the decision to a human."""

from __future__ import annotations

import csv
import io

import pytest
from httpx import AsyncClient

from tests.support.auth import register
from tests.support.scenario import committed_hurricane_event

pytestmark = pytest.mark.db


async def _import_into(
    client: AsyncClient, event_id: str, rows: list[tuple[str, str, str]]
) -> None:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Claim", "Date", "Incurred", "Ccy"])
    for cid, date, amount in rows:
        w.writerow([cid, date, amount, "USD"])
    uploaded = (
        await client.post(
            "/loss-imports", files={"file": ("c.csv", buf.getvalue().encode(), "text/csv")}
        )
    ).json()
    await client.post(
        f"/loss-imports/{uploaded['id']}/mapping",
        json={
            "mapping": {
                "claim_id": "Claim",
                "date_of_loss": "Date",
                "gross_incurred": "Incurred",
                "currency": "Ccy",
            }
        },
    )
    await client.post(f"/loss-imports/{uploaded['id']}/commit", json={"loss_event_id": event_id})


class TestOccurrenceProposal:
    async def test_the_golden_hurricane_is_one_occurrence(
        self, client: AsyncClient, object_store, session
    ) -> None:
        await register(client)
        event_id = await committed_hurricane_event(client)
        proposal = (await client.get(f"/loss-events/{event_id}/occurrence-proposal")).json()
        assert proposal["hours_source"] == "peril_default"
        assert proposal["hours"] == 168
        assert not proposal["splits_the_event"]
        assert proposal["occurrences"][0]["claim_count"] == 10
        assert proposal["occurrences"][0]["gross_incurred"] == "58700000.00"

    async def test_claims_across_two_storms_split_under_a_72_hour_clause(
        self, client: AsyncClient, object_store, session
    ) -> None:
        await register(client)
        event = (
            await client.post(
                "/loss-events",
                json={"name": "Twin storms", "peril": "Windstorm", "hours_clause_hours": 72},
            )
        ).json()
        await _import_into(
            client,
            event["id"],
            [
                ("S-1", "2027-06-01", "10000000"),
                ("S-2", "2027-06-02", "8000000"),
                ("S-3", "2027-06-10", "12000000"),
                ("S-4", "2027-06-11", "5000000"),
            ],
        )
        proposal = (await client.get(f"/loss-events/{event['id']}/occurrence-proposal")).json()
        assert proposal["hours_source"] == "treaty"
        assert proposal["window_days"] == 3
        assert proposal["splits_the_event"]
        assert [o["claim_count"] for o in proposal["occurrences"]] == [2, 2]
        assert [o["gross_incurred"] for o in proposal["occurrences"]] == [
            "18000000.00",
            "17000000.00",
        ]
        assert proposal["occurrences"][1]["start_date"] == "2027-06-10"
