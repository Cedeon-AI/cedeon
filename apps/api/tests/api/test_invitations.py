"""Team invitations: invite → accept, role management, removal, and the security
properties (bound to org + email, single-use, expiry, admin-only)."""

from __future__ import annotations

import datetime as dt

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.audit import AuditEvent
from app.db.models.identity import Invitation
from tests.api.test_auth import STRONG_PASSWORD, _register

pytestmark = pytest.mark.db


async def _invite(client: AsyncClient, email: str, role: str = "member") -> dict:
    resp = await client.post("/invitations", json={"email": email, "role": role})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _token_of(client: AsyncClient, accept_url: str) -> str:
    return accept_url.rsplit("/", 1)[-1]


class TestInviteAndAccept:
    async def test_admin_invites_new_user_who_accepts_and_joins(self, client_factory) -> None:
        admin = await client_factory()
        await _register(admin, org="Atlantic Specialty", email="jane@atlantic.example")

        inv = await _invite(admin, "michael@atlantic.example", "member")
        assert inv["accept_url"]  # console mode surfaces the link

        newcomer = await client_factory()
        token = await _token_of(newcomer, inv["accept_url"])

        preview = (await newcomer.get(f"/auth/invitation/{token}")).json()
        assert preview["organization_name"] == "Atlantic Specialty"
        assert preview["invited_email"] == "michael@atlantic.example"
        assert preview["role"] == "member"
        assert preview["invited_by_name"] == "VP Ceded"
        assert not preview["expired"]
        assert not preview["account_exists"]

        accepted = await newcomer.post(
            f"/auth/invitation/{token}/accept",
            json={"name": "Michael Chen", "password": STRONG_PASSWORD},
        )
        assert accepted.status_code == 200
        body = accepted.json()
        assert body["organization"]["name"] == "Atlantic Specialty"
        assert body["role"] == "member"
        me = (await newcomer.get("/auth/me")).json()
        assert me["user"]["email"] == "michael@atlantic.example"

        members = (await admin.get("/memberships")).json()["members"]
        assert {m["email"] for m in members} == {
            "jane@atlantic.example",
            "michael@atlantic.example",
        }
        assert (await admin.get("/invitations")).json()["invitations"] == []

    async def test_existing_user_must_sign_in_before_accepting(self, client_factory) -> None:
        admin = await client_factory()
        await _register(admin, email="admin@a.example", org="A")
        other = await client_factory()
        await _register(other, email="taken@elsewhere.example", org="Elsewhere")

        inv = await _invite(admin, "taken@elsewhere.example")
        token = await _token_of(admin, inv["accept_url"])

        anon = await client_factory()
        blocked = await anon.post(
            f"/auth/invitation/{token}/accept", json={"name": "X", "password": STRONG_PASSWORD}
        )
        assert blocked.status_code == 409  # account exists → sign in first

        accepted = await other.post(f"/auth/invitation/{token}/accept", json={})
        assert accepted.status_code == 200
        assert accepted.json()["organization"]["name"] == "A"  # switched to the new org

    async def test_accept_is_single_use(self, client_factory) -> None:
        admin = await client_factory()
        await _register(admin, email="admin2@a.example")
        inv = await _invite(admin, "grace@a.example")
        token = await _token_of(admin, inv["accept_url"])

        first = await (await client_factory()).post(
            f"/auth/invitation/{token}/accept",
            json={"name": "Grace", "password": STRONG_PASSWORD},
        )
        assert first.status_code == 200
        second = await (await client_factory()).post(
            f"/auth/invitation/{token}/accept", json={"name": "Grace", "password": STRONG_PASSWORD}
        )
        assert second.status_code == 409

    async def test_expired_invitation_cannot_be_accepted(self, client_factory, session) -> None:
        admin = await client_factory()
        await _register(admin, email="admin3@a.example")
        inv = await _invite(admin, "late@a.example")
        token = await _token_of(admin, inv["accept_url"])

        row = (
            await session.execute(select(Invitation).where(Invitation.email == "late@a.example"))
        ).scalar_one()
        row.expires_at = dt.datetime.now(dt.UTC) - dt.timedelta(hours=1)
        await session.commit()

        resp = await (await client_factory()).post(
            f"/auth/invitation/{token}/accept",
            json={"name": "Late", "password": STRONG_PASSWORD},
        )
        assert resp.status_code == 409

    async def test_revoked_invitation_cannot_be_accepted(self, client_factory) -> None:
        admin = await client_factory()
        await _register(admin, email="admin4@a.example")
        inv = await _invite(admin, "nope@a.example")
        assert (await admin.post(f"/invitations/{inv['id']}/revoke")).status_code == 204
        token = await _token_of(admin, inv["accept_url"])
        resp = await (await client_factory()).post(
            f"/auth/invitation/{token}/accept",
            json={"name": "Nope", "password": STRONG_PASSWORD},
        )
        assert resp.status_code == 409

    async def test_resend_rotates_the_token(self, client_factory) -> None:
        admin = await client_factory()
        await _register(admin, email="admin5@a.example")
        inv = await _invite(admin, "resend@a.example")
        old_token = await _token_of(admin, inv["accept_url"])

        again = (await admin.post(f"/invitations/{inv['id']}/resend")).json()
        new_token = await _token_of(admin, again["accept_url"])
        assert new_token != old_token

        stale = await (await client_factory()).get(f"/auth/invitation/{old_token}")
        assert stale.status_code == 404
        fresh = await (await client_factory()).get(f"/auth/invitation/{new_token}")
        assert fresh.status_code == 200


