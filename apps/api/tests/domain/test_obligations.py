"""Notice deadlines are computed by deterministic code, never a model."""

from __future__ import annotations

import datetime as dt

import pytest

from app.domain.recoveries.obligations import (
    DeadlineBasis,
    NoticeTermSpec,
    NoticeTrigger,
    add_days,
    days_until,
    notice_deadline,
)


class TestNoticeTermSpec:
    def test_rejects_a_nonsense_period(self) -> None:
        with pytest.raises(ValueError):
            NoticeTermSpec(days=0, trigger=NoticeTrigger.KNOWLEDGE_OF_LOSS)
        with pytest.raises(ValueError):
            NoticeTermSpec(days=5000, trigger=NoticeTrigger.KNOWLEDGE_OF_LOSS)

    def test_describe_reads_like_the_clause(self) -> None:
        spec = NoticeTermSpec(days=30, trigger=NoticeTrigger.KNOWLEDGE_OF_LOSS)
        assert spec.describe().startswith("within 30 days of the date the cedent knew")
        one = NoticeTermSpec(
            days=1, trigger=NoticeTrigger.LOSS_OCCURRENCE, basis=DeadlineBasis.BUSINESS
        )
        assert one.describe() == "within 1 business day of the date of loss"

    def test_from_value_parses_the_structured_blob(self) -> None:
        spec = NoticeTermSpec.from_value(
            {
                "value": "within 30 days",
                "days": 30,
                "trigger": "loss_occurrence",
                "basis": "calendar",
            }
        )
        assert spec == NoticeTermSpec(30, NoticeTrigger.LOSS_OCCURRENCE, DeadlineBasis.CALENDAR)

    def test_from_value_returns_none_for_free_text_only(self) -> None:
        assert NoticeTermSpec.from_value({"value": "as soon as practicable"}) is None
        assert NoticeTermSpec.from_value("a bare string") is None
        assert NoticeTermSpec.from_value({"days": "not-a-number"}) is None

    def test_from_value_defaults_trigger_and_basis(self) -> None:
        spec = NoticeTermSpec.from_value({"days": 45})
        assert spec == NoticeTermSpec(45, NoticeTrigger.KNOWLEDGE_OF_LOSS, DeadlineBasis.CALENDAR)


class TestDeadlineMath:
    def test_calendar_days_add_straight_through(self) -> None:
        assert add_days(dt.date(2027, 9, 14), 30, DeadlineBasis.CALENDAR) == dt.date(2027, 10, 14)

    def test_business_days_skip_the_weekend(self) -> None:
        # Fri 2027-09-17 + 1 business day = Mon 2027-09-20
        assert add_days(dt.date(2027, 9, 17), 1, DeadlineBasis.BUSINESS) == dt.date(2027, 9, 20)
        # 5 business days from a Monday lands on the next Monday
        assert add_days(dt.date(2027, 9, 13), 5, DeadlineBasis.BUSINESS) == dt.date(2027, 9, 20)

    def test_notice_deadline_and_days_until(self) -> None:
        spec = NoticeTermSpec(days=30, trigger=NoticeTrigger.LOSS_OCCURRENCE)
        deadline = notice_deadline(dt.date(2027, 9, 14), spec)
        assert deadline == dt.date(2027, 10, 14)
        assert days_until(deadline, dt.date(2027, 10, 10)) == 4
        assert days_until(deadline, dt.date(2027, 10, 14)) == 0
        assert days_until(deadline, dt.date(2027, 10, 20)) == -6
