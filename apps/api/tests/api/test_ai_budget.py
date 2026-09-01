"""A per-organization monthly AI budget stops model work once the cap is reached
(ADR-0028). Spend is the sum of ``agent_runs.cost_usd`` for the calendar month."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models.extraction import AgentRun
from app.db.models.identity import Organization
from app.domain.ai import AgentRunStatus, AgentType
from app.notifications import ConsoleEmailSender
from app.services.ai_budget import AiBudgetService
from app.services.errors import UsageLimitError
from tests.api.test_auth import _register

pytestmark = pytest.mark.db


async def _spend(session, organization_id: uuid.UUID, usd: str) -> None:
    session.add(
        AgentRun(
            organization_id=organization_id,
            agent_type=AgentType.TREATY_EXTRACTION,
            subject_type="treaty_version",
            subject_id=uuid.uuid4(),
            provider="anthropic",
            model="anthropic:claude-opus-5",
            status=AgentRunStatus.SUCCEEDED,
            cost_usd=Decimal(usd),
            started_at=dt.datetime.now(dt.UTC),
        )
    )
    await session.commit()


async def _org(client, session, *, budget: Decimal | None) -> Organization:
    await _register(client, org="Budgeted Re", email="ceo@budgeted.example")
    org = (await session.execute(select(Organization))).scalars().first()
    assert org is not None
    org.ai_budget_usd = budget
    await session.commit()
    return org


class TestBudgetStatus:
    async def test_status_sums_this_months_spend(self, client, session) -> None:
        org = await _org(client, session, budget=Decimal("20"))
        await _spend(session, org.id, "7.50")
        await _spend(session, org.id, "4.25")

        status = await AiBudgetService(session, get_settings()).status(org.id)
        assert status.spent_usd == Decimal("11.75")
        assert status.remaining_usd == Decimal("8.25")
        assert status.exhausted is False


class TestEnforce:
    async def test_over_budget_raises(self, client, session) -> None:
        org = await _org(client, session, budget=Decimal("10"))
        await _spend(session, org.id, "10.01")
        with pytest.raises(UsageLimitError):
            await AiBudgetService(session, get_settings()).enforce(org.id)

    async def test_under_budget_passes(self, client, session) -> None:
        org = await _org(client, session, budget=Decimal("10"))
        await _spend(session, org.id, "9.99")
        await AiBudgetService(session, get_settings()).enforce(org.id)  # no raise

    async def test_unlimited_budget_passes(self, client, session) -> None:
        org = await _org(client, session, budget=None)
        await _spend(session, org.id, "999999")
        await AiBudgetService(session, get_settings()).enforce(org.id)  # no raise


class TestRouteEnforcement:
    async def test_investigate_route_returns_402_when_over_budget(self, client, session) -> None:
        org = await _org(client, session, budget=Decimal("5"))
        await _spend(session, org.id, "6")
        # Any AI-triggering route: the pre-check fires before the candidate lookup.
        resp = await client.post(f"/recovery-candidates/{uuid.uuid4()}/investigate")
        assert resp.status_code == 402
        assert "usage limit" in resp.json()["detail"]


class TestNotification:
    async def test_alert_is_sent_once_when_the_threshold_is_crossed(self, client, session) -> None:
        org = await _org(client, session, budget=Decimal("10"))
        await _spend(session, org.id, "9")  # 90% → past the 80% warn line

        svc = AiBudgetService(session, get_settings())
        await svc.notify_if_crossed(org.id, email=ConsoleEmailSender())
        await session.commit()
        await session.refresh(org)
        first_mark = org.ai_budget_notified_at
        assert first_mark is not None

        await svc.notify_if_crossed(org.id, email=ConsoleEmailSender())
        await session.commit()
        await session.refresh(org)
        assert org.ai_budget_notified_at == first_mark  # not re-alerted this month
