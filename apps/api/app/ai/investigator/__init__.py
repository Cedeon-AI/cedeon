"""Recovery Investigator — one bounded, read-only agent (docs/AI_ARCHITECTURE.md §2b).

It investigates a recovery candidate: does the treaty respond, what supports the
recovery, what is missing or ambiguous, what notice is owed. It is handed the
deterministic recovery figure as a fact to explain or challenge — it never
recomputes it, and it has no write tools.
"""

from __future__ import annotations

from app.ai.investigator.runner import (
    InvestigationResult,
    ToolCallLog,
    run_investigator,
)
from app.ai.investigator.schema import (
    Finding,
    FindingCitation,
    RecoveryInvestigation,
)
from app.ai.investigator.tools import InvestigatorDeps

__all__ = [
    "Finding",
    "FindingCitation",
    "InvestigationResult",
    "InvestigatorDeps",
    "RecoveryInvestigation",
    "ToolCallLog",
    "run_investigator",
]
