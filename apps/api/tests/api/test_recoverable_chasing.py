"""Every recoverable carries a deterministic next-action hint — where to push."""

from __future__ import annotations

import datetime as dt

import pytest
from httpx import AsyncClient

from tests.support.scenario import confirmed_recovery_candidate

pytestmark = pytest.mark.db


class TestChaseHint:
    async def test_a_fresh_leg_says_notify(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        legs = (await client.post(f"/recovery-candidates/{candidate_id}/recoverables")).json()[
            "recoverables"
        ]
        assert {leg["next_action"] for leg in legs} == {"notify"}
        assert all(leg["days_in_status"] >= 0 for leg in legs)

    async def test_a_stale_overdue_leg_is_an_urgent_chase(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        legs = (await client.post(f"/recovery-candidates/{candidate_id}/recoverables")).json()[
            "recoverables"
        ]
        big = max(legs, key=lambda leg: leg["expected_amount"])
        await client.post(
            f"/recoverables/{big['id']}",
            json={
                "status": "billed",
                "due_date": (dt.date.today() - dt.timedelta(days=20)).isoformat(),
            },
        )
        updated = (await client.get(f"/recovery-candidates/{candidate_id}/recoverables")).json()[
            "recoverables"
        ]
        leg = next(x for x in updated if x["id"] == big["id"])
        assert leg["next_action"] == "chase_payment"
        assert leg["next_action_urgent"] is True
        assert "overdue" in leg["next_action_text"]

        # the worklist overdue item carries the same guidance
        items = (await client.get("/worklist")).json()["items"]
        overdue = next(i for i in items if i["kind"] == "recoverable_overdue")
        assert "chase payment" in overdue["detail"].lower()
