"""What to do next about an outstanding recoverable.

A deterministic hint from the leg's status, how long it has sat there, and how
overdue it is — not an AI recommendation. It tells the analyst where to push;
the analyst decides. Pure: standard library only (ADR-0010).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from app.domain.recoveries.collection import RecoverableStatus

# How long a leg can sit in a status before it needs a nudge.
_STALE_AFTER = {
    RecoverableStatus.PENDING: 3,
    RecoverableStatus.NOTIFIED: 21,
    RecoverableStatus.AGREED: 14,
    RecoverableStatus.BILLED: 30,
}


class NextAction(StrEnum):
    NOTIFY = "notify"
    CHASE_ACK = "chase_acknowledgement"
    ISSUE_BILL = "issue_bill"
    CHASE_PAYMENT = "chase_payment"
    RESOLVE_DISPUTE = "resolve_dispute"
    HOLD = "hold"
    DONE = "done"


@dataclass(frozen=True, slots=True)
class ChaseHint:
    action: NextAction
    text: str
    urgent: bool


def entered_status_on(
    status: RecoverableStatus,
    *,
    created_at: dt.datetime,
    notified_at: dt.datetime | None,
    agreed_at: dt.datetime | None,
    billed_at: dt.datetime | None,
    settled_at: dt.datetime | None,
    updated_at: dt.datetime,
) -> dt.datetime:
    """When the leg entered its current status — from the matching stamp, falling
    back to the last update (DISPUTED has no stamp) or creation (PENDING)."""
    stamp = {
        RecoverableStatus.PENDING: created_at,
        RecoverableStatus.NOTIFIED: notified_at,
        RecoverableStatus.AGREED: agreed_at,
        RecoverableStatus.BILLED: billed_at,
        RecoverableStatus.COLLECTED: settled_at,
        RecoverableStatus.WRITTEN_OFF: settled_at,
    }.get(status)
    return stamp or updated_at


def recommend_chase(
    *,
    status: RecoverableStatus,
    days_in_status: int,
    days_overdue: int,
) -> ChaseHint:
    overdue = days_overdue > 0
    stale = days_in_status >= _STALE_AFTER.get(status, 10_000)

    if status is RecoverableStatus.DISPUTED:
        return ChaseHint(
            NextAction.RESOLVE_DISPUTE,
            "Disputed — work the disagreement and record the outcome.",
            urgent=True,
        )
    if status in (RecoverableStatus.COLLECTED, RecoverableStatus.WRITTEN_OFF):
        return ChaseHint(NextAction.DONE, "Closed — nothing to do.", urgent=False)

    if status is RecoverableStatus.PENDING:
        return ChaseHint(
            NextAction.NOTIFY,
            "Materialised but not notified — send the reinsurer notice.",
            urgent=stale,
        )
    if status is RecoverableStatus.NOTIFIED:
        return ChaseHint(
            NextAction.CHASE_ACK,
            (
                f"Notified {days_in_status} days ago with no movement — chase an acknowledgement."
                if stale
                else "Notified — awaiting the reinsurer's acknowledgement."
            ),
            urgent=stale or overdue,
        )
    if status is RecoverableStatus.AGREED:
        return ChaseHint(
            NextAction.ISSUE_BILL,
            "Agreed — issue the bill.",
            urgent=stale or overdue,
        )
    # BILLED
    return ChaseHint(
        NextAction.CHASE_PAYMENT,
        (
            f"Billed {days_in_status} days ago and {days_overdue} days overdue — chase payment."
            if overdue
            else f"Billed {days_in_status} days ago — follow up on payment."
            if stale
            else "Billed — awaiting payment."
        ),
        urgent=overdue or stale,
    )
