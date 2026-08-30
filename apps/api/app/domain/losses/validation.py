"""Pure validation of mapped loss rows. Malformed rows are flagged, never dropped
(docs/PRODUCT.md §11)."""

from __future__ import annotations

import datetime as dt
from collections import Counter
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Any

from app.domain.losses.canonical import CanonicalField

_CENT = Decimal("0.01")
_ZERO = Decimal("0")
_INCURRED_TOLERANCE = Decimal("1.00")
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%b-%Y", "%d %b %Y")
_MONEY_STRIP = str.maketrans("", "", "$, ")


@dataclass(frozen=True, slots=True)
class RowIssue:
    row_number: int
    level: str  # "warning" | "error"
    field: str | None
    message: str


@dataclass(frozen=True, slots=True)
class ValidatedRow:
    row_number: int
    status: str  # LossRowStatus value: ok | warning | error
    parsed: dict[str, Any]
    issues: tuple[RowIssue, ...]

    @property
    def is_committable(self) -> bool:
        return self.status in ("ok", "warning")


@dataclass(frozen=True, slots=True)
class ImportReport:
    total_rows: int
    ok: int
    warnings: int
    errors: int
    committable: int
    currencies: tuple[str, ...]
    distinct_events: tuple[str, ...]
    gross_incurred_by_currency: dict[str, str]
    issues: tuple[RowIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "ok": self.ok,
            "warnings": self.warnings,
            "errors": self.errors,
            "committable": self.committable,
            "currencies": list(self.currencies),
            "distinct_events": list(self.distinct_events),
            "gross_incurred_by_currency": self.gross_incurred_by_currency,
            "issues": [
                {
                    "row_number": i.row_number,
                    "level": i.level,
                    "field": i.field,
                    "message": i.message,
                }
                for i in self.issues
            ],
        }


@dataclass(slots=True)
class _RowBuilder:
    row_number: int
    issues: list[RowIssue] = field(default_factory=list)
    parsed: dict[str, Any] = field(default_factory=dict)

    def error(self, field_name: str | None, message: str) -> None:
        self.issues.append(RowIssue(self.row_number, "error", field_name, message))

    def warn(self, field_name: str | None, message: str) -> None:
        self.issues.append(RowIssue(self.row_number, "warning", field_name, message))

    @property
    def status(self) -> str:
        levels = {i.level for i in self.issues}
        return "error" if "error" in levels else "warning" if "warning" in levels else "ok"


def _parse_date(value: str) -> dt.date | None:
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_money(value: str) -> Decimal | None:
    try:
        amount = Decimal(value.translate(_MONEY_STRIP))
    except (InvalidOperation, ValueError):
        return None
    return amount.quantize(_CENT, rounding=ROUND_HALF_EVEN) if amount.is_finite() else None


def _cell(raw: dict[str, str], mapping: dict[CanonicalField, str], f: CanonicalField) -> str:
    column = mapping.get(f)
    return (raw.get(column, "") if column else "").strip()


