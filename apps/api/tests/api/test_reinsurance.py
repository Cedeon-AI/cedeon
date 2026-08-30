"""Reinsurance reference data + programs + treaty creation."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.support.auth import register

pytestmark = pytest.mark.db


async def test_cedent_program_treaty_flow(client: AsyncClient) -> None:
    await register(client)
    cedent = await client.post("/cedents", json={"name": "Atlantic Specialty Insurance Company"})
    assert cedent.status_code == 201

    program = await client.post(
        "/programs",
        json={
            "cedent_id": cedent.json()["id"],
            "name": "2027 Property Catastrophe Program",
            "treaty_year": 2027,
        },
    )
    assert program.status_code == 201
    assert program.json()["cedent_name"] == "Atlantic Specialty Insurance Company"
    assert program.json()["treaty_count"] == 0

    treaty = await client.post(
        "/treaties",
        json={"program_id": program.json()["id"], "name": "2027 Property Cat XOL"},
    )
    assert treaty.status_code == 201
    assert treaty.json()["current_version"]["status"] == "draft"

    programs = (await client.get("/programs")).json()["programs"]
    assert programs[0]["treaty_count"] == 1
    treaties = (await client.get("/treaties")).json()["treaties"]
    assert [t["name"] for t in treaties] == ["2027 Property Cat XOL"]


async def test_duplicate_cedent_conflicts(client: AsyncClient) -> None:
    await register(client)
    await client.post("/cedents", json={"name": "Acme Insurance"})
    resp = await client.post("/cedents", json={"name": "Acme Insurance"})
    assert resp.status_code == 409


async def test_program_requires_known_cedent(client: AsyncClient) -> None:
    await register(client)
    resp = await client.post(
        "/programs",
        json={
            "cedent_id": "00000000-0000-0000-0000-000000000000",
            "name": "X",
            "treaty_year": 2027,
        },
    )
    assert resp.status_code == 404


async def test_reference_data_is_tenant_scoped(client_factory) -> None:
    a = await client_factory()
    b = await client_factory()
    await register(a, org="Carrier A", email="a@a.example")
    await register(b, org="Carrier B", email="b@b.example")

    await a.post("/cedents", json={"name": "A-only Cedent"})
    assert (await b.get("/cedents")).json()["cedents"] == []
    assert (await b.get("/treaties")).json()["treaties"] == []
