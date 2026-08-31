"""Contractual notice obligations for a recovery: read the validated notice
provision, pick the reference date its trigger points at, and let deterministic
code compute the deadline. The AI never computes the date (ADR-0010, ADR-0011).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_correlation_id
from app.db.models.recoveries import RecoveryCandidate
from app.db.models.reinsurance import TreatyTerm
from app.domain.audit import ActorType, AuditRecord
from app.domain.recoveries import (
    NoticeStatus,
    NoticeTermSpec,
    NoticeTrigger,
    days_until,
    notice_deadline,
)
from app.domain.treaties import TermStatus
from app.repositories.audit import AuditRepository
from app.repositories.losses import LossEventRepository, UnderlyingLossRepository
from app.repositories.recoveries import RecoveryCandidateRepository, RecoveryNoticeRepository
from app.repositories.reinsurance import TreatyVersionRepository
from app.services.auth import AuthenticatedContext
from app.services.errors import NotFoundError, ValidationError

_REFERENCE_LABEL = {
    NoticeTrigger.LOSS_OCCURRENCE: "date of loss",
    NoticeTrigger.KNOWLEDGE_OF_LOSS: "date of knowledge",
    NoticeTrigger.CLAIM_ADVICE: "first claim advice",
}


@dataclass(slots=True)
class NoticeObligation:
    provision_text: str | None
    spec: NoticeTermSpec | None
    reference_date: dt.date | None
    reference_label: str | None
    deadline: dt.date | None
    days_until: int | None
    satisfied: bool
    satisfied_on: dt.date | None
    note: str | None


class ObligationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._versions = TreatyVersionRepository(session)
        self._candidates = RecoveryCandidateRepository(session)
        self._notices = RecoveryNoticeRepository(session)
        self._events = LossEventRepository(session)
        self._losses = UnderlyingLossRepository(session)
        self._audit = AuditRepository(session)

    async def set_notice_term(
        self,
        context: AuthenticatedContext,
        version_id: UUID,
        *,
        provision_text: str,
        spec: NoticeTermSpec | None,
    ) -> None:
        """Set (or replace) the ``notice_provision`` term on a treaty version.

        This is operational metadata — it drives deadline reminders, not the
        executable ``$limit xs $attachment`` layer — so unlike the money terms it
        may be edited after the version is validated. Every change is audited.
        """
        org_id = context.organization.id
        version = await self._versions.get(org_id, version_id)
        if version is None:
            raise NotFoundError("treaty version not found")
        text = provision_text.strip()
        if not text:
            raise ValidationError("the notice provision text is required")

        payload: dict[str, object] = {"value": text}
        if spec is not None:
            payload |= spec.to_dict()

        term = next((t for t in version.terms if t.key == "notice_provision"), None)
        if term is None:
            version.terms.append(
                TreatyTerm(
                    organization_id=org_id,
                    treaty_version_id=version.id,
                    key="notice_provision",
                    value=payload,
                    status=TermStatus.CONFIRMED,
                )
            )
        else:
            term.value = payload
            term.status = TermStatus.CONFIRMED

        self._audit.record(
            AuditRecord(
                organization_id=org_id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="treaty_term.notice_provision_set",
                entity_type="treaty_version",
                entity_id=version.id,
                summary=f"{context.user.email} set the notice provision",
                payload={
                    "structured": spec is not None,
                    **({} if spec is None else spec.to_dict()),
                },
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()

    async def set_knowledge_date(
        self, context: AuthenticatedContext, candidate_id: UUID, knowledge_date: dt.date | None
    ) -> RecoveryCandidate:
        candidate = await self._candidates.get(context.organization.id, candidate_id)
        if candidate is None:
            raise NotFoundError("recovery candidate not found")
        candidate.knowledge_date = knowledge_date
        self._audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="recovery_candidate.knowledge_date_set",
                entity_type="recovery_candidate",
                entity_id=candidate.id,
                summary=(
                    f"{context.user.email} set the date of knowledge to "
                    f"{knowledge_date.isoformat() if knowledge_date else 'unset'}"
                ),
                payload={"knowledge_date": knowledge_date.isoformat() if knowledge_date else None},
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        refreshed = await self._candidates.get(context.organization.id, candidate_id)
        assert refreshed is not None
        return refreshed

    async def for_candidate(
        self, context: AuthenticatedContext, candidate: RecoveryCandidate
    ) -> NoticeObligation | None:
        org_id = context.organization.id
        version = await self._versions.get(org_id, candidate.treaty_version_id)
        term = (
            next((t for t in version.terms if t.key == "notice_provision"), None)
            if version is not None
            else None
        )
        if term is None:
            return None

        provision_text = str(term.value.get("value")) if term.value.get("value") else None
        spec = NoticeTermSpec.from_value(term.value)

        satisfied_on = await self._latest_approved_notice_date(org_id, candidate.id)

        if spec is None:
            return NoticeObligation(
                provision_text=provision_text,
                spec=None,
                reference_date=None,
                reference_label=None,
                deadline=None,
                days_until=None,
                satisfied=satisfied_on is not None,
                satisfied_on=satisfied_on,
                note="No structured deadline — add the period, trigger and basis on the treaty.",
            )

        reference_date, note = await self._reference_date(org_id, candidate, spec.trigger)
        deadline = notice_deadline(reference_date, spec) if reference_date is not None else None
        today = dt.datetime.now(dt.UTC).date()
        return NoticeObligation(
            provision_text=provision_text,
            spec=spec,
            reference_date=reference_date,
            reference_label=_REFERENCE_LABEL[spec.trigger],
            deadline=deadline,
            days_until=days_until(deadline, today) if deadline is not None else None,
            satisfied=satisfied_on is not None,
            satisfied_on=satisfied_on,
            note=note,
        )

    # --- helpers -------------------------------------------------

    async def _reference_date(
        self, org_id: UUID, candidate: RecoveryCandidate, trigger: NoticeTrigger
    ) -> tuple[dt.date | None, str | None]:
        event = await self._events.get(org_id, candidate.loss_event_id)
        loss_from = event.date_of_loss_from if event is not None else None

        if trigger is NoticeTrigger.LOSS_OCCURRENCE:
            if loss_from is None:
                return None, "The loss event has no dated losses."
            return loss_from, None

        if trigger is NoticeTrigger.KNOWLEDGE_OF_LOSS:
            if candidate.knowledge_date is not None:
                return candidate.knowledge_date, None
            return loss_from, "Assuming the date of loss — set the date of knowledge to be exact."

        # CLAIM_ADVICE
        losses = await self._losses.for_event(org_id, candidate.loss_event_id)
        advised = [x.reported_date for x in losses if x.reported_date is not None]
        if advised:
            return min(advised), None
        return loss_from, "No claim advice dates on the schedule — assuming the date of loss."

    async def _latest_approved_notice_date(
        self, org_id: UUID, candidate_id: UUID
    ) -> dt.date | None:
        notices = await self._notices.list_for_candidate(org_id, candidate_id)
        approved_at = [
            n.approved_at
            for n in notices
            if n.status is NoticeStatus.APPROVED and n.approved_at is not None
        ]
        return max(approved_at).date() if approved_at else None
