"""Regression eval datasets — run against the real provider with ``pytest -m eval``.

Not in the default CI job (they cost money and need a key). They assert on exact
values, citation-resolvability and guardrail flags, not "looks OK".
"""

from __future__ import annotations

import pytest
from pydantic_evals import Case, Dataset

from app.ai.evals.extraction import (
    EXTRACTION_EVALUATORS,
    ExtractionCase,
    ExtractionExpectation,
    run_extraction_task,
)
from app.core.config import get_settings
from tests.support.pdfs import (
    build_injection_treaty_pdf,
    build_treaty_pdf,
    build_treaty_pdf_no_limit,
)

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
