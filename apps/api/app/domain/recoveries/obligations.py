"""Contractual notice / reporting obligations, made operable.

A treaty's notice provision is validated as free text *and*, where the analyst
can state it, as a structured ``NoticeTermSpec`` (how many days, from what
trigger, counted how). Deterministic code then turns that plus a reference date
into a real deadline — the AI never computes the date.

Pure: standard library only. No AI, no I/O (ADR-0010, ADR-0011).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class NoticeTrigger(StrEnum):
    """What starts the notice clock. Which date the service passes as the
    reference depends on this."""

    LOSS_OCCURRENCE = "loss_occurrence"
    KNOWLEDGE_OF_LOSS = "knowledge_of_loss"
    CLAIM_ADVICE = "claim_advice"


_TRIGGER_LABEL = {
    NoticeTrigger.LOSS_OCCURRENCE: "the date of loss",
    NoticeTrigger.KNOWLEDGE_OF_LOSS: (
        "the date the cedent knew a loss was likely to involve the treaty"
    ),
    NoticeTrigger.CLAIM_ADVICE: "the date the claim was first advised",
}


class DeadlineBasis(StrEnum):
    CALENDAR = "calendar"
    BUSINESS = "business"


@dataclass(frozen=True, slots=True)
class NoticeTermSpec:
    days: int
    trigger: NoticeTrigger
    basis: DeadlineBasis = DeadlineBasis.CALENDAR

    def __post_init__(self) -> None:
        if self.days < 1 or self.days > 1000:
            raise ValueError(f"notice period must be 1..1000 days, got {self.days}")

    @property
    def trigger_label(self) -> str:
        return _TRIGGER_LABEL[self.trigger]

    def describe(self) -> str:
        unit = "business day" if self.basis is DeadlineBasis.BUSINESS else "day"
        s = "" if self.days == 1 else "s"
        return f"within {self.days} {unit}{s} of {self.trigger_label}"

    def to_dict(self) -> dict[str, Any]:
        return {"days": self.days, "trigger": self.trigger.value, "basis": self.basis.value}

    @classmethod
    def from_value(cls, value: Any) -> NoticeTermSpec | None:
        """Parse the structured part out of a ``treaty_terms.value`` JSONB blob.
        Returns ``None`` when the term carries only free text."""
        if not isinstance(value, dict) or value.get("days") is None:
            return None
        try:
            days = int(value["days"])
            trigger = NoticeTrigger(str(value.get("trigger", NoticeTrigger.KNOWLEDGE_OF_LOSS)))
            basis = DeadlineBasis(str(value.get("basis", DeadlineBasis.CALENDAR)))
            return cls(days=days, trigger=trigger, basis=basis)
        except (ValueError, TypeError):
            return None


def add_days(start: dt.date, days: int, basis: DeadlineBasis) -> dt.date:
    """``start`` plus ``days``. Calendar days add straight through; business days
    skip Saturdays and Sundays (no holiday calendar — treaties rarely specify one,
    and a conservative deadline is the safe error)."""
    if basis is DeadlineBasis.CALENDAR:
        return start + dt.timedelta(days=days)
    out = start
    added = 0
    while added < days:
        out += dt.timedelta(days=1)
        if out.weekday() < 5:  # Mon-Fri
            added += 1
    return out


def notice_deadline(reference_date: dt.date, spec: NoticeTermSpec) -> dt.date:
    """The date by which notice must be given."""
    return add_days(reference_date, spec.days, spec.basis)


def days_until(deadline: dt.date, as_of: dt.date) -> int:
    """Whole days from ``as_of`` to ``deadline``. Positive = days remaining,
    zero = due today, negative = overdue."""
    return (deadline - as_of).days
