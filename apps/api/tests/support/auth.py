"""Test helpers for establishing an authenticated client."""

from __future__ import annotations

from httpx import AsyncClient

STRONG_PASSWORD = "correct-horse-battery-staple"


async def register(
    client: AsyncClient,
    *,
    org: str = "Atlantic Specialty",
    email: str = "vp.ceded@atlantic.example",
    name: str = "VP Ceded",
    password: str = STRONG_PASSWORD,
) -> dict:
    resp = await client.post(
        "/auth/register",
        json={"organization_name": org, "email": email, "name": name, "password": password},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()
