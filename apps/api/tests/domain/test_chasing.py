"""The next-action hint for an outstanding recoverable is a deterministic rule."""

from __future__ import annotations

import datetime as dt

from app.domain.recoveries.chasing import NextAction, entered_status_on, recommend_chase
from app.domain.recoveries.collection import RecoverableStatus


class TestRecommendChase:
    def test_pending_says_send_the_notice(self) -> None:
        hint = recommend_chase(status=RecoverableStatus.PENDING, days_in_status=1, days_overdue=0)
        assert hint.action is NextAction.NOTIFY
        assert hint.urgent is False

    def test_notified_and_quiet_becomes_a_chase(self) -> None:
        fresh = recommend_chase(status=RecoverableStatus.NOTIFIED, days_in_status=5, days_overdue=0)
        stale = recommend_chase(
            status=RecoverableStatus.NOTIFIED, days_in_status=40, days_overdue=0
        )
        assert fresh.action is NextAction.CHASE_ACK and fresh.urgent is False
        assert stale.urgent is True
        assert "40 days ago" in stale.text

    def test_agreed_says_issue_the_bill(self) -> None:
        assert (
            recommend_chase(
                status=RecoverableStatus.AGREED, days_in_status=2, days_overdue=0
            ).action
            is NextAction.ISSUE_BILL
        )

    def test_billed_and_overdue_is_an_urgent_payment_chase(self) -> None:
        hint = recommend_chase(status=RecoverableStatus.BILLED, days_in_status=45, days_overdue=15)
        assert hint.action is NextAction.CHASE_PAYMENT
        assert hint.urgent is True
        assert "15 days overdue" in hint.text

    def test_disputed_is_always_urgent(self) -> None:
        assert (
            recommend_chase(
                status=RecoverableStatus.DISPUTED, days_in_status=1, days_overdue=0
            ).urgent
            is True
        )

    def test_closed_legs_have_nothing_to_do(self) -> None:
        for s in (RecoverableStatus.COLLECTED, RecoverableStatus.WRITTEN_OFF):
            assert (
                recommend_chase(status=s, days_in_status=1, days_overdue=0).action
                is NextAction.DONE
            )


class TestEnteredStatusOn:
    def test_uses_the_matching_stamp(self) -> None:
        created = dt.datetime(2027, 1, 1, tzinfo=dt.UTC)
        billed = dt.datetime(2027, 3, 1, tzinfo=dt.UTC)
        got = entered_status_on(
            RecoverableStatus.BILLED,
            created_at=created,
            notified_at=dt.datetime(2027, 2, 1, tzinfo=dt.UTC),
            agreed_at=dt.datetime(2027, 2, 15, tzinfo=dt.UTC),
            billed_at=billed,
            settled_at=None,
            updated_at=dt.datetime(2027, 4, 1, tzinfo=dt.UTC),
        )
        assert got == billed

    def test_disputed_falls_back_to_updated_at(self) -> None:
        updated = dt.datetime(2027, 4, 1, tzinfo=dt.UTC)
        got = entered_status_on(
            RecoverableStatus.DISPUTED,
            created_at=dt.datetime(2027, 1, 1, tzinfo=dt.UTC),
            notified_at=None,
            agreed_at=None,
            billed_at=None,
            settled_at=None,
            updated_at=updated,
        )
        assert got == updated
