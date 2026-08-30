"""Recovery candidate slice: validated treaty + committed loss event →
deterministic calculation → reviewable candidate. No AI (ADR-0010)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.audit import AuditEvent
from tests.support.auth import register
from tests.support.scenario import committed_hurricane_event, validated_golden_treaty

pytestmark = pytest.mark.db

GOLDEN_LAYER_RECOVERY = Decimal("8700000.00")
GOLDEN_ALLOCATIONS = {
    "Reinsurer Alpha": Decimal("4350000.00"),
    "Reinsurer Beta": Decimal("2610000.00"),
    "Reinsurer Gamma": Decimal("1740000.00"),
}


async def _candidate(client: AsyncClient, object_store, session) -> dict:
    golden = await validated_golden_treaty(client, object_store, session)
    event_id = await committed_hurricane_event(client)
    resp = await client.post(
        "/recovery-candidates",
        json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestGoldenPath:
    async def test_create_produces_the_golden_recovery(
        self, client: AsyncClient, object_store, session
    ) -> None:
        candidate = await _candidate(client, object_store, session)

        assert candidate["status"] == "needs_review"
        assert candidate["currency"] == "USD"
        assert candidate["currency_mismatch"] is False
        assert Decimal(candidate["gross_event_incurred"]) == Decimal("58700000.00")
        assert candidate["current_calculation_id"]

        detail = (await client.get(f"/recovery-candidates/{candidate['id']}")).json()
        calc = detail["current_calculation"]
        assert Decimal(calc["layer_recovery"]) == GOLDEN_LAYER_RECOVERY
        assert Decimal(calc["amount_above_attachment"]) == GOLDEN_LAYER_RECOVERY
        assert Decimal(calc["cedent_retention"]) == Decimal("0.00")
        assert Decimal(calc["total_ceded"]) == GOLDEN_LAYER_RECOVERY
        assert calc["engine_version"]
        assert len(calc["input_hash"]) == 64
        assert [s["label"] for s in calc["trace"]] == [
            "gross event loss",
            "amount above attachment",
            "layer recovery",
        ]

        allocs = {
            a["reinsurer_name"]: Decimal(a["allocated_recovery"]) for a in calc["allocations"]
        }
        assert allocs == GOLDEN_ALLOCATIONS
        assert sum(allocs.values()) == GOLDEN_LAYER_RECOVERY
        assert len(detail["calculations"]) == 1
        assert detail["reviews"] == []

    async def test_creation_is_idempotent_for_the_same_inputs(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        event_id = await committed_hurricane_event(client)
        body = {"treaty_id": golden.treaty_id, "loss_event_id": event_id}
        first = (await client.post("/recovery-candidates", json=body)).json()
        second = (await client.post("/recovery-candidates", json=body)).json()
        assert first["id"] == second["id"]
        listed = (await client.get("/recovery-candidates")).json()["candidates"]
        assert len(listed) == 1

    async def test_recalculate_is_a_noop_when_inputs_are_unchanged(
        self, client: AsyncClient, object_store, session
    ) -> None:
        candidate = await _candidate(client, object_store, session)
        resp = await client.post(f"/recovery-candidates/{candidate['id']}/recalculate")
        assert resp.status_code == 200
        assert resp.json()["current_calculation_id"] == candidate["current_calculation_id"]
        detail = (await client.get(f"/recovery-candidates/{candidate['id']}")).json()
        assert len(detail["calculations"]) == 1

    async def test_committing_more_losses_recalculates_and_reverts_confirmation(
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
        await client.post(
            f"/recovery-candidates/{candidate['id']}/review", json={"decision": "confirm"}
        )

        # A second import committed into the same event adds $2M of incurred.
        extra_csv = (
            b"Claim Ref,Event,Loss Date,Reported,Paid,Reserve,Incurred,Ccy,Peril,Location\n"
            b"CLM-011,HURR-DEMO-2027,2027-09-17,2027-09-28,"
            b"1500000.00,500000.00,2000000.00,USD,Wind,Key West\n"
        )
        up = (
            await client.post("/loss-imports", files={"file": ("extra.csv", extra_csv, "text/csv")})
        ).json()
        await client.post(
            f"/loss-imports/{up['id']}/mapping",
            json={
                "mapping": {
                    "claim_id": "Claim Ref",
                    "loss_event_identifier": "Event",
                    "date_of_loss": "Loss Date",
                    "reported_date": "Reported",
                    "gross_paid": "Paid",
                    "gross_case_reserve": "Reserve",
                    "gross_incurred": "Incurred",
                    "currency": "Ccy",
                }
            },
        )
        await client.post(f"/loss-imports/{up['id']}/commit", json={"loss_event_id": event_id})

        recalced = (await client.post(f"/recovery-candidates/{candidate['id']}/recalculate")).json()
        assert recalced["status"] == "needs_review"  # confirmation was reverted
        assert recalced["current_calculation_id"] != candidate["current_calculation_id"]
        assert Decimal(recalced["gross_event_incurred"]) == Decimal("60700000.00")

        detail = (await client.get(f"/recovery-candidates/{candidate['id']}")).json()
        assert len(detail["calculations"]) == 2
        # 60.7M gross → 10.7M above 50M attachment, capped at the 20M limit
        assert Decimal(detail["current_calculation"]["layer_recovery"]) == Decimal("10700000.00")


class TestReview:
    async def test_confirm_and_reject_transitions(
        self, client: AsyncClient, object_store, session
    ) -> None:
        candidate = await _candidate(client, object_store, session)
        cid = candidate["id"]

        confirmed = (
            await client.post(
                f"/recovery-candidates/{cid}/review",
                json={"decision": "confirm", "reason": "ties to the treaty and the schedule"},
            )
        ).json()
        assert confirmed["status"] == "confirmed"
        assert confirmed["reviewed_at"]

        # already confirmed → further review is a conflict
        assert (
            await client.post(f"/recovery-candidates/{cid}/review", json={"decision": "reject"})
        ).status_code == 409

        detail = (await client.get(f"/recovery-candidates/{cid}")).json()
        assert [r["decision"] for r in detail["reviews"]] == ["confirm"]

    async def test_edit_decision_is_rejected(
        self, client: AsyncClient, object_store, session
    ) -> None:
        candidate = await _candidate(client, object_store, session)
        resp = await client.post(
            f"/recovery-candidates/{candidate['id']}/review", json={"decision": "edit"}
        )
        assert resp.status_code == 422

    async def test_request_info_keeps_the_candidate_open(
        self, client: AsyncClient, object_store, session
    ) -> None:
        candidate = await _candidate(client, object_store, session)
        resp = await client.post(
            f"/recovery-candidates/{candidate['id']}/review",
            json={"decision": "request_info", "reason": "need the loss adjuster report"},
        )
        assert resp.json()["status"] == "needs_review"


class TestGuards:
    async def test_needs_a_validated_treaty(self, client: AsyncClient) -> None:
        await register(client, email="early@carrier.example")
        cedent = (await client.post("/cedents", json={"name": "C"})).json()
        program = (
            await client.post(
                "/programs", json={"cedent_id": cedent["id"], "name": "P", "treaty_year": 2027}
            )
        ).json()
        treaty = (
            await client.post("/treaties", json={"program_id": program["id"], "name": "T"})
        ).json()
        event = (await client.post("/loss-events", json={"name": "Some Event"})).json()
        resp = await client.post(
            "/recovery-candidates",
            json={"treaty_id": treaty["id"], "loss_event_id": event["id"]},
        )
        assert resp.status_code == 409
        assert "validated" in resp.text

    async def test_event_with_no_losses_is_rejected(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)
        event = (await client.post("/loss-events", json={"name": "Empty"})).json()
        resp = await client.post(
            "/recovery-candidates",
            json={"treaty_id": golden.treaty_id, "loss_event_id": event["id"]},
        )
        assert resp.status_code == 409
        assert "no committed underlying losses" in resp.text

    async def test_list_filters_by_status(self, client: AsyncClient, object_store, session) -> None:
        candidate = await _candidate(client, object_store, session)
        await client.post(
            f"/recovery-candidates/{candidate['id']}/review", json={"decision": "confirm"}
        )
        needs = (await client.get("/recovery-candidates?status=needs_review")).json()["candidates"]
        confirmed = (await client.get("/recovery-candidates?status=confirmed")).json()["candidates"]
        assert needs == []
        assert [c["id"] for c in confirmed] == [candidate["id"]]

    async def test_audit_trail(self, client: AsyncClient, object_store, session) -> None:
        candidate = await _candidate(client, object_store, session)
        await client.post(
            f"/recovery-candidates/{candidate['id']}/review", json={"decision": "confirm"}
        )
        actions = {
            row.action for row in (await session.execute(select(AuditEvent))).scalars().all()
        }
        assert {"recovery_candidate.created", "recovery_candidate.reviewed"} <= actions


class TestCurrencyMismatch:
    async def test_losses_in_another_currency_are_flagged_and_excluded(
        self, client: AsyncClient, object_store, session
    ) -> None:
        golden = await validated_golden_treaty(client, object_store, session)

        csv = (
            b"claim,event,dol,paid,reserve,ccy\n"
            b"USD-1,MIXED-EVT,2027-09-14,30000000.00,0.00,USD\n"
            b"EUR-1,MIXED-EVT,2027-09-14,9000000.00,0.00,EUR\n"
        )
        up = (await client.post("/loss-imports", files={"file": ("m.csv", csv, "text/csv")})).json()
        await client.post(
            f"/loss-imports/{up['id']}/mapping",
            json={
                "mapping": {
                    "claim_id": "claim",
                    "loss_event_identifier": "event",
                    "date_of_loss": "dol",
                    "gross_paid": "paid",
                    "gross_case_reserve": "reserve",
                    "currency": "ccy",
                }
            },
        )
        commit = (
            await client.post(f"/loss-imports/{up['id']}/commit", json={"event_name": "Mixed"})
        ).json()
        event_id = commit["loss_event_ids"][0]

        candidate = (
            await client.post(
                "/recovery-candidates",
                json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
            )
        ).json()
        assert candidate["currency_mismatch"] is True
        # only the USD 30M loss counts → below the 50M attachment → zero recovery
        assert Decimal(candidate["gross_event_incurred"]) == Decimal("30000000.00")
        detail = (await client.get(f"/recovery-candidates/{candidate['id']}")).json()
        assert Decimal(detail["current_calculation"]["layer_recovery"]) == Decimal("0.00")


class TestTenantIsolation:
    async def test_other_org_cannot_see_the_candidate(
        self, client_factory, object_store, session
    ) -> None:
        a = await client_factory()
        b = await client_factory()
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

        await register(b, org="Carrier B", email="b@b.example")
        assert (await b.get(f"/recovery-candidates/{candidate['id']}")).status_code == 404
        assert (await b.get("/recovery-candidates")).json()["candidates"] == []
        assert (
            await b.post(
                f"/recovery-candidates/{candidate['id']}/review", json={"decision": "confirm"}
            )
        ).status_code == 404
