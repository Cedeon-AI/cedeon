from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.db


async def test_healthz(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert "X-Correlation-ID" in resp.headers


async def test_readyz_checks_database(client: AsyncClient) -> None:
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


async def test_correlation_id_is_echoed_when_supplied(client: AsyncClient) -> None:
    resp = await client.get("/healthz", headers={"X-Request-ID": "abc-123"})
    assert resp.headers["X-Correlation-ID"] == "abc-123"