class TestInvitationSecurity:
    async def test_member_cannot_invite(self, client_factory) -> None:
        admin = await client_factory()
        await _register(admin, email="admin6@a.example")
        inv = await _invite(admin, "analyst@a.example")
        token = await _token_of(admin, inv["accept_url"])
        member = await client_factory()
        await member.post(
            f"/auth/invitation/{token}/accept",
            json={"name": "Analyst", "password": STRONG_PASSWORD},
        )
        forbidden = await member.post("/invitations", json={"email": "another@a.example"})
        assert forbidden.status_code == 403

    async def test_invitation_is_bound_to_its_email(self, client_factory) -> None:
        admin = await client_factory()
        await _register(admin, email="admin7@a.example")
        # a signed-in user with a different email cannot accept someone else's invite
        other = await client_factory()
        await _register(other, email="wrong@a.example", org="Wrong Co")
        inv = await _invite(admin, "intended@a.example")
        token = await _token_of(admin, inv["accept_url"])
        resp = await other.post(f"/auth/invitation/{token}/accept", json={})
        assert resp.status_code == 403

    async def test_pending_invitation_is_scoped_to_the_org(self, client_factory) -> None:
        a = await client_factory()
        b = await client_factory()
        await _register(a, org="Org A", email="a@a.example")
        await _register(b, org="Org B", email="b@b.example")
        inv = await _invite(a, "pending@a.example")
        assert [i["email"] for i in (await a.get("/invitations")).json()["invitations"]] == [
            "pending@a.example"
        ]
        assert (await b.get("/invitations")).json()["invitations"] == []
        # B cannot revoke A's invitation
        assert (await b.post(f"/invitations/{inv['id']}/revoke")).status_code == 404


class TestMemberRemoval:
    async def test_removing_a_member_revokes_access_but_keeps_audit(
        self, client_factory, session
    ) -> None:
        admin = await client_factory()
        await _register(admin, email="lead@a.example")
        inv = await _invite(admin, "leaver@a.example")
        token = await _token_of(admin, inv["accept_url"])
        member = await client_factory()
        joined = await member.post(
            f"/auth/invitation/{token}/accept",
            json={"name": "Leaver", "password": STRONG_PASSWORD},
        )
        member_id = joined.json()["user"]["id"]
        assert (await member.get("/auth/me")).status_code == 200

        removed = await admin.delete(f"/memberships/{member_id}")
        assert removed.status_code == 204
        assert (await member.get("/auth/me")).status_code == 401  # session dies on the recheck

        actions = {r.action for r in (await session.execute(select(AuditEvent))).scalars().all()}
        assert {"invitation.accepted", "membership.removed"} <= actions

    async def test_change_role_then_the_new_admin_can_manage(self, client_factory) -> None:
        admin = await client_factory()
        await _register(admin, email="founder@a.example")
        inv = await _invite(admin, "promoted@a.example")
        token = await _token_of(admin, inv["accept_url"])
        member = await client_factory()
        joined = await member.post(
            f"/auth/invitation/{token}/accept",
            json={"name": "Promoted", "password": STRONG_PASSWORD},
        )
        uid = joined.json()["user"]["id"]

        assert (await member.post("/invitations", json={"email": "x@a.example"})).status_code == 403
        promote = await admin.patch(f"/memberships/{uid}", json={"role": "admin"})
        assert promote.status_code == 200
        assert (await member.post("/invitations", json={"email": "x@a.example"})).status_code == 201
