"""Assemble, version, and review the Recovery Packet.

No AI here — the packet is a deterministic arrangement of already-produced
material (validated terms, the engine's calculation, the investigator's findings,
human decisions), each statement labelled FACT / CALCULATION / AI_INTERPRETATION /
HUMAN_DECISION (docs/AI_ARCHITECTURE.md §7). Versions are immutable; regenerating
writes a new one and supersedes the rest."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_correlation_id, get_logger
from app.db.models.extraction import Review
from app.db.models.recoveries import (
    RecoveryCalculation,
    RecoveryCandidate,
    RecoveryInvestigation,
    RecoveryPacket,
    RecoveryPacketVersion,
)
from app.domain.audit import ActorType, AuditRecord
from app.domain.recoveries import PacketInputs, assemble_packet, render_packet_html
from app.domain.recoveries.packet import PacketVersionStatus
from app.domain.reviews import ReviewDecision, ReviewSubjectType
from app.repositories.audit import AuditRepository
from app.repositories.extraction import ReviewRepository, TermCandidateRepository
from app.repositories.losses import LossEventRepository, UnderlyingLossRepository
from app.repositories.recoveries import (
    RecoveryCandidateRepository,
    RecoveryInvestigationRepository,
    RecoveryPacketRepository,
)
from app.repositories.reinsurance import TreatyRepository, TreatyVersionRepository
from app.services.auth import AuthenticatedContext
from app.services.errors import ConflictError, NotFoundError, ValidationError

log = get_logger(__name__)

_TERM_LABELS = {
    "attachment": "Attachment (retention)",
    "limit": "Limit",
    "currency": "Currency",
    "effective_date": "Effective date",
    "expiration_date": "Expiration date",
    "notice_provision": "Notice provision",
    "covered_perils": "Covered perils",
    "covered_business": "Covered business",
    "territory": "Territory",
    "event_definition": "Event definition",
    "hours_clause": "Hours clause",
    "reinstatements": "Reinstatements",
}
_PACKET_DECISIONS = (
    ReviewDecision.CONFIRM,
    ReviewDecision.REJECT,
    ReviewDecision.REQUEST_INFO,
    ReviewDecision.EDIT,
)


@dataclass(slots=True)
class PacketReview:
    decision: ReviewDecision
    reason: str | None = None
    statement_key: str | None = None
    value: str | None = None


class RecoveryPacketService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._packets = RecoveryPacketRepository(session)
        self._candidates = RecoveryCandidateRepository(session)
        self._investigations = RecoveryInvestigationRepository(session)
        self._treaties = TreatyRepository(session)
        self._versions = TreatyVersionRepository(session)
        self._term_candidates = TermCandidateRepository(session)
        self._events = LossEventRepository(session)
        self._losses = UnderlyingLossRepository(session)
        self._reviews = ReviewRepository(session)
        self._audit = AuditRepository(session)

    # --- reading -------------------------------------------------

    async def get_for_candidate(
        self, context: AuthenticatedContext, candidate_id: UUID
    ) -> RecoveryPacket:
        packet = await self._packets.for_candidate(context.organization.id, candidate_id)
        if packet is None:
            raise NotFoundError("no recovery packet has been generated for this candidate")
        return packet

    def current_version(self, packet: RecoveryPacket) -> RecoveryPacketVersion | None:
        return next((v for v in packet.versions if v.id == packet.current_version_id), None)

    async def version_html(
        self, context: AuthenticatedContext, version_id: UUID
    ) -> RecoveryPacketVersion:
        version = await self._packets.get_version(context.organization.id, version_id)
        if version is None:
            raise NotFoundError("packet version not found")
        return version

    # --- generate ----------------------------------------------

    async def generate(
        self, context: AuthenticatedContext, candidate_id: UUID
    ) -> RecoveryPacketVersion:
        org_id = context.organization.id
        candidate = await self._candidates.get(org_id, candidate_id)
        if candidate is None:
            raise NotFoundError("recovery candidate not found")
        calc = next(
            (c for c in candidate.calculations if c.id == candidate.current_calculation_id),
            None,
        )
        if calc is None:
            raise ConflictError("the candidate has no calculation to package")

        packet = await self._packets.for_candidate(org_id, candidate_id)
        existing_versions: list[RecoveryPacketVersion] = []
        if packet is None:
            packet = RecoveryPacket(
                organization_id=org_id,
                recovery_candidate_id=candidate_id,
                created_by=context.user.id,
            )
            self._packets.add(packet)
            await self._session.flush()
        else:
            existing_versions = list(packet.versions)

        inputs = await self._collect_inputs(context, candidate, calc, dict(packet.human_overrides))
        content = assemble_packet(inputs)
        html = render_packet_html(content)

        investigation = await self._current_investigation(org_id, candidate_id)
        next_no = 1 + max((v.version_no for v in existing_versions), default=0)
        version = RecoveryPacketVersion(
            organization_id=org_id,
            recovery_packet_id=packet.id,
            version_no=next_no,
            status=PacketVersionStatus.DRAFT,
            content=content.to_dict(),
            rendered_html=html,
            calculation_id=calc.id,
            investigation_id=investigation.id if investigation else None,
            generated_by=context.user.id,
        )
        self._session.add(version)
        await self._session.flush()

        now = dt.datetime.now(dt.UTC)
        for prior in existing_versions:
            if prior.superseded_at is None:
                prior.superseded_at = now
                if prior.status is PacketVersionStatus.DRAFT:
                    prior.status = PacketVersionStatus.SUPERSEDED
        packet.current_version_id = version.id

        self._audit.record(
            AuditRecord(
                organization_id=org_id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="recovery_packet.generated",
                entity_type="recovery_candidate",
                entity_id=candidate_id,
                summary=f"{context.user.email} generated recovery packet v{next_no}",
                payload={
                    "recovery_packet_id": str(packet.id),
                    "version_id": str(version.id),
                    "version_no": next_no,
                    "classes": sorted(c.value for c in content.classes_present()),
                },
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        refreshed = await self._packets.get_version(org_id, version.id)
        assert refreshed is not None
        return refreshed

    # --- review -----------------------------------------------

    async def review_version(
        self,
        context: AuthenticatedContext,
        packet_id: UUID,
        version_id: UUID,
        review: PacketReview,
    ) -> RecoveryPacketVersion:
        if review.decision not in _PACKET_DECISIONS:
            raise ValidationError(f"unsupported packet decision {review.decision.value!r}")

        org_id = context.organization.id
        packet = await self._packets.get(org_id, packet_id)
        if packet is None:
            raise NotFoundError("recovery packet not found")
        version = next((v for v in packet.versions if v.id == version_id), None)
        if version is None:
            raise NotFoundError("packet version not found")
        if version.id != packet.current_version_id:
            raise ConflictError("only the current packet version can be reviewed")
        if version.status in (PacketVersionStatus.APPROVED, PacketVersionStatus.REJECTED):
            raise ConflictError(f"this packet version is already {version.status.value}")

        status_before = version.status.value
        value_after: dict[str, object] = {"decision": review.decision.value}

        if review.decision is ReviewDecision.EDIT:
            if not review.statement_key or review.value is None:
                raise ValidationError("an edit needs a statement_key and a value")
            before = _statement_text(version.content, review.statement_key)
            if before is None:
                raise ValidationError(f"no statement {review.statement_key!r} in this packet")
            overrides = dict(packet.human_overrides)
            overrides[review.statement_key] = {
                "text": review.value,
                "reason": review.reason or "",
                "by": context.user.email,
            }
            packet.human_overrides = overrides
            value_after |= {"statement_key": review.statement_key, "value": review.value}
            self._reviews.add(
                Review(
                    organization_id=org_id,
                    subject_type=ReviewSubjectType.RECOVERY_PACKET,
                    subject_id=version.id,
                    reviewer_id=context.user.id,
                    decision=review.decision,
                    value_before={"statement_key": review.statement_key, "text": before},
                    value_after=value_after,
                    reason=review.reason,
                )
            )
            self._audit.record(self._audit_edit(context, packet, version, review.statement_key))
            await self._session.commit()
            return await self.generate(context, packet.recovery_candidate_id)

        if review.decision is ReviewDecision.CONFIRM:
            version.status = PacketVersionStatus.APPROVED
            version.approved_by = context.user.id
            version.approved_at = dt.datetime.now(dt.UTC)
        elif review.decision is ReviewDecision.REJECT:
            version.status = PacketVersionStatus.REJECTED
        else:  # REQUEST_INFO — packet stays a draft
            version.review_note = review.reason

        self._reviews.add(
            Review(
                organization_id=org_id,
                subject_type=ReviewSubjectType.RECOVERY_PACKET,
                subject_id=version.id,
                reviewer_id=context.user.id,
                decision=review.decision,
                value_before={"status": status_before},
                value_after=value_after | {"status": version.status.value},
                reason=review.reason,
            )
        )
        self._audit.record(
            AuditRecord(
                organization_id=org_id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="recovery_packet.reviewed",
                entity_type="recovery_candidate",
                entity_id=packet.recovery_candidate_id,
                summary=(
                    f"{context.user.email} {review.decision.value} recovery packet "
                    f"v{version.version_no}"
                ),
                payload={
                    "recovery_packet_id": str(packet.id),
                    "version_id": str(version.id),
                    "decision": review.decision.value,
                    "status": version.status.value,
                },
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        refreshed = await self._packets.get_version(org_id, version.id)
        assert refreshed is not None
        return refreshed

    # --- helpers ---------------------------------------------

    def _audit_edit(
        self,
        context: AuthenticatedContext,
        packet: RecoveryPacket,
        version: RecoveryPacketVersion,
        statement_key: str,
    ) -> AuditRecord:
        return AuditRecord(
            organization_id=context.organization.id,
            actor_type=ActorType.USER,
            actor_id=context.user.id,
            action="recovery_packet.statement_edited",
            entity_type="recovery_candidate",
            entity_id=packet.recovery_candidate_id,
            summary=f"{context.user.email} edited packet statement {statement_key!r}",
            payload={"recovery_packet_id": str(packet.id), "statement_key": statement_key},
            correlation_id=get_correlation_id(),
        )

    async def _current_investigation(
        self, organization_id: UUID, candidate_id: UUID
    ) -> RecoveryInvestigation | None:
        rows = await self._investigations.list_for_candidate(organization_id, candidate_id)
        return next(
            (r for r in rows if r.superseded_at is None and r.status.value == "completed"),
            rows[0] if rows else None,
        )

    async def _collect_inputs(
        self,
        context: AuthenticatedContext,
        candidate: RecoveryCandidate,
        calc: RecoveryCalculation,
        overrides: dict[str, dict[str, str]],
    ) -> PacketInputs:
        org_id = context.organization.id
        version = await self._versions.get(org_id, candidate.treaty_version_id)
        assert version is not None
        treaty = await self._treaties.get(org_id, candidate.treaty_id)
        assert treaty is not None
        layer = next((x for x in version.layers if x.id == candidate.treaty_layer_id), None)
        assert layer is not None

        # citations for validated terms, by key
        candidates = await self._term_candidates.list_for_version(org_id, version.id)
        citation_by_key: dict[str, dict[str, object]] = {}
        for c in candidates:
            if (
                c.resolution == "confirmed"
                and c.citation is not None
                and c.key not in citation_by_key
            ):
                citation_by_key[c.key] = {
                    "document_id": str(c.citation.document_id),
                    "page_number": c.citation.page_number,
                    "section": c.citation.section,
                    "quoted_text": c.citation.quoted_text,
                }

        validated_terms: list[dict[str, object]] = [
            {
                "key": "attachment",
                "label": _TERM_LABELS["attachment"],
                "value": f"{layer.currency} {layer.attachment}",
                "citation": citation_by_key.get("attachment"),
            },
            {
                "key": "limit",
                "label": _TERM_LABELS["limit"],
                "value": f"{layer.currency} {layer.limit}",
                "citation": citation_by_key.get("limit"),
            },
            {
                "key": "currency",
                "label": _TERM_LABELS["currency"],
                "value": layer.currency,
                "citation": citation_by_key.get("currency"),
            },
        ]
        for term in version.terms:
            if term.key in ("attachment", "limit", "currency"):
                continue
            validated_terms.append(
                {
                    "key": term.key,
                    "label": _TERM_LABELS.get(term.key, term.key.replace("_", " ").title()),
                    "value": str(term.value.get("value", term.value)),
                    "citation": citation_by_key.get(term.key),
                }
            )

        event = await self._events.get(org_id, candidate.loss_event_id)
        assert event is not None
        aggregates = await self._events.aggregates(org_id)
        totals = aggregates.get(event.id, {})
        losses = await self._losses.for_event(org_id, event.id)
        date_from = event.date_of_loss_from.isoformat() if event.date_of_loss_from else None
        date_to = event.date_of_loss_to.isoformat() if event.date_of_loss_to else None

        allocations = [
            {
                "reinsurer_name": a.reinsurer.name,
                "participation_share": f"{a.participation_share * 100:g}%",
                "allocated_recovery": str(a.allocated_recovery),
            }
            for a in calc.allocations
        ]

        investigation = await self._current_investigation(org_id, candidate.id)
        investigation_payload: dict[str, object] | None = None
        if investigation is not None and investigation.status.value == "completed":
            investigation_payload = {
                "summary": investigation.summary or "",
                "applicability": (
                    investigation.applicability_assessment.value
                    if investigation.applicability_assessment
                    else "unclear"
                ),
                "findings": [
                    {
                        "kind": f.kind.value,
                        "text": f.text,
                        "citation": (
                            {
                                "document_id": str(f.citation.document_id),
                                "page_number": f.citation.page_number,
                                "section": f.citation.section,
                                "quoted_text": f.citation.quoted_text,
                            }
                            if f.citation is not None
                            else None
                        ),
                    }
                    for f in investigation.findings
                ],
                "unresolved_questions": list(investigation.unresolved_questions),
            }

        reviews = await self._reviews.list_for_subject(org_id, candidate.id)
        review_payload = [
            {
                "kind": "candidate",
                "decision": r.decision.value,
                "reason": r.reason,
                "at": r.created_at.date().isoformat(),
            }
            for r in reviews
        ]

        return PacketInputs(
            treaty_name=treaty.name,
            cedent_name=treaty.program.cedent.name,
            program_name=treaty.program.name,
            layer_attachment=str(layer.attachment),
            layer_limit=str(layer.limit),
            currency=layer.currency,
            validated_terms=validated_terms,
            calculation={
                "gross_event_incurred": str(candidate.gross_event_incurred),
                "attachment": str(calc.attachment),
                "limit": str(calc.layer_limit),
                "amount_above_attachment": str(calc.amount_above_attachment),
                "layer_recovery": str(calc.layer_recovery),
                "cedent_retention": str(calc.cedent_retention),
                "total_ceded": str(calc.total_ceded),
                "engine_version": calc.engine_version,
                "trace": list(calc.trace),
                "allocations": allocations,
            },
            loss_event={
                "name": event.name,
                "event_identifier": event.event_identifier,
                "catastrophe_code": event.catastrophe_code,
                "date_from": date_from,
                "date_to": date_to,
                "totals": [
                    {"currency": ccy, "claim_count": count, "gross_incurred": str(total)}
                    for ccy, (count, total) in sorted(totals.items())
                ],
            },
            loss_count=len(losses),
            investigation=investigation_payload,
            reviews=review_payload,
            human_overrides=overrides,
            generated_at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        )


def _statement_text(content: dict, key: str) -> str | None:
    for section in content.get("sections", []):
        for statement in section.get("statements", []):
            if statement.get("key") == key:
                return statement.get("text")
    return None
