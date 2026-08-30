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
    async def test_register_creates_org_owner_and_session(self, client: AsyncClient) -> None:
        body = await _register(client)
        assert body["organization"]["name"] == "Atlantic Specialty"
        assert body["organization"]["slug"] == "atlantic-specialty"
        assert body["role"] == "owner"
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
            json={
                "organization_name": "Co",
                "email": "a@b.example",
                "name": "A",
                "password": "short",
            },
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

    async def test_unknown_user_is_401(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/auth/login", json={"email": "nobody@nowhere.example", "password": STRONG_PASSWORD}
        )
        assert resp.status_code == 401


class TestSession:
    async def test_me_requires_authentication(self, client: AsyncClient) -> None:
        resp = await client.get("/auth/me")
        assert resp.status_code == 401
        problem = resp.json()
        assert problem["status"] == 401
        assert problem["type"].endswith("authentication_failed")
        assert "correlation_id" in problem

    async def test_logout_revokes_the_session(self, client: AsyncClient) -> None:
        await _register(client)
        assert (await client.post("/auth/logout")).status_code == 204
        assert (await client.get("/auth/me")).status_code == 401


class TestTenantIsolation:
    async def test_members_list_is_scoped_to_the_callers_org(self, client_factory) -> None:
        a = await client_factory()
        b = await client_factory()
        await _register(a, org="Carrier A", email="owner@a.example")
        await _register(b, org="Carrier B", email="owner@b.example")

        a_members = (await a.get("/memberships")).json()["members"]
        assert [m["email"] for m in a_members] == ["owner@a.example"]

        b_members = (await b.get("/memberships")).json()["members"]
        assert [m["email"] for m in b_members] == ["owner@b.example"]


class TestRoleEnforcement:
    async def test_member_cannot_add_members(self, client_factory) -> None:
        owner = await client_factory()
        await _register(owner, email="owner@carrier.example")

        add = await owner.post(
            "/memberships",
            json={
                "email": "analyst@carrier.example",
                "name": "Analyst",
                "role": "member",
                "initial_password": STRONG_PASSWORD,
            },
        )
        assert add.status_code == 201

        member = await client_factory()
        await member.post(
            "/auth/login",
            json={"email": "analyst@carrier.example", "password": STRONG_PASSWORD},
        )
        forbidden = await member.post(
            "/memberships",
            json={
                "email": "another@carrier.example",
                "name": "Another",
                "role": "member",
                "initial_password": STRONG_PASSWORD,
            },
        )
        assert forbidden.status_code == 403

    async def test_admin_cannot_grant_owner(self, client_factory) -> None:
        owner = await client_factory()
        await _register(owner, email="owner2@carrier.example")
        await owner.post(
            "/memberships",
            json={
                "email": "admin@carrier.example",
                "name": "Admin",
                "role": "admin",
                "initial_password": STRONG_PASSWORD,
            },
        )
        admin = await client_factory()
        await admin.post(
            "/auth/login",
            json={"email": "admin@carrier.example", "password": STRONG_PASSWORD},
        )
        resp = await admin.post(
            "/memberships",
            json={
                "email": "coowner@carrier.example",
                "name": "Co Owner",
                "role": "owner",
                "initial_password": STRONG_PASSWORD,
            },
        )
        assert resp.status_code == 403

    async def test_added_member_appears_in_list(self, client_factory) -> None:
        owner = await client_factory()
        await _register(owner, email="owner3@carrier.example")
        await owner.post(
            "/memberships",
            json={
                "email": "ops@carrier.example",
                "name": "Ops Manager",
                "role": "member",
                "initial_password": STRONG_PASSWORD,
            },
        )
        members = (await owner.get("/memberships")).json()["members"]
        assert {m["email"] for m in members} == {
            "owner3@carrier.example",
            "ops@carrier.example",
        }


class TestAudit:
    async def test_registration_writes_an_audit_event(self, client: AsyncClient, session) -> None:
        await _register(client)
        rows = (await session.execute(select(AuditEvent))).scalars().all()
        actions = {r.action for r in rows}
        assert "organization.registered" in actions
        reg = next(r for r in rows if r.action == "organization.registered")
        assert reg.actor_type.value == "user"
        assert reg.actor_id is not None
        assert reg.correlation_id is not None
