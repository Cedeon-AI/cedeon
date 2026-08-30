"""The human validation workspace: review term candidates, then freeze the treaty
version into an executable layer + participations."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_correlation_id
from app.db.models.documents import DocumentPage
from app.db.models.extraction import Review, TreatyTermCandidate
from app.db.models.reinsurance import (
    TreatyLayer,
    TreatyParticipation,
    TreatyTerm,
    TreatyVersion,
)
from app.domain.audit import ActorType, AuditRecord
from app.domain.money import Money, MoneyError
from app.domain.reviews import ReviewDecision, ReviewSubjectType
from app.domain.treaties import TermStatus, TreatyVersionStatus
from app.repositories.audit import AuditRepository
from app.repositories.documents import DocumentRepository
from app.repositories.extraction import ReviewRepository, TermCandidateRepository
from app.repositories.reinsurance import ReinsurerRepository, TreatyVersionRepository
from app.services.auth import AuthenticatedContext
from app.services.errors import ConflictError, NotFoundError, ValidationError

_LAYER_KEYS = ("attachment", "limit", "currency")
_SHARE_EPSILON = Decimal("0.0001")


@dataclass(slots=True)
class CandidateReview:
    decision: ReviewDecision
    value: str | None = None
    currency: str | None = None
    reason: str | None = None


class ValidationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._versions = TreatyVersionRepository(session)
        self._candidates = TermCandidateRepository(session)
        self._reviews = ReviewRepository(session)
        self._reinsurers = ReinsurerRepository(session)
        self._documents = DocumentRepository(session)
        self._audit = AuditRepository(session)

    # --- reading -------------------------------------------------------

    async def list_candidates(
        self, context: AuthenticatedContext, treaty_version_id: UUID
    ) -> tuple[TreatyVersion, list[TreatyTermCandidate], list[DocumentPage]]:
        version = await self._require_version(context, treaty_version_id)
        candidates = await self._candidates.list_for_version(
            context.organization.id, treaty_version_id
        )
        pages: list[DocumentPage] = []
        if version.source_document_id is not None:
            parse = await self._documents.current_parse(
                context.organization.id, version.source_document_id
            )
            if parse is not None:
                pages = await self._documents.list_pages(context.organization.id, parse.id)
        return version, candidates, pages

    async def candidate_reviews(
        self, context: AuthenticatedContext, candidate_id: UUID
    ) -> list[Review]:
        return await self._reviews.list_for_subject(context.organization.id, candidate_id)

    # --- reviewing ---------------------------------------------------

    async def review_candidate(
        self,
        context: AuthenticatedContext,
        treaty_version_id: UUID,
        candidate_id: UUID,
        review: CandidateReview,
    ) -> TreatyTermCandidate:
        version = await self._require_version(context, treaty_version_id)
        if version.status.is_frozen:
            raise ConflictError("this treaty version is already validated")

        candidate = await self._candidates.get(context.organization.id, candidate_id)
        if candidate is None or candidate.treaty_version_id != treaty_version_id:
            raise NotFoundError("term candidate not found")

        value_before = {
            "status": candidate.status.value,
            "value": candidate.raw_value,
            "resolution": candidate.resolution,
        }
        value_after: dict[str, object] = {"decision": review.decision.value}

        if review.decision in (ReviewDecision.CONFIRM, ReviewDecision.EDIT):
            resolved_value = (
                review.value
                if review.decision is ReviewDecision.EDIT
                else _candidate_value(candidate)
            )
            resolved_currency = review.currency or candidate.currency or version.currency
            self._apply_confirmed(version, candidate, resolved_value, resolved_currency)
            value_after["value"] = resolved_value
            value_after["currency"] = resolved_currency
            candidate.resolution = "confirmed"
        elif review.decision is ReviewDecision.REJECT:
            self._remove_confirmed(version, candidate)
            candidate.resolution = "rejected"
        elif review.decision is ReviewDecision.MARK_AMBIGUOUS:
            candidate.resolution = "ambiguous"
        elif review.decision is ReviewDecision.REQUEST_INFO:
            candidate.resolution = "info_requested"

        self._reviews.add(
            Review(
                organization_id=context.organization.id,
                subject_type=ReviewSubjectType.TREATY_TERM_CANDIDATE,
                subject_id=candidate.id,
                reviewer_id=context.user.id,
                decision=review.decision,
                value_before=value_before,
                value_after=value_after,
                reason=review.reason,
            )
        )
        self._audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="treaty_term_candidate.reviewed",
                entity_type="treaty_term_candidate",
                entity_id=candidate.id,
                summary=f"{context.user.email} {review.decision.value} {candidate.key!r}",
                payload={"treaty_version_id": str(version.id), "decision": review.decision.value},
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        refreshed = await self._candidates.get(context.organization.id, candidate_id)
        assert refreshed is not None
        return refreshed

    # --- validating ------------------------------------------------

    async def validate_version(
        self, context: AuthenticatedContext, treaty_version_id: UUID
    ) -> TreatyVersion:
        version = await self._require_version(context, treaty_version_id)
        if version.status is TreatyVersionStatus.VALIDATED:
            return version
        if version.status not in (
            TreatyVersionStatus.NEEDS_VALIDATION,
            TreatyVersionStatus.EXTRACTING,
        ):
            raise ConflictError(
                f"treaty version cannot be validated from status {version.status.value!r}"
            )

        confirmed = {t.key: t for t in version.terms if t.status is TermStatus.CONFIRMED}
        missing = [k for k in ("attachment", "limit") if k not in confirmed]
        if missing:
            raise ValidationError(
                f"confirm {', '.join(missing)} before validating the treaty",
                detail={"missing": missing},
            )
        currency = version.currency
        if not currency and "currency" in confirmed:
            currency = str(confirmed["currency"].value.get("value") or "").strip() or None
        if not currency:
            raise ValidationError("confirm the treaty currency before validating")
        currency = currency.upper()[:3]

        try:
            attachment = Money(Decimal(str(confirmed["attachment"].value["value"])), currency)
            limit = Money(Decimal(str(confirmed["limit"].value["value"])), currency)
        except (KeyError, TypeError, InvalidOperation, MoneyError) as exc:
            raise ValidationError(f"confirmed attachment/limit is not valid money: {exc}") from exc
        attachment.require_non_negative("attachment")
        if not limit.is_positive:
            raise ValidationError("limit must be greater than zero")

        if not version.participations:
            raise ValidationError("confirm at least one reinsurer participation before validating")
        share_sum = sum((p.placed_share for p in version.participations), Decimal("0"))
        if share_sum > Decimal("1") + _SHARE_EPSILON:
            raise ValidationError(
                f"placed shares sum to {share_sum} (> 100%)",
                detail={"share_sum": str(share_sum)},
            )

        # Materialise the executable layer.
        for existing in list(version.layers):
            await self._session.delete(existing)
        version.layers.clear()
        version.layers.append(
            TreatyLayer(
                organization_id=context.organization.id,
                treaty_version_id=version.id,
                layer_no=1,
                attachment=attachment.amount,
                limit=limit.amount,
                currency=currency,
            )
        )

        version.currency = currency
        version.status = TreatyVersionStatus.VALIDATED
        version.validated_at = dt.datetime.now(dt.UTC)
        version.validated_by = context.user.id

        self._audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="treaty_version.validated",
                entity_type="treaty_version",
                entity_id=version.id,
                summary=(
                    f"{context.user.email} validated treaty version — "
                    f"{limit.amount} xs {attachment.amount} {currency}, "
                    f"{len(version.participations)} participants"
                ),
                payload={
                    "attachment": str(attachment.amount),
                    "limit": str(limit.amount),
                    "currency": currency,
                    "participants": len(version.participations),
                },
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        result = await self._versions.get(context.organization.id, version.id)
        assert result is not None
        return result

    # --- helpers ------------------------------------------------

    async def _require_version(
        self, context: AuthenticatedContext, treaty_version_id: UUID
    ) -> TreatyVersion:
        version = await self._versions.get(context.organization.id, treaty_version_id)
        if version is None:
            raise NotFoundError("treaty version not found")
        return version

    def _apply_confirmed(
        self,
        version: TreatyVersion,
        candidate: TreatyTermCandidate,
        value: str | None,
        currency: str | None,
    ) -> None:
        if candidate.key == "participation":
            self._upsert_participation(version, candidate, value)
            return
        if value is None or value == "":
            raise ValidationError(f"a value is required to confirm {candidate.key!r}")

        term = next((t for t in version.terms if t.key == candidate.key), None)
        payload = {"value": value}
        if term is None:
            term = TreatyTerm(
                organization_id=version.organization_id,
                treaty_version_id=version.id,
                key=candidate.key,
                value=payload,
                status=TermStatus.CONFIRMED,
                currency=(currency.upper()[:3] if currency else None),
                derived_from_candidate_id=candidate.id,
            )
            version.terms.append(term)
        else:
            term.value = payload
            term.status = TermStatus.CONFIRMED
            term.currency = currency.upper()[:3] if currency else term.currency
            term.derived_from_candidate_id = candidate.id

        if candidate.key == "currency" and value:
            version.currency = value.upper()[:3]

    def _remove_confirmed(self, version: TreatyVersion, candidate: TreatyTermCandidate) -> None:
        if candidate.key == "participation":
            name = (candidate.normalized_value or {}).get("reinsurer_name")
            version.participations[:] = [
                p for p in version.participations if p.reinsurer.name != name
            ]
            return
        version.terms[:] = [t for t in version.terms if t.key != candidate.key]

    def _upsert_participation(
        self, version: TreatyVersion, candidate: TreatyTermCandidate, value: str | None
    ) -> None:
        data = candidate.normalized_value or {}
        name = str(data.get("reinsurer_name", "")).strip()
        if not name:
            raise ValidationError("participation candidate has no reinsurer name")
        try:
            percent = (
                Decimal(str(value)) if value else Decimal(str(data.get("placed_share_percent", 0)))
            )
        except InvalidOperation as exc:
            raise ValidationError("participation share must be a number") from exc
        share = (percent / Decimal("100")).quantize(Decimal("0.000001"))
        if not (Decimal("0") <= share <= Decimal("1")):
            raise ValidationError("participation share must be between 0 and 100 percent")

        existing = next((p for p in version.participations if p.reinsurer.name == name), None)
        if existing is not None:
            existing.placed_share = share
            return

        from app.db.models.reinsurance import Reinsurer

        reinsurer = Reinsurer(organization_id=version.organization_id, name=name)
        self._session.add(reinsurer)
        version.participations.append(
            TreatyParticipation(
                organization_id=version.organization_id,
                treaty_version_id=version.id,
                reinsurer=reinsurer,
                placed_share=share,
            )
        )


def _candidate_value(candidate: TreatyTermCandidate) -> str | None:
    if candidate.key == "participation":
        return str((candidate.normalized_value or {}).get("placed_share_percent", ""))
    return candidate.raw_value
