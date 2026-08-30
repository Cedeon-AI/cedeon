"""Treaty term extraction — one typed structured-output call, no tools, no loop."""

from __future__ import annotations

from app.ai.extraction.runner import ExtractionResult, extract_treaty_terms
from app.ai.extraction.schema import (
    ParticipationCandidate,
    Provenance,
    TermCandidate,
    TermCandidateStatus,
    TreatyExtraction,
)

__all__ = [
    "ExtractionResult",
    "ParticipationCandidate",
    "Provenance",
    "TermCandidate",
    "TermCandidateStatus",
    "TreatyExtraction",
    "extract_treaty_terms",
]
