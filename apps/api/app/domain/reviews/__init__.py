"""Human review of AI/system outputs. The review log is append-only (ADR-0012)."""

from __future__ import annotations

from enum import StrEnum


class ReviewSubjectType(StrEnum):
    TREATY_TERM_CANDIDATE = "treaty_term_candidate"
    TREATY_PARTICIPATION_SET = "treaty_participation_set"
    RECOVERY_CANDIDATE = "recovery_candidate"
    RECOVERY_PACKET = "recovery_packet"
    RECOVERY_NOTICE = "recovery_notice"


class ReviewDecision(StrEnum):
    CONFIRM = "confirm"
    EDIT = "edit"
    REJECT = "reject"
    MARK_AMBIGUOUS = "mark_ambiguous"
    REQUEST_INFO = "request_info"
