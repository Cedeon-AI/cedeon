"""Cedeon's canonical underlying-loss schema. Customer CSVs map onto this
(docs/PRODUCT.md §10) — the ACORD adapter maps onto it later, not into it."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CanonicalField(StrEnum):
    CLAIM_ID = "claim_id"
    LOSS_EVENT_IDENTIFIER = "loss_event_identifier"
    DATE_OF_LOSS = "date_of_loss"
    REPORTED_DATE = "reported_date"
    GROSS_PAID = "gross_paid"
    GROSS_CASE_RESERVE = "gross_case_reserve"
    GROSS_INCURRED = "gross_incurred"
    CURRENCY = "currency"
    STATUS = "status"
    CAUSE_OF_LOSS = "cause_of_loss"
    LOCATION = "location"
    DESCRIPTION = "description"


@dataclass(frozen=True, slots=True)
class FieldSpec:
    field: CanonicalField
    label: str
    kind: str  # "text" | "date" | "money" | "currency"
    required: bool
    hint: str = ""


FIELD_SPECS: tuple[FieldSpec, ...] = (
    FieldSpec(CanonicalField.CLAIM_ID, "Claim ID", "text", required=True, hint="unique per import"),
    FieldSpec(
        CanonicalField.LOSS_EVENT_IDENTIFIER,
        "Loss event identifier",
        "text",
        required=False,
        hint="groups claims into a loss event on commit",
    ),
    FieldSpec(CanonicalField.DATE_OF_LOSS, "Date of loss", "date", required=True),
    FieldSpec(CanonicalField.REPORTED_DATE, "Reported date", "date", required=False),
    FieldSpec(
        CanonicalField.GROSS_INCURRED,
        "Gross incurred",
        "money",
        required=False,
        hint="required unless paid + case reserve are both given",
    ),
    FieldSpec(CanonicalField.GROSS_PAID, "Gross paid", "money", required=False),
    FieldSpec(CanonicalField.GROSS_CASE_RESERVE, "Gross case reserve", "money", required=False),
    FieldSpec(
        CanonicalField.CURRENCY, "Currency", "currency", required=True, hint="ISO 4217, e.g. USD"
    ),
    FieldSpec(CanonicalField.STATUS, "Claim status", "text", required=False),
    FieldSpec(CanonicalField.CAUSE_OF_LOSS, "Cause of loss", "text", required=False),
    FieldSpec(CanonicalField.LOCATION, "Location", "text", required=False),
    FieldSpec(CanonicalField.DESCRIPTION, "Description", "text", required=False),
)

CANONICAL_FIELDS: tuple[CanonicalField, ...] = tuple(s.field for s in FIELD_SPECS)
REQUIRED_FIELDS: frozenset[CanonicalField] = frozenset(s.field for s in FIELD_SPECS if s.required)
OPTIONAL_FIELDS: frozenset[CanonicalField] = frozenset(
    s.field for s in FIELD_SPECS if not s.required
)
SPEC_BY_FIELD: dict[CanonicalField, FieldSpec] = {s.field: s for s in FIELD_SPECS}
