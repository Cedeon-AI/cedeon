"""The ceded-reinsurance desk's attention queue: one prioritised list of
everything that needs a human, across every stage of the pipeline.

Each item is *derived* from concrete domain state (a recovery, a notice
obligation, a treaty version) — this is a read-model, not a stored object, so it
does not force a generalised "finding" abstraction onto the domain. It carries an
``AttentionCategory`` so the product can group Recovery, Obligation and Contract
work today and add Exception / Reconciliation intelligence later without a
rewrite.

Pure — standard library only, no AI, no I/O. The service layer gathers the raw
signals; this module turns them into typed items and ranks them. The ranking is
deterministic and explainable: every contribution to an item's urgency is a
named term (``urgency_terms``), never a model output.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

_ZERO = Decimal("0")


class AttentionCategory(StrEnum):
    """The intelligence area an item belongs to. Recovery is the wedge;
    Obligation and Contract are live today; Exception / Reconciliation are the
    next modules and get their own values when they land."""

    RECOVERY = "recovery"
    OBLIGATION = "obligation"
    CONTRACT = "contract"
    EXCEPTION = "exception"


class WorklistKind(StrEnum):
    """What kind of attention an item needs. Ordered roughly by how much a missed
    one costs — the base weight in ``_KIND_WEIGHT`` follows the same order."""

    NOTICE_DUE = "notice_due"
    RECOVERY_DRIFT = "recovery_drift"
    CONTRACT_CHANGE = "contract_change"
    RECONCILIATION_MISMATCH = "reconciliation_mismatch"
    STATEMENT_DISCREPANCY = "statement_discrepancy"
    REINSTATEMENT_DUE = "reinstatement_due"
    RECOVERY_REVIEW = "recovery_review"
    SUGGESTED_RECOVERY = "suggested_recovery"
    PACKET_APPROVAL = "packet_approval"
    TERM_VALIDATION = "term_validation"
    RECOVERABLE_OVERDUE = "recoverable_overdue"


_KIND_CATEGORY: dict[WorklistKind, AttentionCategory] = {
    WorklistKind.NOTICE_DUE: AttentionCategory.OBLIGATION,
    WorklistKind.RECOVERY_DRIFT: AttentionCategory.RECOVERY,
    WorklistKind.CONTRACT_CHANGE: AttentionCategory.CONTRACT,
    WorklistKind.RECONCILIATION_MISMATCH: AttentionCategory.EXCEPTION,
    WorklistKind.STATEMENT_DISCREPANCY: AttentionCategory.EXCEPTION,
    WorklistKind.REINSTATEMENT_DUE: AttentionCategory.OBLIGATION,
    WorklistKind.RECOVERY_REVIEW: AttentionCategory.RECOVERY,
    WorklistKind.SUGGESTED_RECOVERY: AttentionCategory.RECOVERY,
    WorklistKind.PACKET_APPROVAL: AttentionCategory.RECOVERY,
    WorklistKind.TERM_VALIDATION: AttentionCategory.CONTRACT,
    WorklistKind.RECOVERABLE_OVERDUE: AttentionCategory.RECOVERY,
}


def category_for(kind: WorklistKind) -> AttentionCategory:
    return _KIND_CATEGORY[kind]


# A missed notice contests a recovery; a stale number mis-books an asset; a
# contract change under an open recovery invalidates its basis; a reconciliation
# mismatch is money not landing as expected; a review or approval is a queue that
# has already been triaged; an overdue recoverable is chased continuously.
_KIND_WEIGHT: dict[WorklistKind, int] = {
    WorklistKind.NOTICE_DUE: 600,
    WorklistKind.RECOVERY_DRIFT: 500,
    WorklistKind.CONTRACT_CHANGE: 450,
    WorklistKind.RECONCILIATION_MISMATCH: 400,
    WorklistKind.STATEMENT_DISCREPANCY: 380,
    WorklistKind.REINSTATEMENT_DUE: 350,
    WorklistKind.RECOVERY_REVIEW: 300,
    WorklistKind.SUGGESTED_RECOVERY: 250,
    WorklistKind.PACKET_APPROVAL: 200,
    WorklistKind.TERM_VALIDATION: 150,
    WorklistKind.RECOVERABLE_OVERDUE: 100,
}

# Tuning constants — all deterministic, all here so the ranking is one function.
_DEADLINE_HORIZON_DAYS = 14  # inside this window, a deadline starts adding urgency
_DEADLINE_PER_DAY = 40  # each day closer (or past) adds this much
_DEADLINE_CAP = 500  # ... up to here
_AGE_PER_DAY = 2
_AGE_CAP = 220
_AMOUNT_DIVISOR = Decimal("100000")  # one urgency point per $100k at stake
_AMOUNT_CAP = 160


@dataclass(frozen=True, slots=True)
class UrgencyTerm:
    label: str
    points: int


@dataclass(frozen=True, slots=True)
class WorklistItem:
    kind: WorklistKind
    key: str
    """Stable identity — dedupes and serves as the React key. ``<kind>:<uuid>``."""
    title: str
    detail: str
    href: str
    amount: Decimal | None = None
    currency: str | None = None
    due_in_days: int | None = None
    """Days until a contractual deadline. Negative means overdue. ``None`` = no clock."""
    age_days: int | None = None
    """How long this has been waiting."""
    urgency: int = 0
    urgency_terms: tuple[UrgencyTerm, ...] = field(default_factory=tuple)

    @property
    def category(self) -> AttentionCategory:
        return _KIND_CATEGORY[self.kind]


def score_urgency(
    *,
    kind: WorklistKind,
    due_in_days: int | None = None,
    age_days: int | None = None,
    amount: Decimal | None = None,
) -> tuple[int, tuple[UrgencyTerm, ...]]:
    """Deterministic urgency for one item. Returns the total and the breakdown so
    the UI can show *why* something is near the top."""
    terms: list[UrgencyTerm] = [UrgencyTerm(f"{kind.value} baseline", _KIND_WEIGHT[kind])]

    if due_in_days is not None and due_in_days <= _DEADLINE_HORIZON_DAYS:
        pressure = min((_DEADLINE_HORIZON_DAYS - due_in_days) * _DEADLINE_PER_DAY, _DEADLINE_CAP)
        if pressure > 0:
            label = (
                f"overdue by {abs(due_in_days)}d" if due_in_days < 0 else f"due in {due_in_days}d"
            )
            terms.append(UrgencyTerm(label, pressure))

    if age_days and age_days > 0:
        terms.append(UrgencyTerm(f"waiting {age_days}d", min(age_days * _AGE_PER_DAY, _AGE_CAP)))

    if amount is not None and amount > _ZERO:
        pts = min(int(amount / _AMOUNT_DIVISOR), _AMOUNT_CAP)
        if pts > 0:
            terms.append(UrgencyTerm("amount at stake", pts))

    return sum(t.points for t in terms), tuple(terms)


def rank(items: Iterable[WorklistItem]) -> list[WorklistItem]:
    """Score every item and return them worst-first. Ties break by the tightest
    deadline, then the largest amount, then the key (stable)."""
    scored = [
        WorklistItem(
            kind=it.kind,
            key=it.key,
            title=it.title,
            detail=it.detail,
            href=it.href,
            amount=it.amount,
            currency=it.currency,
            due_in_days=it.due_in_days,
            age_days=it.age_days,
            urgency=score,
            urgency_terms=terms,
        )
        for it in items
        for score, terms in [
            score_urgency(
                kind=it.kind,
                due_in_days=it.due_in_days,
                age_days=it.age_days,
                amount=it.amount,
            )
        ]
    ]
    scored.sort(
        key=lambda it: (
            -it.urgency,
            it.due_in_days if it.due_in_days is not None else 10_000,
            -(it.amount or _ZERO),
            it.key,
        )
    )
    return scored
