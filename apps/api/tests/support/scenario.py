"""End-to-end scenario builders shared across API tests: a validated golden
treaty ($20M xs $50M, Alpha/Beta/Gamma 50/30/20) and a committed hurricane loss
event whose underlying losses sum to USD 58,700,000.00."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from httpx import AsyncClient

from app.core.config import get_settings
from tests.support.extraction import run_extraction
from tests.support.losses import GOLDEN_MAPPING, golden_loss_csv
from tests.support.pdfs import build_treaty_pdf
from tests.support.pipeline import run_parse


@dataclass(slots=True)
class GoldenTreaty:
    org_id: UUID
    treaty_id: str
    version_id: str
    program_id: str


async def validated_golden_treaty(
    client: AsyncClient,
    object_store: object,
    session: object,
    *,
    email: str = "ops@carrier.example",
    org: str = "Carrier Ops",
    layers: list[tuple[str, str]] | None = None,
) -> GoldenTreaty:
    from tests.support.auth import register

    reg = await register(client, email=email, org=org)
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
    for candidate in (await client.get(base)).json()["candidates"]:
        confirm = candidate["key"] == "participation" or (
            layers is None and candidate["key"] in ("attachment", "limit")
        )
        if confirm:
            await client.post(f"{base}/{candidate['id']}/review", json={"decision": "confirm"})
    if layers is not None:
        await client.put(
            f"/treaties/{treaty['id']}/versions/{version_id}/layers",
            json={"currency": "USD", "layers": [{"attachment": a, "limit": x} for a, x in layers]},
        )
    await client.post(f"/treaties/{treaty['id']}/versions/{version_id}/validate")

    return GoldenTreaty(
        org_id=org_id,
        treaty_id=treaty["id"],
        version_id=version_id,
        program_id=program["id"],
    )


async def committed_hurricane_event(
    client: AsyncClient, *, event_name: str = "Hurricane Demo 2027"
) -> str:
    """Upload → map → commit the golden loss CSV; return the loss event id."""
    uploaded = (
        await client.post(
            "/loss-imports", files={"file": ("losses.csv", golden_loss_csv(), "text/csv")}
        )
    ).json()
    await client.post(f"/loss-imports/{uploaded['id']}/mapping", json={"mapping": GOLDEN_MAPPING})
    commit = (
        await client.post(f"/loss-imports/{uploaded['id']}/commit", json={"event_name": event_name})
    ).json()
    return str(commit["loss_event_ids"][0])


async def confirmed_recovery_candidate(
    client: AsyncClient, object_store: object, session: object, **kw: object
) -> tuple[GoldenTreaty, str]:
    """Validated golden treaty + committed Hurricane Demo event → candidate → CONFIRMED."""
    golden = await validated_golden_treaty(client, object_store, session, **kw)  # type: ignore[arg-type]
    event_id = await committed_hurricane_event(client)
    candidate = (
        await client.post(
            "/recovery-candidates",
            json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
        )
    ).json()
    candidate_id = candidate["id"]
    await client.post(f"/recovery-candidates/{candidate_id}/review", json={"decision": "confirm"})
    return golden, candidate_id
