"""Loss-import domain: canonical fields, the import state machine, and pure
row validation. No AI, no I/O."""

from __future__ import annotations

from enum import StrEnum

from app.domain.losses.canonical import (
    CANONICAL_FIELDS,
    FIELD_SPECS,
    OPTIONAL_FIELDS,
    REQUIRED_FIELDS,
    SPEC_BY_FIELD,
    CanonicalField,
    FieldSpec,
)
from app.domain.losses.validation import (
    ImportReport,
    RowIssue,
    ValidatedRow,
    validate_rows,
)

__all__ = [
    "CANONICAL_FIELDS",
    "FIELD_SPECS",
    "OPTIONAL_FIELDS",
    "REQUIRED_FIELDS",
    "SPEC_BY_FIELD",
    "CanonicalField",
    "FieldSpec",
    "ImportReport",
    "LossImportStatus",
    "LossRowStatus",
    "RowIssue",
    "ValidatedRow",
    "validate_rows",
]


class LossImportStatus(StrEnum):
    UPLOADED = "uploaded"
    MAPPED = "mapped"
    VALIDATED = "validated"
    COMMITTED = "committed"
    FAILED = "failed"


class LossRowStatus(StrEnum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"
