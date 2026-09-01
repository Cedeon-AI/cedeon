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
    Reinsurer,
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


@dataclass(slots=True)
class TermDiffEntry:
    """One term, as it stands on the new (endorsement) version vs what was carried
    forward from the superseded version."""

    key: str
    carried_value: str | None  # the confirmed value copied from the prior version
    extracted_value: str | None  # what re-extraction found in the endorsement document
    extracted_candidate_id: UUID | None
    change: str  # unchanged | changed | new | not_extracted


_MONEY_KEYS = frozenset({"attachment", "limit"})


def _norm_term_value(key: str, value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if key in _MONEY_KEYS:
        cleaned = text.replace(",", "").replace("$", "").strip()
        for token in cleaned.replace("USD", "").split():
            try:
                return str(Decimal(token))
            except InvalidOperation:
                continue
        try:
            return str(Decimal(cleaned))
        except InvalidOperation:
            return text.lower()
    return text.lower()


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

    async def term_diff(
        self, context: AuthenticatedContext, treaty_version_id: UUID
    ) -> list[TermDiffEntry]:
        """What changed between the carried-forward terms and what re-extraction found
        in the endorsement document. Empty when this version was not re-extracted."""
        version = await self._require_version(context, treaty_version_id)
        candidates = await self._candidates.list_for_version(
            context.organization.id, treaty_version_id
        )
        carried = {
            t.key: str(t.value.get("value", ""))
            for t in version.terms
            if t.status is TermStatus.CONFIRMED and t.key != "participation"
        }
        # newest candidate per key
        latest: dict[str, TreatyTermCandidate] = {}
        for c in candidates:
            if c.key == "participation":
                continue
            latest.setdefault(c.key, c)

        entries: list[TermDiffEntry] = []
        for key in sorted(carried.keys() | latest.keys()):
            carried_value = carried.get(key)
            candidate = latest.get(key)
            extracted_value = _candidate_value(candidate) if candidate is not None else None
            if carried_value is not None and candidate is None:
                change = "not_extracted"
            elif carried_value is None:
                change = "new"
            elif _norm_term_value(key, carried_value) == _norm_term_value(key, extracted_value):
                change = "unchanged"
            else:
                change = "changed"
            entries.append(
                TermDiffEntry(
                    key=key,
                    carried_value=carried_value,
                    extracted_value=extracted_value,
                    extracted_candidate_id=candidate.id if candidate is not None else None,
                    change=change,
                )
            )
        return entries

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

    # --- layers ---------------------------------------------------

    async def set_layers(
        self,
        context: AuthenticatedContext,
        treaty_version_id: UUID,
        specs: list[tuple[Decimal, Decimal]],
        *,
        currency: str | None = None,
    ) -> TreatyVersion:
        """Replace the whole stack of executable XOL layers on a non-frozen
        version. Layers are sorted by attachment and numbered from the bottom."""
        version = await self._require_version(context, treaty_version_id)
        if version.status.is_frozen:
            raise ConflictError("this treaty version is already validated — its layers are frozen")
        resolved = (currency or "").upper()[:3] or self._version_currency(version)
        if not resolved:
            raise ValidationError("a currency is required to set the layer stack")
        currency = resolved

        ordered = sorted(specs, key=lambda s: s[0])
        for i, (attachment, limit) in enumerate(ordered, start=1):
            if attachment < 0:
                raise ValidationError(f"layer {i} attachment must be non-negative")
            if limit <= 0:
                raise ValidationError(f"layer {i} limit must be greater than zero")

        # Per-layer panels are keyed to layer ids that are about to disappear.
        for p in list(version.participations):
            if p.treaty_layer_id is not None:
                await self._session.delete(p)
        for existing in list(version.layers):
            await self._session.delete(existing)
        version.layers.clear()
        # flush the deletes before re-inserting the same (version_id, layer_no)
        await self._session.flush()
        for i, (attachment, limit) in enumerate(ordered, start=1):
            version.layers.append(
                TreatyLayer(
                    organization_id=context.organization.id,
                    treaty_version_id=version.id,
                    layer_no=i,
                    attachment=attachment,
                    limit=limit,
                    currency=currency,
                )
            )
        version.currency = currency
        self._audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="treaty_version.layers_set",
                entity_type="treaty_version",
                entity_id=version.id,
                summary=(
                    f"{context.user.email} set the {len(ordered)}-layer stack: "
                    + " / ".join(f"{lim} xs {att}" for att, lim in ordered)
                ),
                payload={"layers": [{"attachment": str(a), "limit": str(x)} for a, x in ordered]},
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        result = await self._versions.get(context.organization.id, version.id)
        assert result is not None
        return result

    async def set_layer_participations(
        self,
        context: AuthenticatedContext,
        treaty_version_id: UUID,
        layer_no: int,
        panel: list[tuple[str, Decimal]],
    ) -> TreatyVersion:
        """Give one layer its own reinsurer panel, overriding the programme panel for
        that layer only. ``panel`` is ``(reinsurer name, placed share percent)`` pairs;
        an empty list clears the override and the layer falls back to the programme
        panel. Editable until the version is frozen."""
        version = await self._require_version(context, treaty_version_id)
        if version.status.is_frozen:
            raise ConflictError("this treaty version is already validated — its panel is frozen")
        layer = next((x for x in version.layers if x.layer_no == layer_no), None)
        if layer is None:
            raise NotFoundError(f"treaty version has no layer {layer_no}")

        resolved: list[tuple[str, Decimal]] = []
        for raw_name, percent in panel:
            name = raw_name.strip()
            if not name:
                raise ValidationError("a reinsurer name is required")
            share = (percent / Decimal("100")).quantize(Decimal("0.000001"))
            if not (Decimal("0") <= share <= Decimal("1")):
                raise ValidationError(f"{name}: share must be between 0 and 100 percent")
            resolved.append((name, share))
        if len({n.lower() for n, _ in resolved}) != len(resolved):
            raise ValidationError("a reinsurer appears twice in the panel")

        for existing in [p for p in version.participations if p.treaty_layer_id == layer.id]:
            version.participations.remove(existing)
            await self._session.delete(existing)
        await self._session.flush()

        for name, share in resolved:
            reinsurer = await self._reinsurers.get_by_name(context.organization.id, name)
            if reinsurer is None:
                reinsurer = Reinsurer(organization_id=context.organization.id, name=name)
                self._reinsurers.add(reinsurer)
            version.participations.append(
                TreatyParticipation(
                    organization_id=context.organization.id,
                    treaty_version_id=version.id,
                    treaty_layer_id=layer.id,
                    reinsurer=reinsurer,
                    placed_share=share,
                )
            )

        self._audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="treaty_version.layer_panel_set",
                entity_type="treaty_version",
                entity_id=version.id,
                summary=(
                    f"{context.user.email} "
                    + (
                        f"set a {len(resolved)}-reinsurer panel on layer {layer_no}"
                        if resolved
                        else f"cleared the layer {layer_no} panel (back to the programme panel)"
                    )
                ),
                payload={
                    "layer_no": layer_no,
                    "panel": [{"reinsurer": n, "placed_share": str(s)} for n, s in resolved],
                },
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        result = await self._versions.get(context.organization.id, version.id)
        assert result is not None
        return result

    async def set_layer_reinstatement_terms(
        self,
        context: AuthenticatedContext,
        treaty_version_id: UUID,
        layer_no: int,
        *,
        deposit_premium: Decimal | None,
        rates: list[Decimal],
        basis: str,
    ) -> TreatyVersion:
        """Set the reinstatement premium terms on one layer — deposit premium, the
        rate per reinstatement, and whether it is flat or pro-rata as to time. Human
        facts, never AI. Editable until the version is frozen. Passing no rates clears
        the terms."""
        version = await self._require_version(context, treaty_version_id)
        if version.status.is_frozen:
            raise ConflictError("this treaty version is already validated — its terms are frozen")
        layer = next((x for x in version.layers if x.layer_no == layer_no), None)
        if layer is None:
            raise NotFoundError(f"treaty version has no layer {layer_no}")
        if basis not in ("flat", "pro_rata_time"):
            raise ValidationError("reinstatement basis must be 'flat' or 'pro_rata_time'")
        for rate in rates:
            if rate < 0:
                raise ValidationError("a reinstatement rate must not be negative")
        if deposit_premium is not None and deposit_premium < 0:
            raise ValidationError("the deposit premium must not be negative")
        if rates and deposit_premium is None:
            raise ValidationError("a deposit premium is required to price reinstatements")

        layer.reinstatement_rates = [str(r) for r in rates] if rates else None
        layer.reinstatement_basis = basis if rates else None
        layer.deposit_premium = deposit_premium if rates else None
        layer.reinstatements = len(rates) if rates else layer.reinstatements

        self._audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="treaty_version.reinstatement_terms_set",
                entity_type="treaty_version",
                entity_id=version.id,
                summary=(
                    f"{context.user.email} "
                    + (
                        f"set {len(rates)} reinstatement(s) on layer {layer_no} "
                        f"({basis}, deposit {deposit_premium})"
                        if rates
                        else f"cleared the reinstatement terms on layer {layer_no}"
                    )
                ),
                payload={
                    "layer_no": layer_no,
                    "rates": [str(r) for r in rates],
                    "basis": basis,
                    "deposit_premium": (
                        str(deposit_premium) if deposit_premium is not None else None
                    ),
                },
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        result = await self._versions.get(context.organization.id, version.id)
        assert result is not None
        return result

    def _version_currency(self, version: TreatyVersion) -> str | None:
        if version.currency:
            return version.currency.upper()[:3]
        term = next((t for t in version.terms if t.key == "currency"), None)
        if term is not None:
            raw = str(term.value.get("value") or "").strip()
            if raw:
                return raw.upper()[:3]
        return None

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
        currency = self._version_currency(version)
        if not currency:
            raise ValidationError("confirm the treaty currency before validating")

        # Layers: use the stack the analyst set, else build one from the terms.
        if not version.layers:
            missing = [k for k in ("attachment", "limit") if k not in confirmed]
            if missing:
                raise ValidationError(
                    f"confirm {', '.join(missing)} (or set the layer stack) before validating",
                    detail={"missing": missing},
                )
            try:
                attachment = Money(Decimal(str(confirmed["attachment"].value["value"])), currency)
                limit = Money(Decimal(str(confirmed["limit"].value["value"])), currency)
            except (KeyError, TypeError, InvalidOperation, MoneyError) as exc:
                raise ValidationError(
                    f"confirmed attachment/limit is not valid money: {exc}"
                ) from exc
            attachment.require_non_negative("attachment")
            if not limit.is_positive:
                raise ValidationError("limit must be greater than zero")
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

        for layer in version.layers:
            if layer.currency != currency:
                raise ValidationError(
                    f"layer {layer.layer_no} is {layer.currency}, but the treaty is {currency}"
                )

        if not version.participations:
            raise ValidationError("confirm at least one reinsurer participation before validating")
        # The programme panel and each layer's own panel are checked separately.
        programme = [p for p in version.participations if p.treaty_layer_id is None]
        for layer in version.layers:
            own = [p for p in version.participations if p.treaty_layer_id == layer.id]
            panel = own or programme
            if not panel:
                raise ValidationError(
                    f"layer {layer.layer_no} has no reinsurer panel — set one, "
                    "or confirm a programme-wide panel"
                )
        panels: list[tuple[str, list[TreatyParticipation]]] = [("programme", programme)]
        for x in version.layers:
            panels.append(
                (
                    f"layer {x.layer_no}",
                    [p for p in version.participations if p.treaty_layer_id == x.id],
                )
            )
        for label, panel in panels:
            share_sum = sum((p.placed_share for p in panel), Decimal("0"))
            if share_sum > Decimal("1") + _SHARE_EPSILON:
                raise ValidationError(
                    f"{label} placed shares sum to {share_sum} (> 100%)",
                    detail={"panel": label, "share_sum": str(share_sum)},
                )

        version.currency = currency
        version.status = TreatyVersionStatus.VALIDATED
        version.validated_at = dt.datetime.now(dt.UTC)
        version.validated_by = context.user.id

        stack = sorted(version.layers, key=lambda x: x.layer_no)
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
                    + " / ".join(f"{x.limit} xs {x.attachment}" for x in stack)
                    + f" {currency}, {len(version.participations)} participants"
                ),
                payload={
                    "layers": [
                        {"attachment": str(x.attachment), "limit": str(x.limit)} for x in stack
                    ],
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
                p
                for p in version.participations
                if p.treaty_layer_id is not None or p.reinsurer.name != name
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

        existing = next(
            (
                p
                for p in version.participations
                if p.treaty_layer_id is None and p.reinsurer.name == name
            ),
            None,
        )
        if existing is not None:
            existing.placed_share = share
            return

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
