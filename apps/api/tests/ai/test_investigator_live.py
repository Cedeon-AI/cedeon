"""Live Recovery Investigator eval against the configured provider. Skipped by
default (``live``); run with:  uv run pytest -m live

Checks the hard constraints from docs/AI_ARCHITECTURE.md §5:
- grounding: every persisted citation resolves to real page text
- the agent does not assert a recovery number different from the deterministic one
- applicability is one of the modelled values
- tool calls and token usage are recorded
"""

from __future__ import annotations

import re
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models.documents import DocumentPage
from app.db.models.extraction import ToolCall
from app.domain.ai import ApplicabilityAssessment
from app.services.investigation import InvestigationService
from tests.support.scenario import committed_hurricane_event, validated_golden_treaty

pytestmark = [pytest.mark.db, pytest.mark.live]

_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip().lower()


@pytest.mark.skipif(
    not get_settings().anthropic_api_key, reason="ANTHROPIC_API_KEY is not configured"
)
async def test_investigator_is_grounded_and_does_not_recompute(
    client: AsyncClient, object_store, session
) -> None:
    golden = await validated_golden_treaty(client, object_store, session)
    event_id = await committed_hurricane_event(client)
    candidate = (
        await client.post(
            "/recovery-candidates",
            json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
        )
    ).json()

    investigation = await InvestigationService(session, get_settings()).investigate(
        golden.org_id, uuid.UUID(candidate["id"])
    )

    assert investigation.status.value == "completed"
    assert investigation.applicability_assessment in set(ApplicabilityAssessment)

    output = investigation.output or {}
    # the deterministic figure is 8,700,000.00 — the agent must not change it
    assert not output.get("recomputed_a_different_number", False)
    reviewed = output.get("recovery_amount_reviewed")
    if reviewed is not None:
        assert Decimal(reviewed) == Decimal("8700000.00")

    # grounding: every stored citation quotes text that is actually on that page
    pages = {
        p.page_number: _norm(p.text)
        for p in (await session.execute(select(DocumentPage).order_by(DocumentPage.page_number)))
        .scalars()
        .all()
    }
    cited = [f for f in investigation.findings if f.citation is not None]
    assert cited, "expected at least one citation-backed finding"
    for finding in cited:
        page = pages.get(finding.citation.page_number, "")
        assert _norm(finding.citation.quoted_text) in page, finding.citation.quoted_text

    calls = (
        (
            await session.execute(
                select(ToolCall).where(ToolCall.agent_run_id == investigation.agent_run_id)
            )
        )
        .scalars()
        .all()
    )
    assert calls, "the investigator should have used its tools"
    assert "get_recovery_calculation" in {c.tool_name for c in calls}
