"""Loss import vertical slice: CSV upload → column mapping → validation report →
commit to immutable underlying losses grouped into a loss event."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.audit import AuditEvent
from tests.support.auth import register
from tests.support.losses import (
    GOLDEN_EVENT_IDENTIFIER,
    GOLDEN_GROSS_INCURRED,
    GOLDEN_MAPPING,
    golden_loss_csv,
    messy_loss_csv,
)

pytestmark = pytest.mark.db


async def _upload(client: AsyncClient, csv_bytes: bytes, *, filename: str = "losses.csv") -> dict:
    resp = await client.post(
        "/loss-imports",
        files={"file": (filename, csv_bytes, "text/csv")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _map(client: AsyncClient, import_id: str, mapping: dict[str, str]) -> dict:
    resp = await client.post(f"/loss-imports/{import_id}/mapping", json={"mapping": mapping})
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestGoldenPath:
    async def test_upload_map_commit_produces_the_demo_event(
        self, client: AsyncClient, session
    ) -> None:
        await register(client, email="loss.analyst@carrier.example")

        uploaded = await _upload(client, golden_loss_csv())
        assert uploaded["status"] == "uploaded"
        assert uploaded["row_count"] == 10
        assert uploaded["header_columns"][0] == "Claim Ref"

        detail = await _map(client, uploaded["id"], GOLDEN_MAPPING)
        report = detail["loss_import"]["report"]
        assert detail["loss_import"]["status"] == "validated"
        assert report["total_rows"] == 10
        assert report["errors"] == 0
        assert report["committable"] == 10
        assert report["currencies"] == ["USD"]
        assert report["distinct_events"] == [GOLDEN_EVENT_IDENTIFIER]
        assert report["gross_incurred_by_currency"] == {"USD": GOLDEN_GROSS_INCURRED}

        commit = await client.post(
            f"/loss-imports/{uploaded['id']}/commit",
            json={"event_name": "Hurricane Demo 2027"},
        )
        assert commit.status_code == 200, commit.text
        result = commit.json()
        assert result["committed"] == 10
        assert result["skipped"] == 0
        assert result["events_created"] == 1
        (event_id,) = result["loss_event_ids"]

        events = (await client.get("/loss-events")).json()["events"]
        assert len(events) == 1
        assert events[0]["name"] == "Hurricane Demo 2027"
        assert events[0]["event_identifier"] == GOLDEN_EVENT_IDENTIFIER
        assert events[0]["currency"] == "USD"
        assert events[0]["date_of_loss_from"] == "2027-09-14"
        assert events[0]["date_of_loss_to"] == "2027-09-16"
        assert events[0]["totals"] == [
            {"currency": "USD", "claim_count": 10, "gross_incurred": GOLDEN_GROSS_INCURRED}
        ]

        event = (await client.get(f"/loss-events/{event_id}")).json()
        assert len(event["losses"]) == 10
        total = sum(Decimal(loss["gross_incurred"]) for loss in event["losses"])
        assert total == Decimal(GOLDEN_GROSS_INCURRED)
        assert {loss["claim_id"] for loss in event["losses"]} == {
            f"CLM-{i:03d}" for i in range(1, 11)
        }
        assert all(loss["loss_import_id"] == uploaded["id"] for loss in event["losses"])

    async def test_commit_is_audited(self, client: AsyncClient, session) -> None:
        await register(client, email="audit.loss@carrier.example")
        uploaded = await _upload(client, golden_loss_csv())
        await _map(client, uploaded["id"], GOLDEN_MAPPING)
        await client.post(f"/loss-imports/{uploaded['id']}/commit", json={})

        actions = {
            row.action for row in (await session.execute(select(AuditEvent))).scalars().all()
        }
        assert {"loss_import.uploaded", "loss_import.mapped", "loss_import.committed"} <= actions


class TestValidationReport:
    async def test_messy_csv_surfaces_row_level_issues(self, client: AsyncClient) -> None:
        await register(client, email="messy@carrier.example")
        uploaded = await _upload(client, messy_loss_csv(), filename="messy.csv")

        detail = await _map(
            client,
            uploaded["id"],
            {
                "claim_id": "claim",
                "date_of_loss": "when",
                "reported_date": "reported",
                "gross_incurred": "incurred",
                "currency": "ccy",
            },
        )
        report = detail["loss_import"]["report"]
        assert report["total_rows"] == 7
        # rows 1 & 3 are a duplicate pair, row 4 bad date, row 5 negative, row 6 missing incurred
        assert report["errors"] == 5
        assert report["warnings"] == 1  # row 7: reported before loss
        assert report["ok"] == 1  # row 2 only
        assert set(report["currencies"]) == {"USD", "EUR"}

        rows = {r["row_number"]: r for r in detail["rows"]}
        assert rows[1]["status"] == "error"  # duplicate claim id
        assert rows[2]["status"] == "ok"
        assert rows[3]["status"] == "error"  # duplicate of row 1
        assert rows[7]["status"] == "warning"
        assert rows[2]["parsed"]["currency"] == "USD"
        assert rows[1]["parsed"]["currency"] == "USD"  # lowercased in source

    async def test_commit_before_mapping_is_rejected(self, client: AsyncClient) -> None:
        await register(client, email="early@carrier.example")
        uploaded = await _upload(client, golden_loss_csv())
        resp = await client.post(f"/loss-imports/{uploaded['id']}/commit", json={})
        assert resp.status_code == 409

    async def test_double_commit_is_rejected(self, client: AsyncClient) -> None:
        await register(client, email="twice@carrier.example")
        uploaded = await _upload(client, golden_loss_csv())
        await _map(client, uploaded["id"], GOLDEN_MAPPING)
        assert (
            await client.post(f"/loss-imports/{uploaded['id']}/commit", json={})
        ).status_code == 200
        assert (
            await client.post(f"/loss-imports/{uploaded['id']}/commit", json={})
        ).status_code == 409

    async def test_unknown_canonical_field_is_rejected(self, client: AsyncClient) -> None:
        await register(client, email="badmap@carrier.example")
        uploaded = await _upload(client, golden_loss_csv())
        resp = await client.post(
            f"/loss-imports/{uploaded['id']}/mapping",
            json={"mapping": {"not_a_field": "Claim Ref"}},
        )
        assert resp.status_code == 422

    async def test_mapping_to_missing_column_is_rejected(self, client: AsyncClient) -> None:
        await register(client, email="badcol@carrier.example")
        uploaded = await _upload(client, golden_loss_csv())
        resp = await client.post(
            f"/loss-imports/{uploaded['id']}/mapping",
            json={"mapping": {"claim_id": "Nonexistent Column"}},
        )
        assert resp.status_code == 422


class TestUpload:
    async def test_fields_endpoint_lists_canonical_schema(self, client: AsyncClient) -> None:
        await register(client, email="fields@carrier.example")
        fields = (await client.get("/loss-imports/fields")).json()["fields"]
        by_name = {f["field"]: f for f in fields}
        assert by_name["claim_id"]["required"] is True
        assert by_name["gross_incurred"]["required"] is False
        assert by_name["currency"]["kind"] == "currency"

    async def test_identical_bytes_are_deduplicated(self, client: AsyncClient) -> None:
        await register(client, email="dedup@carrier.example")
        first = await _upload(client, golden_loss_csv())
        second = await _upload(client, golden_loss_csv(), filename="again.csv")
        assert first["id"] == second["id"]
        assert len((await client.get("/loss-imports")).json()["imports"]) == 1

    async def test_empty_and_headerless_csvs_are_rejected(self, client: AsyncClient) -> None:
        await register(client, email="empty@carrier.example")
        assert (
            await client.post("/loss-imports", files={"file": ("e.csv", b"", "text/csv")})
        ).status_code == 422
        assert (
            await client.post(
                "/loss-imports", files={"file": ("h.csv", b"claim,date,ccy\n", "text/csv")}
            )
        ).status_code == 422

    async def test_content_streams_back_the_original_bytes(self, client: AsyncClient) -> None:
        await register(client, email="stream@carrier.example")
        csv_bytes = golden_loss_csv()
        uploaded = await _upload(client, csv_bytes)
        resp = await client.get(f"/loss-imports/{uploaded['id']}/content")
        assert resp.status_code == 200
        assert resp.content == csv_bytes

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/loss-imports", files={"file": ("l.csv", golden_loss_csv(), "text/csv")}
        )
        assert resp.status_code == 401


class TestLossEvents:
    async def test_manual_event_creation(self, client: AsyncClient) -> None:
        await register(client, email="manual@carrier.example")
        resp = await client.post(
            "/loss-events",
            json={"name": "Winter Storm Elliot", "catastrophe_code": "CAT-2027-04"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["name"] == "Winter Storm Elliot"
        assert body["totals"] == []
        assert body["peril"] is None
        assert body["hours_clause_hours"] is None

    async def test_event_records_the_occurrence_basis(self, client: AsyncClient) -> None:
        await register(client, email="basis@carrier.example")
        resp = await client.post(
            "/loss-events",
            json={
                "name": "Hurricane Béatrice",
                "peril": "Named windstorm",
                "hours_clause_hours": 168,
            },
        )
        assert resp.status_code == 201, resp.text
        event_id = resp.json()["id"]

        detail = (await client.get(f"/loss-events/{event_id}")).json()["event"]
        assert detail["peril"] == "Named windstorm"
        assert detail["hours_clause_hours"] == 168

        # a nonsense hours clause is rejected by the schema
        bad = await client.post("/loss-events", json={"name": "x", "hours_clause_hours": 99999})
        assert bad.status_code == 422

    async def test_commit_into_an_existing_event(self, client: AsyncClient) -> None:
        await register(client, email="existing@carrier.example")
        event = (await client.post("/loss-events", json={"name": "Hurricane Demo"})).json()

        uploaded = await _upload(client, golden_loss_csv())
        await _map(client, uploaded["id"], GOLDEN_MAPPING)
        result = (
            await client.post(
                f"/loss-imports/{uploaded['id']}/commit",
                json={"loss_event_id": event["id"]},
            )
        ).json()
        assert result["events_created"] == 0
        assert result["loss_event_ids"] == [event["id"]]

        detail = (await client.get(f"/loss-events/{event['id']}")).json()
        assert len(detail["losses"]) == 10


class TestTenantIsolation:
    async def test_other_org_cannot_see_or_commit(self, client_factory) -> None:
        a = await client_factory()
        b = await client_factory()
        await register(a, org="Carrier A", email="a@a.example")
        await register(b, org="Carrier B", email="b@b.example")

        uploaded = await _upload(a, golden_loss_csv())

        assert (await b.get(f"/loss-imports/{uploaded['id']}")).status_code == 404
        assert (await b.get(f"/loss-imports/{uploaded['id']}/content")).status_code == 404
        assert (await b.get("/loss-imports")).json()["imports"] == []
        resp = await b.post(f"/loss-imports/{uploaded['id']}/mapping", json={"mapping": {}})
        assert resp.status_code == 404
