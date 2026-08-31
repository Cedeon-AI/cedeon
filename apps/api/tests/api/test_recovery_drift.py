"""Auto-recalculation on claim development: a confirmed recovery whose number
moves because more claims landed is *drift* — flagged, surfaced on the worklist,
and cleared only by a human review. No AI, pure deterministic recompute."""

from __future__ import annotations

import csv
import io

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.audit import AuditEvent
from tests.support.losses import GOLDEN_EVENT_IDENTIFIER, GOLDEN_HEADER, GOLDEN_MAPPING
from tests.support.scenario import confirmed_recovery_candidate

pytestmark = pytest.mark.db


def _extra_claims_csv() -> bytes:
    """Two more hurricane claims on the same event: +USD 5,000,000 gross."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(GOLDEN_HEADER)
    for claim, paid, reserve in (
        ("CLM-011", "1500000.00", "500000.00"),
        ("CLM-012", "2400000.00", "600000.00"),
    ):
        w.writerow(
            [
                claim,
                GOLDEN_EVENT_IDENTIFIER,
                "2027-09-17",
                "2027-09-30",
                paid,
                reserve,
                f"{float(paid) + float(reserve):.2f}",
                "USD",
                "Wind",
                "Volusia, FL",
            ]
        )
    return buf.getvalue().encode()


async def _commit_extra(client: AsyncClient, event_id: str) -> dict:
    uploaded = (
        await client.post(
            "/loss-imports", files={"file": ("extra.csv", _extra_claims_csv(), "text/csv")}
        )
    ).json()
    await client.post(f"/loss-imports/{uploaded['id']}/mapping", json={"mapping": GOLDEN_MAPPING})
    return (
        await client.post(
            f"/loss-imports/{uploaded['id']}/commit", json={"loss_event_id": event_id}
        )
    ).json()


class TestDrift:
    async def test_new_claims_drift_a_confirmed_recovery(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        event_id = (await client.get(f"/recovery-candidates/{candidate_id}")).json()["candidate"][
            "loss_event_id"
        ]

        result = await _commit_extra(client, event_id)
        assert result["recoveries_drifted"] == 1

        detail = (await client.get(f"/recovery-candidates/{candidate_id}")).json()
        cand = detail["candidate"]
        assert cand["status"] == "needs_review"  # reverted from confirmed
        assert cand["drifted_at"] is not None
        assert cand["pre_drift_recovery"] == "8700000.00"
        # 63.7M gross - 50M attach = 13.7M, under the 20M limit
        assert detail["current_calculation"]["layer_recovery"] == "13700000.00"

    async def test_drift_shows_on_the_worklist_and_clears_on_review(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        event_id = (await client.get(f"/recovery-candidates/{candidate_id}")).json()["candidate"][
            "loss_event_id"
        ]
        await _commit_extra(client, event_id)

        items = (await client.get("/worklist")).json()["items"]
        drift = [i for i in items if i["kind"] == "recovery_drift"]
        assert len(drift) == 1
        assert "8700000.00 to 13700000.00" in drift[0]["detail"]
        assert drift[0]["amount"] == "13700000.00"
        # a drifted candidate is not also listed as a plain review
        assert [i for i in items if i["kind"] == "recovery_review"] == []

        # a human re-reviews → drift cleared
        await client.post(
            f"/recovery-candidates/{candidate_id}/review", json={"decision": "confirm"}
        )
        cand = (await client.get(f"/recovery-candidates/{candidate_id}")).json()["candidate"]
        assert cand["drifted_at"] is None
        assert cand["pre_drift_recovery"] is None
        items = (await client.get("/worklist")).json()["items"]
        assert [i for i in items if i["kind"] == "recovery_drift"] == []

    async def test_drift_is_recorded_on_the_audit_log_as_a_system_action(
        self, client: AsyncClient, object_store, session
    ) -> None:
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        event_id = (await client.get(f"/recovery-candidates/{candidate_id}")).json()["candidate"][
            "loss_event_id"
        ]
        await _commit_extra(client, event_id)

        rows = (
            await session.execute(
                select(AuditEvent.action, AuditEvent.actor_type).order_by(AuditEvent.occurred_at)
            )
        ).all()
        drifted = [r for r in rows if r.action == "recovery_candidate.drifted"]
        assert len(drifted) == 1
        assert drifted[0].actor_type.value == "system"

    async def test_a_commit_that_does_not_move_the_number_is_not_drift(
        self, client: AsyncClient, object_store, session
    ) -> None:
        # confirm, then commit an import that adds nothing new to the event
        _, candidate_id = await confirmed_recovery_candidate(client, object_store, session)
        event_id = (await client.get(f"/recovery-candidates/{candidate_id}")).json()["candidate"][
            "loss_event_id"
        ]
        empty = io.StringIO()
        w = csv.writer(empty)
        w.writerow(GOLDEN_HEADER)
        w.writerow(
            [
                "CLM-011",
                GOLDEN_EVENT_IDENTIFIER,
                "2027-09-17",
                "2027-09-30",
                "0.00",
                "0.00",
                "0.00",
                "USD",
                "Wind",
                "Volusia, FL",
            ]
        )
        uploaded = (
            await client.post(
                "/loss-imports", files={"file": ("z.csv", empty.getvalue().encode(), "text/csv")}
            )
        ).json()
        await client.post(
            f"/loss-imports/{uploaded['id']}/mapping", json={"mapping": GOLDEN_MAPPING}
        )
        result = (
            await client.post(
                f"/loss-imports/{uploaded['id']}/commit", json={"loss_event_id": event_id}
            )
        ).json()
        assert result["recoveries_drifted"] == 0
        cand = (await client.get(f"/recovery-candidates/{candidate_id}")).json()["candidate"]
        assert cand["status"] == "confirmed"
        assert cand["drifted_at"] is None
