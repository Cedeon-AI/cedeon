"""The recovery-suggestion screen is deterministic — currency, window, attachment."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from app.domain.recoveries.suggestions import (
    EventFacts,
    LayerWindow,
    Suggestion,
    SuggestionMiss,
    evaluate_suggestion,
)

_LAYER = LayerWindow(
    currency="USD",
    attachment=Decimal("50000000.00"),
    limit=Decimal("20000000.00"),
    effective_date=dt.date(2027, 1, 1),
    expiration_date=dt.date(2027, 12, 31),
)


def _event(**kw: object) -> EventFacts:
    base: dict[str, object] = {
        "currency": "USD",
        "date_from": dt.date(2027, 9, 14),
        "date_to": dt.date(2027, 9, 16),
        "gross_in_currency": Decimal("58700000.00"),
    }
    base.update(kw)
    return EventFacts(**base)  # type: ignore[arg-type]


class TestEvaluate:
    def test_the_golden_event_is_suggested_with_an_indicative_recovery(self) -> None:
        out = evaluate_suggestion(_event(), _LAYER, has_open_candidate=False)
        assert isinstance(out, Suggestion)
        assert out.indicative_recovery == Decimal("8700000.00")
        assert "above the 50000000.00 attachment" in out.reason

    def test_indicative_recovery_is_capped_at_the_limit(self) -> None:
        out = evaluate_suggestion(
            _event(gross_in_currency=Decimal("90000000.00")), _LAYER, has_open_candidate=False
        )
        assert isinstance(out, Suggestion)
        assert out.indicative_recovery == Decimal("20000000.00")

    def test_gross_at_or_below_attachment_is_not_suggested(self) -> None:
        assert (
            evaluate_suggestion(
                _event(gross_in_currency=Decimal("50000000.00")), _LAYER, has_open_candidate=False
            )
            is SuggestionMiss.BELOW_ATTACHMENT
        )

    def test_nothing_in_the_layer_currency_is_a_currency_miss(self) -> None:
        assert (
            evaluate_suggestion(
                _event(gross_in_currency=Decimal("0")), _LAYER, has_open_candidate=False
            )
            is SuggestionMiss.CURRENCY
        )

    def test_a_loss_before_the_treaty_incepts_is_out_of_window(self) -> None:
        assert (
            evaluate_suggestion(
                _event(date_from=dt.date(2026, 12, 20), date_to=dt.date(2026, 12, 22)),
                _LAYER,
                has_open_candidate=False,
            )
            is SuggestionMiss.WINDOW
        )

    def test_an_undated_event_is_not_excluded_on_the_window(self) -> None:
        out = evaluate_suggestion(
            _event(date_from=None, date_to=None), _LAYER, has_open_candidate=False
        )
        assert isinstance(out, Suggestion)

    def test_an_existing_candidate_suppresses_the_suggestion(self) -> None:
        assert (
            evaluate_suggestion(_event(), _LAYER, has_open_candidate=True)
            is SuggestionMiss.ALREADY_OPEN
        )
