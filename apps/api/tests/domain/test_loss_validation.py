"""Pure loss-row validation. Malformed rows are flagged, never dropped."""

from __future__ import annotations

from decimal import Decimal

from app.domain.losses import CanonicalField, validate_rows

F = CanonicalField


def _map(**pairs: str) -> dict[CanonicalField, str]:
    return {F(k): v for k, v in pairs.items()}


GOLDEN_MAPPING = _map(
    claim_id="claim",
    loss_event_identifier="event",
    date_of_loss="dol",
    gross_paid="paid",
    gross_case_reserve="reserve",
    currency="ccy",
)


def _row(
    claim: str, dol: str, paid: str, reserve: str, *, event: str = "E1", ccy: str = "USD"
) -> dict:
    return {
        "claim": claim,
        "event": event,
        "dol": dol,
        "paid": paid,
        "reserve": reserve,
        "ccy": ccy,
    }


class TestHappyPath:
    def test_incurred_is_derived_from_paid_plus_reserve(self) -> None:
        rows, report = validate_rows(
            [_row("C-1", "2027-09-14", "12000000.00", "3000000.00")], GOLDEN_MAPPING
        )
        assert rows[0].status == "ok"
        assert rows[0].parsed["gross_incurred"] == "15000000.00"
        assert report.gross_incurred_by_currency == {"USD": "15000000.00"}
        assert report.committable == 1

    def test_distinct_events_and_currencies_are_collected(self) -> None:
        _, report = validate_rows(
            [
                _row("C-1", "2027-09-14", "1000000.00", "0.00", event="E1"),
                _row("C-2", "2027-09-15", "2000000.00", "0.00", event="E2"),
            ],
            GOLDEN_MAPPING,
        )
        assert report.distinct_events == ("E1", "E2")
        assert report.currencies == ("USD",)

    def test_currency_is_normalised_to_upper(self) -> None:
        rows, _ = validate_rows(
            [_row("C-1", "2027-09-14", "1000000.00", "0.00", ccy="usd")], GOLDEN_MAPPING
        )
        assert rows[0].parsed["currency"] == "USD"

    def test_multiple_date_formats_parse(self) -> None:
        m = _map(claim_id="claim", date_of_loss="dol", gross_incurred="inc", currency="ccy")
        raw = [
            {"claim": "C-1", "dol": "2027-09-14", "inc": "1000", "ccy": "USD"},
            {"claim": "C-2", "dol": "09/14/2027", "inc": "1000", "ccy": "USD"},
            {"claim": "C-3", "dol": "14-Sep-2027", "inc": "1000", "ccy": "USD"},
        ]
        rows, report = validate_rows(raw, m)
        assert [r.parsed["date_of_loss"] for r in rows] == ["2027-09-14"] * 3
        assert report.errors == 0


class TestFailures:
    def test_missing_required_mapping_errors_every_row(self) -> None:
        rows, report = validate_rows(
            [{"claim": "C-1"}, {"claim": "C-2"}],
            _map(claim_id="claim"),  # date_of_loss + currency unmapped
        )
        assert report.errors == 2
        assert all("unmapped required field" in i.message for r in rows for i in r.issues[:1])

    def test_duplicate_claim_id_flags_all_offending_rows(self) -> None:
        rows, _ = validate_rows(
            [
                _row("DUP", "2027-09-14", "1000", "0"),
                _row("UNIQUE", "2027-09-14", "1000", "0"),
                _row("DUP", "2027-09-15", "1000", "0"),
            ],
            GOLDEN_MAPPING,
        )
        assert rows[0].status == "error"
        assert rows[1].status == "ok"
        assert rows[2].status == "error"

    def test_unparseable_date_is_an_error(self) -> None:
        rows, _ = validate_rows([_row("C-1", "last tuesday", "1000", "0")], GOLDEN_MAPPING)
        assert rows[0].status == "error"
        assert any(i.field == "date_of_loss" for i in rows[0].issues)

    def test_negative_money_is_an_error(self) -> None:
        rows, _ = validate_rows([_row("C-1", "2027-09-14", "-1000", "0")], GOLDEN_MAPPING)
        assert rows[0].status == "error"

    def test_missing_incurred_without_paid_and_reserve_is_an_error(self) -> None:
        m = _map(claim_id="claim", date_of_loss="dol", currency="ccy")
        rows, _ = validate_rows([{"claim": "C-1", "dol": "2027-09-14", "ccy": "USD"}], m)
        assert rows[0].status == "error"
        assert any(i.field == "gross_incurred" for i in rows[0].issues)

    def test_errored_rows_do_not_count_toward_incurred_totals(self) -> None:
        _, report = validate_rows(
            [
                _row("C-1", "2027-09-14", "1000000.00", "0.00"),
                _row("C-2", "last tuesday", "9999999.00", "0.00"),  # bad date -> error, excluded
            ],
            GOLDEN_MAPPING,
        )
        assert report.gross_incurred_by_currency == {"USD": "1000000.00"}

    def test_incurred_mismatch_with_paid_plus_reserve_is_a_warning(self) -> None:
        m = _map(
            claim_id="claim",
            date_of_loss="dol",
            gross_paid="paid",
            gross_case_reserve="reserve",
            gross_incurred="inc",
            currency="ccy",
        )
        raw = [
            {
                "claim": "C-1",
                "dol": "2027-09-14",
                "paid": "1000000.00",
                "reserve": "500000.00",
                "inc": "2000000.00",  # != 1.5M
                "ccy": "USD",
            }
        ]
        rows, report = validate_rows(raw, m)
        assert rows[0].status == "warning"
        assert rows[0].is_committable
        assert report.committable == 1


def test_report_to_dict_is_json_safe() -> None:
    _, report = validate_rows([_row("C-1", "2027-09-14", "1000000.00", "0.00")], GOLDEN_MAPPING)
    payload = report.to_dict()
    assert payload["gross_incurred_by_currency"] == {"USD": "1000000.00"}
    assert isinstance(payload["issues"], list)
    # values are all primitives
    assert Decimal(payload["gross_incurred_by_currency"]["USD"]) == Decimal("1000000.00")
