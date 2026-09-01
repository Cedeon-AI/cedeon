"""Phase 3 golden path: document → extraction (faked) → human validation →
executable treaty version. The real model call is covered by tests/ai."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models.audit import AuditEvent
from tests.support.auth import register
from tests.support.extraction import run_extraction
from tests.support.pdfs import build_treaty_pdf
from tests.support.pipeline import run_parse

pytestmark = pytest.mark.db


async def _bootstrap(client: AsyncClient, object_store, session) -> dict:
    reg = await register(client, email="head.ceded@carrier.example", org="Atlantic Specialty")
    org_id = UUID(reg["organization"]["id"])

    cedent = (await client.post("/cedents", json={"name": "Demo Specialty Insurance Co."})).json()
    program = (
        await client.post(
            "/programs",
            json={
                "cedent_id": cedent["id"],
                "name": "2027 Property Cat Program",
                "treaty_year": 2027,
            },
        )
    ).json()

    upload = await client.post(
        "/documents",
        files={"file": ("treaty.pdf", build_treaty_pdf(), "application/pdf")},
        data={"kind": "treaty"},
    )
    document_id = UUID(upload.json()["id"])
    await run_parse(session, object_store, org_id, document_id)

    treaty = (
        await client.post(
            "/treaties",
            json={
                "program_id": program["id"],
                "name": "2027 Property Cat XOL",
                "source_document_id": str(document_id),
            },
        )
    ).json()
    version_id = UUID(treaty["current_version"]["id"])
    assert treaty["current_version"]["status"] == "extracting"

    await run_extraction(session, get_settings(), org_id, version_id)
    return {"org_id": org_id, "treaty_id": treaty["id"], "version_id": str(version_id)}


def _candidates_url(ctx: dict) -> str:
    return f"/treaties/{ctx['treaty_id']}/versions/{ctx['version_id']}/term-candidates"


async def test_extraction_produces_reviewable_candidates(
    client: AsyncClient, object_store, session
) -> None:
    ctx = await _bootstrap(client, object_store, session)
    body = (await client.get(_candidates_url(ctx))).json()

    assert body["status"] == "needs_validation"
    assert body["currency"] == "USD"
    assert len(body["pages"]) == 3

    by_key: dict[str, list] = {}
    for c in body["candidates"]:
        by_key.setdefault(c["key"], []).append(c)

    assert by_key["attachment"][0]["normalized_value"]["value"] == "50000000.00"
    assert by_key["attachment"][0]["citation"]["page_number"] == 2
    assert by_key["limit"][0]["normalized_value"]["value"] == "20000000.00"
    assert len(by_key["participation"]) == 3


async def test_full_validation_builds_the_executable_layer(
    client: AsyncClient, object_store, session
) -> None:
    ctx = await _bootstrap(client, object_store, session)
    candidates = (await client.get(_candidates_url(ctx))).json()["candidates"]
    base = _candidates_url(ctx)

    for candidate in candidates:
        if candidate["key"] in ("attachment", "limit", "participation"):
            resp = await client.post(
                f"{base}/{candidate['id']}/review", json={"decision": "confirm"}
            )
            assert resp.status_code == 200, resp.text

    validate = await client.post(
        f"/treaties/{ctx['treaty_id']}/versions/{ctx['version_id']}/validate"
    )
    assert validate.status_code == 200, validate.text
    version = validate.json()
    assert version["status"] == "validated"
    assert version["validated_at"] is not None

    assert len(version["layers"]) == 1
    layer = version["layers"][0]
    assert Decimal(layer["attachment"]) == Decimal("50000000.00")
    assert Decimal(layer["limit"]) == Decimal("20000000.00")
    assert layer["currency"] == "USD"

    shares = {p["reinsurer_name"]: Decimal(p["placed_share"]) for p in version["participations"]}
    assert shares == {
        "Reinsurer Alpha": Decimal("0.500000"),
        "Reinsurer Beta": Decimal("0.300000"),
        "Reinsurer Gamma": Decimal("0.200000"),
    }
    assert sum(shares.values()) == Decimal("1.000000")

    detail = (await client.get(f"/treaties/{ctx['treaty_id']}")).json()
    assert detail["current_version"]["status"] == "validated"
    assert len(detail["current_version"]["participations"]) == 3


async def test_cannot_validate_without_confirming_attachment_and_limit(
    client: AsyncClient, object_store, session
) -> None:
    ctx = await _bootstrap(client, object_store, session)
    resp = await client.post(f"/treaties/{ctx['treaty_id']}/versions/{ctx['version_id']}/validate")
    assert resp.status_code == 422
    assert "attachment" in resp.text


async def test_editing_a_candidate_value_is_honoured(
    client: AsyncClient, object_store, session
) -> None:
    ctx = await _bootstrap(client, object_store, session)
    candidates = (await client.get(_candidates_url(ctx))).json()["candidates"]
    base = _candidates_url(ctx)

    for candidate in candidates:
        if candidate["key"] == "limit":
            await client.post(
                f"{base}/{candidate['id']}/review",
                json={"decision": "edit", "value": "25000000.00"},
            )
        elif candidate["key"] in ("attachment", "participation"):
            await client.post(f"{base}/{candidate['id']}/review", json={"decision": "confirm"})

    version = (
        await client.post(f"/treaties/{ctx['treaty_id']}/versions/{ctx['version_id']}/validate")
    ).json()
    assert Decimal(version["layers"][0]["limit"]) == Decimal("25000000.00")


async def test_reconfirming_a_participation_reuses_the_reinsurer(
    client: AsyncClient, object_store, session
) -> None:
    """Reject then re-confirm a participation: the earlier reject leaves the
    Reinsurer row, so the second confirm must reuse it rather than hit the
    (organization, name) unique constraint with a 500."""
    ctx = await _bootstrap(client, object_store, session)
    base = _candidates_url(ctx)
    candidates = (await client.get(base)).json()["candidates"]
    part = next(c for c in candidates if c["key"] == "participation")

    assert (
        await client.post(f"{base}/{part['id']}/review", json={"decision": "confirm"})
    ).status_code == 200
    assert (
        await client.post(f"{base}/{part['id']}/review", json={"decision": "reject"})
    ).status_code == 200
    again = await client.post(f"{base}/{part['id']}/review", json={"decision": "confirm"})
    assert again.status_code == 200, again.text
    assert again.json()["resolution"] == "confirmed"

    detail = (await client.get(f"/treaties/{ctx['treaty_id']}")).json()
    names = [p["reinsurer_name"] for p in detail["current_version"]["participations"]]
    part_name = (part.get("normalized_value") or {}).get("reinsurer_name")
    assert names.count(part_name) == 1


async def test_audit_trail_covers_extraction_and_validation(
    client: AsyncClient, object_store, session
) -> None:
    ctx = await _bootstrap(client, object_store, session)
    candidates = (await client.get(_candidates_url(ctx))).json()["candidates"]
    base = _candidates_url(ctx)
    for candidate in candidates:
        if candidate["key"] in ("attachment", "limit", "participation"):
            await client.post(f"{base}/{candidate['id']}/review", json={"decision": "confirm"})
    await client.post(f"/treaties/{ctx['treaty_id']}/versions/{ctx['version_id']}/validate")

    actions = {row.action for row in (await session.execute(select(AuditEvent))).scalars().all()}
    assert {
        "treaty.created",
        "treaty.extraction_completed",
        "treaty_term_candidate.reviewed",
        "treaty_version.validated",
    } <= actions

    reg_run = next(
        r
        for r in (await session.execute(select(AuditEvent))).scalars().all()
        if r.action == "treaty.extraction_completed"
    )
    assert reg_run.actor_type.value == "agent"
