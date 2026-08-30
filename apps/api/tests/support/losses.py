"""Synthetic loss CSVs for the loss-import pipeline tests.

``golden_loss_rows`` is the demo claim schedule: ten hurricane claims whose
gross incurred sums to exactly USD 58,700,000.00 — the gross event loss the
XOL engine turns into an 8.7M layer recovery (see tests/domain/test_xol.py).
"""

from __future__ import annotations

import csv
import io

# (claim_id, date_of_loss, reported_date, gross_paid, gross_case_reserve, cause, location)
_GOLDEN: tuple[tuple[str, str, str, str, str, str, str], ...] = (
    ("CLM-001", "2027-09-14", "2027-09-16", "12000000.00", "3000000.00", "Wind", "Miami-Dade, FL"),
    ("CLM-002", "2027-09-14", "2027-09-17", "8000000.00", "2500000.00", "Wind", "Broward, FL"),
    ("CLM-003", "2027-09-14", "2027-09-18", "5000000.00", "1000000.00", "Flood", "Collier, FL"),
    ("CLM-004", "2027-09-15", "2027-09-19", "4200000.00", "800000.00", "Wind", "Lee, FL"),
    ("CLM-005", "2027-09-15", "2027-09-20", "3000000.00", "500000.00", "Wind", "Charlotte, FL"),
    ("CLM-006", "2027-09-15", "2027-09-21", "2500000.00", "700000.00", "Flood", "Sarasota, FL"),
    ("CLM-007", "2027-09-15", "2027-09-22", "6000000.00", "1500000.00", "Wind", "Hillsborough, FL"),
    ("CLM-008", "2027-09-16", "2027-09-24", "1800000.00", "200000.00", "Wind", "Pinellas, FL"),
    ("CLM-009", "2027-09-16", "2027-09-25", "900000.00", "100000.00", "Flood", "Pasco, FL"),
    ("CLM-010", "2027-09-16", "2027-09-27", "4000000.00", "1000000.00", "Wind", "Manatee, FL"),
)

GOLDEN_EVENT_IDENTIFIER = "HURR-DEMO-2027"
GOLDEN_GROSS_INCURRED = "58700000.00"

GOLDEN_HEADER = [
    "Claim Ref",
    "Event",
    "Loss Date",
    "Reported",
    "Paid",
    "Reserve",
    "Incurred",
    "Ccy",
    "Peril",
    "Location",
]

GOLDEN_MAPPING = {
    "claim_id": "Claim Ref",
    "loss_event_identifier": "Event",
    "date_of_loss": "Loss Date",
    "reported_date": "Reported",
    "gross_paid": "Paid",
    "gross_case_reserve": "Reserve",
    "gross_incurred": "Incurred",
    "currency": "Ccy",
    "cause_of_loss": "Peril",
    "location": "Location",
}


def _rows_to_csv(header: list[str], rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def golden_loss_csv(*, currency: str = "USD") -> bytes:
    rows = [
        [
            claim_id,
            GOLDEN_EVENT_IDENTIFIER,
            dol,
            reported,
            paid,
            reserve,
            f"{float(paid) + float(reserve):.2f}",
            currency,
            cause,
            location,
        ]
        for claim_id, dol, reported, paid, reserve, cause, location in _GOLDEN
    ]
    return _rows_to_csv(GOLDEN_HEADER, rows)


def messy_loss_csv() -> bytes:
    """One clean row, then a spread of the problems validation must catch."""
    header = ["claim", "when", "reported", "incurred", "ccy"]
    rows = [
        ["A-1", "2027-01-05", "2027-01-06", "1,000,000.00", "usd"],  # ok, $-stripping + lc ccy
        ["A-2", "05/02/2027", "", "$250000", "USD"],  # ok, m/d/y + $ prefix
        ["A-1", "2027-01-07", "", "500000", "USD"],  # duplicate claim id -> error (both rows)
        ["A-3", "not-a-date", "", "10000", "USD"],  # unparseable date -> error
        ["A-4", "2027-01-08", "", "-5000", "USD"],  # negative amount -> error
        ["A-5", "2027-01-09", "", "", "USD"],  # missing incurred, no paid/reserve -> error
        ["A-6", "2027-01-10", "2027-01-02", "7500", "EUR"],  # reported < loss -> warning; 2nd ccy
    ]
    return _rows_to_csv(header, rows)


MESSY_MAPPING = {
    "claim_id": "claim",
    "date_of_loss": "when",
    "reported_date": "reported",
    "gross_incurred": "incurred",
    "currency": "ccy",
}
