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
