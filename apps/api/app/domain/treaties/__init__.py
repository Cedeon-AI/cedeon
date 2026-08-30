"""Treaty domain: types, the version lifecycle, and (Phase 4) the executable model.

Kept small on purpose — MVP supports exactly one structure: per-occurrence
excess of loss (`$limit xs $attachment`). See docs/PRODUCT.md §7.
"""

from __future__ import annotations

from enum import StrEnum


class TreatyType(StrEnum):
    PER_OCCURRENCE_XOL = "per_occurrence_xol"


class TreatyVersionStatus(StrEnum):
    """Lifecycle of one treaty version (the immutable executable unit).

    DRAFT ──▶ PARSING ──▶ EXTRACTING ──▶ NEEDS_VALIDATION ──▶ VALIDATED ──▶ ACTIVE
                                                 └──────────────┘
                          (post-validation change → new version; old → SUPERSEDED)
    """

    DRAFT = "draft"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    NEEDS_VALIDATION = "needs_validation"
    VALIDATED = "validated"
    ACTIVE = "active"
    SUPERSEDED = "superseded"

    @property
    def is_frozen(self) -> bool:
        """Terms/layers/participations are immutable once the version reaches here."""
        return self in (
            TreatyVersionStatus.VALIDATED,
            TreatyVersionStatus.ACTIVE,
            TreatyVersionStatus.SUPERSEDED,
        )


# Canonical keys for scalar treaty terms (money/structural terms live in
# treaty_layers / treaty_participations, not here).
class TermKey(StrEnum):
    EFFECTIVE_DATE = "effective_date"
    EXPIRATION_DATE = "expiration_date"
    CURRENCY = "currency"
    CEDENT_NAME = "cedent_name"
    COVERED_BUSINESS = "covered_business"
    COVERED_PERILS = "covered_perils"
    TERRITORY = "territory"
    EXCLUSIONS = "exclusions"
    EVENT_DEFINITION = "event_definition"
    HOURS_CLAUSE = "hours_clause"
    NOTICE_PROVISION = "notice_provision"
    REPORTING_THRESHOLD = "reporting_threshold"
    REINSTATEMENTS = "reinstatements"


class TermStatus(StrEnum):
    CONFIRMED = "confirmed"
    AMBIGUOUS = "ambiguous"
    REJECTED = "rejected"
