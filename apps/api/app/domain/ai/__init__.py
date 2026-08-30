"""AI-run domain concepts (telemetry for every model call)."""

from __future__ import annotations

from enum import StrEnum


class AgentType(StrEnum):
    TREATY_EXTRACTION = "treaty_extraction"
    RECOVERY_INVESTIGATOR = "recovery_investigator"
    NOTICE_DRAFTER = "notice_drafter"


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ExtractedTermStatus(StrEnum):
    EXTRACTED = "extracted"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    CONFLICTING = "conflicting"


class ToolCallStatus(StrEnum):
    OK = "ok"
    ERROR = "error"


class InvestigationStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ApplicabilityAssessment(StrEnum):
    """The agent's read on whether the treaty responds to this loss — it explains
    and challenges the deterministic figure, it never recomputes it."""

    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNCLEAR = "unclear"
    CONTRADICTED = "contradicted"


class FindingKind(StrEnum):
    RELEVANT_CLAUSE = "relevant_clause"
    SUPPORTING_EVIDENCE = "supporting_evidence"
    MISSING_INFORMATION = "missing_information"
    AMBIGUITY = "ambiguity"
    INCONSISTENCY = "inconsistency"
    NOTICE_OBLIGATION = "notice_obligation"
    NEXT_STEP = "next_step"
