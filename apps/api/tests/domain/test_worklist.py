"""The worklist ranking is deterministic and explainable — assert both."""

from __future__ import annotations

from decimal import Decimal

from app.domain.worklist import (
    WorklistItem,
    WorklistKind,
    rank,
    score_urgency,
)


def _item(kind: WorklistKind, key: str, **kw: object) -> WorklistItem:
    return WorklistItem(kind=kind, key=key, title=key, detail="", href="/", **kw)  # type: ignore[arg-type]


class TestScoreUrgency:
    def test_baseline_only_when_nothing_else_applies(self) -> None:
        score, terms = score_urgency(kind=WorklistKind.TERM_VALIDATION)
        assert score == 150
        assert [t.label for t in terms] == ["term_validation baseline"]

    def test_a_deadline_inside_the_horizon_adds_pressure(self) -> None:
        near, _ = score_urgency(kind=WorklistKind.NOTICE_DUE, due_in_days=2)
        far, _ = score_urgency(kind=WorklistKind.NOTICE_DUE, due_in_days=30)
        assert far == 600  # outside the 14-day horizon — baseline only
        assert near > far

    def test_overdue_outranks_merely_due(self) -> None:
        due, _ = score_urgency(kind=WorklistKind.NOTICE_DUE, due_in_days=3)
        overdue, terms = score_urgency(kind=WorklistKind.NOTICE_DUE, due_in_days=-3)
        assert overdue > due
        assert any(t.label == "overdue by 3d" for t in terms)

    def test_amount_and_age_contribute_and_cap(self) -> None:
        _, terms = score_urgency(
            kind=WorklistKind.RECOVERY_REVIEW,
            age_days=1000,
            amount=Decimal("999000000"),
        )
        by_label = {t.label: t.points for t in terms}
        assert by_label["waiting 1000d"] == 220  # age cap
        assert by_label["amount at stake"] == 160  # amount cap

    def test_zero_and_none_amount_add_nothing(self) -> None:
        a, _ = score_urgency(kind=WorklistKind.RECOVERY_REVIEW, amount=Decimal("0"))
        b, _ = score_urgency(kind=WorklistKind.RECOVERY_REVIEW, amount=None)
        assert a == b == 300


class TestRank:
    def test_a_notice_due_friday_outranks_a_packet_awaiting_signature(self) -> None:
        items = [
            _item(WorklistKind.PACKET_APPROVAL, "packet:1", amount=Decimal("8700000")),
            _item(WorklistKind.NOTICE_DUE, "notice:1", due_in_days=2, amount=Decimal("4350000")),
        ]
        ranked = rank(items)
        assert ranked[0].key == "notice:1"

    def test_ranking_is_stable_and_total_order(self) -> None:
        items = [
            _item(WorklistKind.RECOVERY_REVIEW, "r:b"),
            _item(WorklistKind.RECOVERY_REVIEW, "r:a"),
        ]
        ranked = rank(items)
        assert [i.key for i in ranked] == ["r:a", "r:b"]  # tie broken by key

    def test_overdue_recoverable_beats_a_fresh_one_of_the_same_kind(self) -> None:
        items = [
            _item(WorklistKind.RECOVERABLE_OVERDUE, "rec:fresh", due_in_days=-1),
            _item(WorklistKind.RECOVERABLE_OVERDUE, "rec:aged", due_in_days=-90),
        ]
        ranked = rank(items)
        assert ranked[0].key == "rec:aged"

    def test_every_ranked_item_carries_its_breakdown(self) -> None:
        ranked = rank([_item(WorklistKind.RECOVERY_DRIFT, "d:1", amount=Decimal("2000000"))])
        assert ranked[0].urgency == sum(t.points for t in ranked[0].urgency_terms)