def validate_rows(
    raw_rows: list[dict[str, str]],
    mapping: dict[CanonicalField, str],
) -> tuple[list[ValidatedRow], ImportReport]:
    missing_required = [
        f.value
        for f in (CanonicalField.CLAIM_ID, CanonicalField.DATE_OF_LOSS, CanonicalField.CURRENCY)
        if f not in mapping
    ]

    claim_counts: Counter[str] = Counter(
        c for raw in raw_rows if (c := _cell(raw, mapping, CanonicalField.CLAIM_ID))
    )
    duplicate_claims = {claim for claim, n in claim_counts.items() if n > 1}

    validated: list[ValidatedRow] = []
    all_issues: list[RowIssue] = []
    currencies: set[str] = set()
    events: list[str] = []
    incurred_totals: dict[str, Decimal] = {}

    for index, raw in enumerate(raw_rows):
        b = _RowBuilder(index + 1)
        if missing_required:
            b.error(None, f"unmapped required field(s): {', '.join(missing_required)}")

        claim_id = _cell(raw, mapping, CanonicalField.CLAIM_ID)
        if not claim_id:
            b.error("claim_id", "claim_id is required")
        else:
            b.parsed["claim_id"] = claim_id
            if claim_id in duplicate_claims:
                b.error("claim_id", f"duplicate claim_id {claim_id!r}")

        date_of_loss = None
        raw_dol = _cell(raw, mapping, CanonicalField.DATE_OF_LOSS)
        if not raw_dol:
            b.error("date_of_loss", "date_of_loss is required")
        elif (date_of_loss := _parse_date(raw_dol)) is None:
            b.error("date_of_loss", f"could not parse date {raw_dol!r}")
        else:
            b.parsed["date_of_loss"] = date_of_loss.isoformat()

        raw_reported = _cell(raw, mapping, CanonicalField.REPORTED_DATE)
        if raw_reported:
            reported = _parse_date(raw_reported)
            if reported is None:
                b.warn("reported_date", f"could not parse date {raw_reported!r}")
            else:
                b.parsed["reported_date"] = reported.isoformat()
                if date_of_loss and reported < date_of_loss:
                    b.warn("reported_date", "reported before date of loss")

        currency = _cell(raw, mapping, CanonicalField.CURRENCY).upper()
        if not currency:
            b.error("currency", "currency is required")
        elif len(currency) != 3 or not currency.isalpha():
            b.error("currency", f"{currency!r} is not a 3-letter currency code")
        else:
            b.parsed["currency"] = currency
            currencies.add(currency)

        money: dict[str, Decimal | None] = {}
        for f in (
            CanonicalField.GROSS_INCURRED,
            CanonicalField.GROSS_PAID,
            CanonicalField.GROSS_CASE_RESERVE,
        ):
            raw_amount = _cell(raw, mapping, f)
            if not raw_amount:
                money[f.value] = None
                continue
            parsed = _parse_money(raw_amount)
            if parsed is None:
                b.error(f.value, f"{raw_amount!r} is not a valid amount")
                money[f.value] = None
            elif parsed < _ZERO:
                b.error(f.value, "amount must be non-negative")
                money[f.value] = None
            else:
                money[f.value] = parsed
                b.parsed[f.value] = str(parsed)

        incurred = money["gross_incurred"]
        paid, reserve = money["gross_paid"], money["gross_case_reserve"]
        if incurred is None and paid is not None and reserve is not None:
            incurred = (paid + reserve).quantize(_CENT)
            b.parsed["gross_incurred"] = str(incurred)
        elif incurred is None:
            b.error(
                "gross_incurred",
                "gross_incurred is required unless gross_paid and gross_case_reserve are given",
            )
        elif (
            paid is not None
            and reserve is not None
            and abs(incurred - (paid + reserve)) > _INCURRED_TOLERANCE
        ):
            b.warn("gross_incurred", "gross incurred does not equal paid + case reserve")

        for f in (
            CanonicalField.STATUS,
            CanonicalField.CAUSE_OF_LOSS,
            CanonicalField.LOCATION,
            CanonicalField.DESCRIPTION,
        ):
            if value := _cell(raw, mapping, f):
                b.parsed[f.value] = value

        if event := _cell(raw, mapping, CanonicalField.LOSS_EVENT_IDENTIFIER):
            b.parsed["loss_event_identifier"] = event
            events.append(event)

        if b.status != "error" and incurred is not None and currency in currencies:
            incurred_totals[currency] = incurred_totals.get(currency, _ZERO) + incurred

        validated.append(ValidatedRow(b.row_number, b.status, b.parsed, tuple(b.issues)))
        all_issues.extend(b.issues)

    ok = sum(1 for r in validated if r.status == "ok")
    warnings = sum(1 for r in validated if r.status == "warning")
    errors = sum(1 for r in validated if r.status == "error")
    report = ImportReport(
        total_rows=len(validated),
        ok=ok,
        warnings=warnings,
        errors=errors,
        committable=ok + warnings,
        currencies=tuple(sorted(currencies)),
        distinct_events=tuple(sorted(set(events))),
        gross_incurred_by_currency={k: str(v) for k, v in sorted(incurred_totals.items())},
        issues=tuple(all_issues),
    )
    return validated, report
