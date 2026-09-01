"""Org creation is gated by ``signup_mode`` (ADR-0028): ``closed`` refuses all
self-serve, ``code`` needs a redeemable access code that stamps an AI budget onto
the new org, ``open`` is unrestricted."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.dependencies.context import get_settings_dep
from app.core.config import get_settings
from app.core.security import hash_session_token
from app.db.models.audit import AuditEvent
from app.db.models.identity import Organization, SignupCode

pytestmark = pytest.mark.db

STRONG_PASSWORD = "correct-horse-battery-staple"


def _use_mode(app, mode: str):
    override = get_settings().model_copy(update={"signup_mode": mode})
    app.dependency_overrides[get_settings_dep] = lambda: override


async def _make_code(session, *, raw: str = "acme-re-2026", **kw: object) -> SignupCode:
    code = SignupCode(
        code_hash=hash_session_token(raw, get_settings().session_secret),
        label=str(kw.get("label", "Acme Re")),
        max_uses=int(kw.get("max_uses", 1)),  # type: ignore[call-overload]
        redeemed_count=int(kw.get("redeemed_count", 0)),  # type: ignore[call-overload]
        grant_ai_budget_usd=kw.get("grant_ai_budget_usd"),  # type: ignore[arg-type]
        expires_at=kw.get("expires_at"),  # type: ignore[arg-type]
        revoked_at=kw.get("revoked_at"),  # type: ignore[arg-type]
    )
    session.add(code)
    await session.commit()
    return code


async def _register(client: AsyncClient, **body: object) -> object:
    payload = {
        "organization_name": "Atlantic Specialty",
        "email": "vp@atlantic.example",
        "name": "VP Ceded",
        "password": STRONG_PASSWORD,
    }
    payload.update(body)
    return await client.post("/auth/register", json=payload)


class TestAuthConfig:
    async def test_config_reports_the_mode(self, client: AsyncClient, app) -> None:
        _use_mode(app, "code")
        resp = await client.get("/auth/config")
        assert resp.status_code == 200
        assert resp.json()["signup_mode"] == "code"


class TestClosedMode:
    async def test_registration_is_refused(self, client: AsyncClient, app) -> None:
        _use_mode(app, "closed")
        resp = await _register(client)
        assert resp.status_code == 403
        assert "invite-only" in resp.json()["detail"]


class TestCodeMode:
    async def test_missing_code_is_rejected(self, client: AsyncClient, app) -> None:
        _use_mode(app, "code")
        resp = await _register(client)
        assert resp.status_code == 422
        assert "access code" in resp.json()["detail"]

    async def test_unknown_code_is_rejected(self, client: AsyncClient, app) -> None:
        _use_mode(app, "code")
        resp = await _register(client, signup_code="not-a-real-code")
        assert resp.status_code == 422

    async def test_valid_code_creates_org_and_stamps_budget(
        self, client: AsyncClient, app, session
    ) -> None:
        _use_mode(app, "code")
        await _make_code(session, raw="acme-re-2026", grant_ai_budget_usd=Decimal("50.00"))

        resp = await _register(client, signup_code="acme-re-2026")
        assert resp.status_code == 201, resp.text

        org = (
            await session.execute(
                select(Organization).where(Organization.slug == "atlantic-specialty")
            )
        ).scalar_one()
        assert org.ai_budget_usd == Decimal("50.00")

        code = (await session.execute(select(SignupCode))).scalar_one()
        assert code.redeemed_count == 1

        redeemed = (
            await session.execute(
                select(AuditEvent).where(AuditEvent.action == "signup_code.redeemed")
            )
        ).scalar_one()
        assert redeemed.organization_id == org.id

    async def test_single_use_code_cannot_be_redeemed_twice(
        self, client_factory, app, session
    ) -> None:
        _use_mode(app, "code")
        await _make_code(session, raw="one-shot", max_uses=1)

        first = await _register(await client_factory(), signup_code="one-shot")
        assert first.status_code == 201

        second = await _register(
            await client_factory(),
            signup_code="one-shot",
            organization_name="Second Co",
            email="two@second.example",
        )
        assert second.status_code == 422
        assert "already been used" in second.json()["detail"]

    async def test_expired_code_is_rejected(self, client: AsyncClient, app, session) -> None:
        _use_mode(app, "code")
        await _make_code(
            session, raw="stale", expires_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=1)
        )
        resp = await _register(client, signup_code="stale")
        assert resp.status_code == 422

    async def test_revoked_code_is_rejected(self, client: AsyncClient, app, session) -> None:
        _use_mode(app, "code")
        await _make_code(session, raw="killed", revoked_at=dt.datetime.now(dt.UTC))
        resp = await _register(client, signup_code="killed")
        assert resp.status_code == 422

    async def test_multi_use_code_allows_several_orgs(self, client_factory, app, session) -> None:
        _use_mode(app, "code")
        await _make_code(session, raw="partner", max_uses=3)
        for i in range(3):
            resp = await _register(
                await client_factory(),
                signup_code="partner",
                organization_name=f"Partner {i}",
                email=f"p{i}@partner.example",
            )
            assert resp.status_code == 201, resp.text


class TestOpenMode:
    async def test_open_mode_ignores_the_code_field(self, client: AsyncClient, app) -> None:
        _use_mode(app, "open")
        resp = await _register(client)
        assert resp.status_code == 201

    async def test_open_mode_leaves_budget_unset(self, client: AsyncClient, app, session) -> None:
        _use_mode(app, "open")
        await _register(client)
        org = (await session.execute(select(Organization))).scalar_one()
        assert org.ai_budget_usd is None
