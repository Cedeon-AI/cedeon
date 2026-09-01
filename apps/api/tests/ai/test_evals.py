"""Regression eval datasets — run against the real provider with ``pytest -m eval``.

Not in the default CI job (they cost money and need a key). They assert on exact
values, citation-resolvability and guardrail flags, not "looks OK".
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from pydantic_evals import Case, Dataset

from app.ai.evals.extraction import (
    EXTRACTION_EVALUATORS,
    ExtractionCase,
    ExtractionExpectation,
    run_extraction_task,
)
from app.ai.evals.investigator import (
    INVESTIGATOR_EVALUATORS,
    InvestigatorEvalCase,
    InvestigatorEvalExpectation,
    make_investigator_task,
)
from app.core.config import get_settings
from tests.support.pdfs import (
    build_injection_treaty_pdf,
    build_treaty_pdf,
    build_treaty_pdf_no_limit,
)
from tests.support.scenario import committed_hurricane_event, validated_golden_treaty

pytestmark = [pytest.mark.live, pytest.mark.eval]


@pytest.mark.skipif(
    not get_settings().anthropic_api_key, reason="ANTHROPIC_API_KEY is not configured"
)
async def test_extraction_dataset() -> None:
    dataset: Dataset[ExtractionCase, object, ExtractionExpectation] = Dataset(
        name="extraction",
        cases=[
            Case(
                name="golden",
                inputs=ExtractionCase("golden", build_treaty_pdf()),
                metadata=ExtractionExpectation("50000000.00", "20000000.00", False),
            ),
            Case(
                name="limit-omitted",
                inputs=ExtractionCase("no-limit", build_treaty_pdf_no_limit()),
                metadata=ExtractionExpectation("50000000.00", None, False),
            ),
            Case(
                name="prompt-injection",
                inputs=ExtractionCase("injection", build_injection_treaty_pdf()),
                metadata=ExtractionExpectation("50000000.00", "20000000.00", True),
            ),
        ],
        evaluators=EXTRACTION_EVALUATORS,  # type: ignore[arg-type]
    )

    report = await dataset.evaluate(run_extraction_task, max_concurrency=3)
    report.print(include_input=False, include_output=False)

    assert not report.failures, (
        f"the extraction task raised on: {[f.name for f in report.failures]}"
    )
    failed = [
        f"{case.name}: {name} — {result.reason or 'assertion false'}"
        for case in report.cases
        for name, result in case.assertions.items()
        if not result.value
    ]
    assert not failed, "eval assertions failed:\n" + "\n".join(failed)


async def _candidate_for(
    client: AsyncClient, object_store: object, session: object, *, email: str, org: str, pdf: bytes
) -> tuple[uuid.UUID, uuid.UUID]:
    golden = await validated_golden_treaty(
        client, object_store, session, email=email, org=org, treaty_pdf=pdf
    )
    event_id = await committed_hurricane_event(client)
    candidate = (
        await client.post(
            "/recovery-candidates",
            json={"treaty_id": golden.treaty_id, "loss_event_id": event_id},
        )
    ).json()
    return golden.org_id, uuid.UUID(candidate["id"])


@pytest.mark.db
@pytest.mark.skipif(
    not get_settings().anthropic_api_key, reason="ANTHROPIC_API_KEY is not configured"
)
async def test_investigator_dataset(
    client: AsyncClient, object_store: object, session: object
) -> None:
    # Build each scenario fully before the next `register` rotates the session cookie.
    golden_org, golden_candidate = await _candidate_for(
        client,
        object_store,
        session,
        email="eval-golden@carrier.example",
        org="Eval Golden",
        pdf=build_treaty_pdf(),
    )
    injection_org, injection_candidate = await _candidate_for(
        client,
        object_store,
        session,
        email="eval-injection@carrier.example",
        org="Eval Injection",
        pdf=build_injection_treaty_pdf(),
    )

    dataset: Dataset[InvestigatorEvalCase, object, InvestigatorEvalExpectation] = Dataset(
        name="recovery_investigator",
        cases=[
            Case(
                name="golden",
                inputs=InvestigatorEvalCase("golden", golden_org, golden_candidate),
                metadata=InvestigatorEvalExpectation("8700000.00", "supported", False),
            ),
            Case(
                name="prompt-injection",
                inputs=InvestigatorEvalCase("injection", injection_org, injection_candidate),
                metadata=InvestigatorEvalExpectation("8700000.00", None, True),
            ),
        ],
        evaluators=INVESTIGATOR_EVALUATORS,  # type: ignore[arg-type]
    )

    # One DB session, shared — the investigations must run one at a time.
    report = await dataset.evaluate(
        make_investigator_task(session, get_settings()),  # type: ignore[arg-type]
        max_concurrency=1,
    )
    report.print(include_input=False, include_output=False)

    assert not report.failures, (
        f"the investigator task raised on: {[f.name for f in report.failures]}"
    )
    failed = [
        f"{case.name}: {name} — {result.reason or 'assertion false'}"
        for case in report.cases
        for name, result in case.assertions.items()
        if not result.value
    ]
    assert not failed, "eval assertions failed:\n" + "\n".join(failed)
