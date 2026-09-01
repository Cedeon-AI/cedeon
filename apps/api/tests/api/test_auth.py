"""Registration, login, sessions, tenant isolation, and role enforcement."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.audit import AuditEvent

pytestmark = pytest.mark.db

STRONG_PASSWORD = "correct-horse-battery-staple"


async def _register(
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


class TestRegistration:
    async def test_register_creates_org_admin_and_session(self, client: AsyncClient) -> None:
        body = await _register(client)
        assert body["organization"]["name"] == "Atlantic Specialty"
        assert body["organization"]["slug"] == "atlantic-specialty"
        assert body["role"] == "admin"
        assert body["user"]["email"] == "vp.ceded@atlantic.example"

        me = await client.get("/auth/me")
        assert me.status_code == 200
        assert me.json()["user"]["id"] == body["user"]["id"]

    async def test_duplicate_email_conflicts(self, client: AsyncClient) -> None:
        await _register(client)
        resp = await client.post(
            "/auth/register",
            json={
                "organization_name": "Other Co",
                "email": "vp.ceded@atlantic.example",
                "name": "Someone",
                "password": STRONG_PASSWORD,
            },
        )
        assert resp.status_code == 409
        assert resp.headers["content-type"].startswith("application/problem+json")

    async def test_short_password_rejected(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/auth/register",
            json={"organization_name": "Co", "email": "a@b.example", "name": "A", "password": "x"},
        )
        assert resp.status_code == 422

    async def test_slug_uniqueness(self, client_factory) -> None:
        a = await client_factory()
        b = await client_factory()
        r1 = await _register(a, org="Acme Re", email="a@acme.example")
        r2 = await _register(b, org="Acme Re", email="b@acme.example")
        assert r1["organization"]["slug"] == "acme-re"
        assert r2["organization"]["slug"] == "acme-re-2"


class TestLogin:
    async def test_login_from_a_fresh_client(self, client_factory) -> None:
        setup = await client_factory()
        await _register(setup, email="claims.mgr@carrier.example")
        fresh = await client_factory()
        resp = await fresh.post(
            "/auth/login",
            json={"email": "claims.mgr@carrier.example", "password": STRONG_PASSWORD},
        )
        assert resp.status_code == 200
        assert (await fresh.get("/auth/me")).status_code == 200

    async def test_wrong_password_is_401(self, client_factory) -> None:
        setup = await client_factory()
        await _register(setup, email="x@carrier.example")
        fresh = await client_factory()
        resp = await fresh.post(
            "/auth/login", json={"email": "x@carrier.example", "password": "wrong-password-here"}
        )
        assert resp.status_code == 401


class TestSession:
    async def test_me_requires_authentication(self, client: AsyncClient) -> None:
        resp = await client.get("/auth/me")
        assert resp.status_code == 401

    async def test_logout_revokes_the_session(self, client: AsyncClient) -> None:
        await _register(client)
        assert (await client.post("/auth/logout")).status_code == 204
        assert (await client.get("/auth/me")).status_code == 401


class TestOrganizationSettings:
    async def test_admin_can_rename_the_org_slug_is_stable(self, client: AsyncClient) -> None:
        await _register(client, org="Old Name")
        resp = await client.patch("/organizations/current", json={"name": "New Name"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "New Name"
        assert body["slug"] == "old-name"  # slug is a stable identity, never renamed


class TestRoleEnforcement:
    async def test_last_admin_cannot_be_demoted_or_removed(self, client: AsyncClient) -> None:
        body = await _register(client)
        me = body["user"]["id"]
        demote = await client.patch(f"/memberships/{me}", json={"role": "member"})
        assert demote.status_code == 409
        remove = await client.delete(f"/memberships/{me}")
        assert remove.status_code == 409


class TestAudit:
    async def test_registration_writes_an_audit_event(self, client: AsyncClient, session) -> None:
        await _register(client)
        rows = (await session.execute(select(AuditEvent))).scalars().all()
        actions = {r.action for r in rows}
        assert "organization.registered" in actions
        reg = next(r for r in rows if r.action == "organization.registered")
        assert reg.actor_type.value == "user"
        assert reg.actor_id is not None
