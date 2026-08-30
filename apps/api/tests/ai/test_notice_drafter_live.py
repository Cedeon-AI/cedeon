"""Live notice-drafter eval against the configured provider. Skipped by default
(``live``); run with:  uv run pytest -m live

Checks the hard constraints (docs/AI_ARCHITECTURE.md §2c):
- the draft uses only the facts provided (no invented figures / parties / contacts)
- the deterministic layer recovery appears unchanged
- the notice is framed as indicative, without admission or agreement that money is due
"""

from __future__ import annotations

import re
import uuid

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.domain.recoveries import NoticeKind
from app.services.notice import NoticeService
from tests.support.scenario import confirmed_recovery_candidate

pytestmark = [pytest.mark.db, pytest.mark.live]

_INVENTED_CONTACT = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


@pytest.mark.skipif(
    not get_settings().anthropic_api_key, reason="ANTHROPIC_API_KEY is not configured"
)
async def test_notice_uses_only_provided_facts_and_stays_indicative(
    client: AsyncClient, object_store, session
) -> None:
    golden, candidate_id = await confirmed_recovery_candidate(client, object_store, session)

    notice = await NoticeService(session, get_settings()).draft(
        golden.org_id,
        uuid.UUID(candidate_id),
        kind=NoticeKind.INITIAL_LOSS_ADVICE,
        recipient={"name": "Claims Manager", "organisation": "Reinsurer Alpha"},
    )

    body = notice.body_markdown.lower()
    assert notice.used_only_provided_facts is True

    # the deterministic figure, unchanged (with or without thousands separators)
    assert "8,700,000" in notice.body_markdown or "8700000" in notice.body_markdown

    # the addressee and principals come from the facts
    assert "reinsurer alpha" in body
    assert "demo specialty" in body

    # framed as indicative, not as an agreed / paid amount
    assert any(
        w in body for w in ("indicative", "subject to", "without admission", "without prejudice")
    )
    assert "has been paid" not in body
    assert "has been agreed" not in body

    # no fabricated email address (none were provided)
    assert not _INVENTED_CONTACT.search(notice.body_markdown)
