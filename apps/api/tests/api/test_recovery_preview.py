"""The read-only recovery preview: deterministic engine against a validated treaty."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from tests.support.auth import register
from tests.support.extraction import run_extraction
from tests.support.pdfs import build_treaty_pdf
from tests.support.pipeline import run_parse

pytestmark = pytest.mark.db


async def _validated_treaty(client: AsyncClient, object_store, session) -> str:
    reg = await register(client, email="ops@carrier.example", org="Carrier Ops")
    org_id = UUID(reg["organization"]["id"])
    cedent = (await client.post("/cedents", json={"name": "Demo Specialty"})).json()
    program = (
        await client.post(
            "/programs",
            json={"cedent_id": cedent["id"], "name": "2027 Cat", "treaty_year": 2027},
        )
    ).json()
    upload = await client.post(
        "/documents",
        files={"file": ("t.pdf", build_treaty_pdf(), "application/pdf")},
        data={"kind": "treaty"},
    )
    doc_id = UUID(upload.json()["id"])
    await run_parse(session, object_store, org_id, doc_id)
    treaty = (
        await client.post(
            "/treaties",
            json={
                "program_id": program["id"],
                "name": "2027 Property Cat XOL",
                "source_document_id": str(doc_id),
            },
        )
    ).json()
    version_id = treaty["current_version"]["id"]
    await run_extraction(session, get_settings(), org_id, UUID(version_id))

    base = f"/treaties/{treaty['id']}/versions/{version_id}/term-candidates"
    candidates = (await client.get(base)).json()["candidates"]
    for c in candidates:
        if c["key"] in ("attachment", "limit", "participation"):
            await client.post(f"{base}/{c['id']}/review", json={"decision": "confirm"})
    await client.post(f"/treaties/{treaty['id']}/versions/{version_id}/validate")
    return treaty["id"]


async def test_preview_matches_the_golden_recovery(
    client: AsyncClient, object_store, session
) -> None:
    treaty_id = await _validated_treaty(client, object_store, session)
    resp = await client.post(
        f"/treaties/{treaty_id}/recovery-preview", json={"gross_loss": "58700000.00"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert Decimal(body["layer_recovery"]) == Decimal("8700000.00")
    assert Decimal(body["amount_above_attachment"]) == Decimal("8700000.00")
    assert Decimal(body["cedent_retention"]) == Decimal("0.00")
    assert body["currency"] == "USD"
    assert body["engine_version"]

    allocs = {a["reinsurer_name"]: Decimal(a["amount"]) for a in body["allocations"]}
    assert allocs == {
        "Reinsurer Alpha": Decimal("4350000.00"),
        "Reinsurer Beta": Decimal("2610000.00"),
        "Reinsurer Gamma": Decimal("1740000.00"),
    }
    assert [s["label"] for s in body["trace"]] == [
        "gross event loss",
        "amount above attachment",
        "layer recovery",
    ]


async def test_preview_below_attachment_is_zero(client: AsyncClient, object_store, session) -> None:
    treaty_id = await _validated_treaty(client, object_store, session)
    resp = await client.post(
        f"/treaties/{treaty_id}/recovery-preview", json={"gross_loss": "40000000.00"}
    )
    body = resp.json()
    assert Decimal(body["layer_recovery"]) == Decimal("0.00")
    assert len(body["allocations"]) == 3
    assert all(Decimal(a["amount"]) == Decimal("0.00") for a in body["allocations"])


async def test_preview_requires_a_validated_treaty(client: AsyncClient) -> None:
    await register(client)
    cedent = (await client.post("/cedents", json={"name": "C"})).json()
    program = (
        await client.post(
            "/programs", json={"cedent_id": cedent["id"], "name": "P", "treaty_year": 2027}
        )
    ).json()
    treaty = (
        await client.post("/treaties", json={"program_id": program["id"], "name": "T"})
    ).json()
    resp = await client.post(
        f"/treaties/{treaty['id']}/recovery-preview", json={"gross_loss": "58700000.00"}
    )
    assert resp.status_code == 409
    assert "validated" in resp.text
