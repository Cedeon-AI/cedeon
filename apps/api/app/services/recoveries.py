"""Recovery services.

``RecoveryPreviewService`` is a read-only "what would this treaty recover" probe
(nothing persisted). ``RecoveryCandidateService`` persists the real thing: a
reviewable candidate for one ``(treaty_version, treaty_layer, loss_event)`` triple,
carrying an immutable calculation each time the deterministic engine runs.

No AI anywhere in this module — the recovery figure is deterministic code
(ADR-0010). The Recovery Investigator agent (Phase 7) investigates a candidate; it
never computes the number.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_correlation_id
from app.db.models.extraction import Review
from app.db.models.recoveries import RecoveryAllocation, RecoveryCalculation, RecoveryCandidate
from app.db.models.reinsurance import TreatyLayer, TreatyParticipation, TreatyVersion
from app.domain.audit import ActorType, AuditRecord
from app.domain.money import Money, MoneyError
from app.domain.recoveries import (
    ENGINE_VERSION,
    Participation,
    RecoveryCandidateStatus,
    calculate_recovery,
    recovery_input_hash,
)
from app.domain.recoveries import (
    RecoveryCalculation as RecoveryCalculationResult,
)
from app.domain.reviews import ReviewDecision, ReviewSubjectType
from app.domain.treaties import TreatyVersionStatus
from app.repositories.audit import AuditRepository
from app.repositories.extraction import ReviewRepository
from app.repositories.losses import LossEventRepository, UnderlyingLossRepository
from app.repositories.recoveries import RecoveryCandidateRepository
from app.repositories.reinsurance import TreatyRepository, TreatyVersionRepository
from app.services.auth import AuthenticatedContext
from app.services.errors import ConflictError, NotFoundError, ValidationError

_VALID_VERSION_STATES = (TreatyVersionStatus.VALIDATED, TreatyVersionStatus.ACTIVE)
_REVIEW_DECISIONS = (ReviewDecision.CONFIRM, ReviewDecision.REJECT, ReviewDecision.REQUEST_INFO)


@dataclass(frozen=True, slots=True)
class CandidateContext:
    """Names + the frozen layer figure for one candidate — the programme context the
    recoveries list and the sibling-layers strip need."""

    treaty_name: str | None
    loss_event_name: str | None
    layer_no: int | None
    layer_attachment: Decimal | None
    layer_limit: Decimal | None
    layer_recovery: Decimal | None


class RecoveryPreviewService:
    def __init__(self, session: AsyncSession) -> None:
        self._treaties = TreatyRepository(session)
        self._versions = TreatyVersionRepository(session)

    async def preview(
        self, context: AuthenticatedContext, treaty_id: UUID, *, gross_loss_amount: str
    ) -> RecoveryCalculationResult:
        treaty = await self._treaties.get(context.organization.id, treaty_id)
        if treaty is None or treaty.current_version_id is None:
            raise NotFoundError("treaty not found")
        version = await self._versions.get(context.organization.id, treaty.current_version_id)
        if version is None:
            raise NotFoundError("treaty version not found")
        if version.status not in _VALID_VERSION_STATES:
            raise ConflictError("the treaty must be validated before a recovery can be computed")
        if not version.layers:
            raise ConflictError("the validated treaty version has no layer")

        layer = min(version.layers, key=lambda x: x.layer_no)
        currency = layer.currency

        try:
            gross_loss = Money(Decimal(gross_loss_amount), currency)
        except (InvalidOperation, MoneyError) as exc:
            raise ValidationError(f"gross loss is not a valid amount: {exc}") from exc

        return calculate_recovery(
            gross_loss=gross_loss,
            attachment=Money(Decimal(layer.attachment), currency),
            limit=Money(Decimal(layer.limit), currency),
            participations=_participations(version, layer),
        )


class RecoveryCandidateService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._candidates = RecoveryCandidateRepository(session)
        self._treaties = TreatyRepository(session)
        self._versions = TreatyVersionRepository(session)
        self._events = LossEventRepository(session)
        self._losses = UnderlyingLossRepository(session)
        self._reviews = ReviewRepository(session)
        self._audit = AuditRepository(session)

    # --- reading --------------------------------------------------

    async def list_candidates(
        self, context: AuthenticatedContext, *, status: RecoveryCandidateStatus | None = None
    ) -> list[RecoveryCandidate]:
        return await self._candidates.list(context.organization.id, status=status)

    async def context_for(
        self, context: AuthenticatedContext, candidates: list[RecoveryCandidate]
    ) -> dict[UUID, CandidateContext]:
        """Names + the layer figure for a set of candidates, batched. Used to draw the
        recoveries list and the "sibling layers" strip without N+1 queries."""
        org_id = context.organization.id
        treaty_ids = {c.treaty_id for c in candidates}
        version_ids = {c.treaty_version_id for c in candidates}
        event_ids = {c.loss_event_id for c in candidates}
        treaties = {tid: await self._treaties.get(org_id, tid) for tid in treaty_ids}
        versions = {vid: await self._versions.get(org_id, vid) for vid in version_ids}
        events = {eid: await self._events.get(org_id, eid) for eid in event_ids}

        out: dict[UUID, CandidateContext] = {}
        for c in candidates:
            version = versions.get(c.treaty_version_id)
            layer = (
                next((x for x in version.layers if x.id == c.treaty_layer_id), None)
                if version is not None
                else None
            )
            calc = self.current_calculation(c)
            treaty = treaties.get(c.treaty_id)
            event = events.get(c.loss_event_id)
            out[c.id] = CandidateContext(
                treaty_name=treaty.name if treaty is not None else None,
                loss_event_name=event.name if event is not None else None,
                layer_no=layer.layer_no if layer is not None else None,
                layer_attachment=Decimal(layer.attachment) if layer is not None else None,
                layer_limit=Decimal(layer.limit) if layer is not None else None,
                layer_recovery=Decimal(calc.layer_recovery) if calc is not None else None,
            )
        return out

    async def get_candidate(
        self, context: AuthenticatedContext, candidate_id: UUID
    ) -> RecoveryCandidate:
        candidate = await self._candidates.get(context.organization.id, candidate_id)
        if candidate is None:
            raise NotFoundError("recovery candidate not found")
        return candidate

    async def candidate_reviews(
        self, context: AuthenticatedContext, candidate_id: UUID
    ) -> list[Review]:
        return await self._reviews.list_for_subject(context.organization.id, candidate_id)

    def current_calculation(self, candidate: RecoveryCandidate) -> RecoveryCalculation | None:
        return next(
            (c for c in candidate.calculations if c.id == candidate.current_calculation_id), None
        )

    # --- create --------------------------------------------------

    async def create(
        self, context: AuthenticatedContext, *, treaty_id: UUID, loss_event_id: UUID
    ) -> list[RecoveryCandidate]:
        """Open a recovery for every layer of the treaty that responds to the
        event (gross above the layer's attachment). If none respond, open the
        bottom layer so the analyst can see the near miss. Existing candidates
        are returned as-is (idempotent per ``(version, layer, event)``)."""
        org_id = context.organization.id
        version, layers = await self._executable_layers(context, treaty_id)
        currency = layers[0].currency
        event_id, gross_loss, mismatch = await self._gross_for_event(
            org_id, loss_event_id, currency
        )

        responding = [x for x in layers if gross_loss.amount > Decimal(x.attachment)]
        targets = responding or [layers[0]]

        created_ids: list[UUID] = []
        for layer in targets:
            existing = await self._candidates.get_by_inputs(
                org_id,
                treaty_version_id=version.id,
                treaty_layer_id=layer.id,
                loss_event_id=event_id,
            )
            if existing is not None:
                created_ids.append(existing.id)
                continue

            candidate = RecoveryCandidate(
                organization_id=org_id,
                treaty_id=treaty_id,
                treaty_version_id=version.id,
                treaty_layer_id=layer.id,
                loss_event_id=event_id,
                status=RecoveryCandidateStatus.NEEDS_REVIEW,
                currency=layer.currency,
                gross_event_incurred=gross_loss.amount,
                currency_mismatch=mismatch,
                created_by=context.user.id,
            )
            self._candidates.add(candidate)
            await self._session.flush()
            calc = await self._run_and_store(candidate, version, layer, gross_loss)
            candidate.current_calculation_id = calc.id
            created_ids.append(candidate.id)

            self._audit.record(
                AuditRecord(
                    organization_id=org_id,
                    actor_type=ActorType.USER,
                    actor_id=context.user.id,
                    action="recovery_candidate.created",
                    entity_type="recovery_candidate",
                    entity_id=candidate.id,
                    summary=(
                        f"{context.user.email} created a recovery candidate — layer "
                        f"{layer.layer_no} ({layer.limit} xs {layer.attachment}), "
                        f"{calc.layer_recovery} {calc.currency} recovery"
                    ),
                    payload={
                        "treaty_version_id": str(version.id),
                        "treaty_layer_id": str(layer.id),
                        "layer_no": layer.layer_no,
                        "loss_event_id": str(event_id),
                        "layer_recovery": str(calc.layer_recovery),
                        "engine_version": calc.engine_version,
                        "currency_mismatch": mismatch,
                    },
                    correlation_id=get_correlation_id(),
                )
            )
        await self._session.commit()
        return [
            c for cid in created_ids if (c := await self._candidates.get(org_id, cid)) is not None
        ]

    # --- recalculate ------------------------------------------

    async def recalculate(
        self, context: AuthenticatedContext, candidate_id: UUID
    ) -> RecoveryCandidate:
        org_id = context.organization.id
        candidate = await self.get_candidate(context, candidate_id)

        prior_amount = getattr(self.current_calculation(candidate), "layer_recovery", None)
        calc, changed = await self._recompute_core(org_id, candidate)
        if not changed or calc is None:
            return candidate

        reverted = candidate.status is RecoveryCandidateStatus.CONFIRMED
        if reverted:
            candidate.status = RecoveryCandidateStatus.NEEDS_REVIEW
            candidate.reviewed_at = None
            candidate.reviewed_by = None
        # a human asked for this recompute — it is not silent drift
        candidate.drifted_at = None
        candidate.pre_drift_recovery = None

        self._audit.record(
            AuditRecord(
                organization_id=org_id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="recovery_candidate.recalculated",
                entity_type="recovery_candidate",
                entity_id=candidate.id,
                summary=(
                    f"{context.user.email} recalculated — "
                    f"{Decimal(prior_amount) if prior_amount is not None else 0} → "
                    f"{calc.layer_recovery} {calc.currency}"
                    + (" (reverted to needs review)" if reverted else "")
                ),
                payload={
                    "layer_recovery": str(calc.layer_recovery),
                    "reverted_to_needs_review": reverted,
                },
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        return await self.get_candidate(context, candidate.id)

    async def recalculate_for_events(
        self, context: AuthenticatedContext, event_ids: set[UUID]
    ) -> list[dict[str, str]]:
        """Auto-recompute every non-rejected recovery on the given loss events.
        A figure that moves without a human in the loop is *drift* — flagged on the
        candidate and surfaced on the worklist until the next review. No commit —
        the caller (the loss-import commit) owns the transaction."""
        if not event_ids:
            return []
        org_id = context.organization.id
        drifted: list[dict[str, str]] = []
        for candidate in await self._candidates.list(org_id):
            if (
                candidate.loss_event_id not in event_ids
                or candidate.status is RecoveryCandidateStatus.REJECTED
            ):
                continue
            prior = self.current_calculation(candidate)
            prior_amount = Decimal(prior.layer_recovery) if prior is not None else None
            calc, changed = await self._recompute_core(org_id, candidate)
            if not changed or calc is None:
                continue

            candidate.drifted_at = dt.datetime.now(dt.UTC)
            candidate.pre_drift_recovery = prior_amount
            if candidate.status in (
                RecoveryCandidateStatus.CONFIRMED,
                RecoveryCandidateStatus.NOTICE_DRAFTED,
            ):
                candidate.status = RecoveryCandidateStatus.NEEDS_REVIEW
                candidate.reviewed_at = None
                candidate.reviewed_by = None
            self._audit.record(
                AuditRecord(
                    organization_id=org_id,
                    actor_type=ActorType.SYSTEM,
                    actor_id=None,
                    action="recovery_candidate.drifted",
                    entity_type="recovery_candidate",
                    entity_id=candidate.id,
                    summary=(
                        f"claims developed — recovery moved "
                        f"{prior_amount if prior_amount is not None else 0} → "
                        f"{calc.layer_recovery} {calc.currency}"
                    ),
                    payload={
                        "from": str(prior_amount) if prior_amount is not None else None,
                        "to": str(calc.layer_recovery),
                    },
                    correlation_id=get_correlation_id(),
                )
            )
            drifted.append(
                {
                    "candidate_id": str(candidate.id),
                    "from": str(prior_amount) if prior_amount is not None else "0",
                    "to": str(calc.layer_recovery),
                }
            )
        return drifted

    async def _recompute_core(
        self, org_id: UUID, candidate: RecoveryCandidate
    ) -> tuple[RecoveryCalculation | None, bool]:
        """Re-run the engine for one candidate. Writes a new immutable calculation
        (and moves ``current_calculation_id``) only when ``input_hash`` changed.
        Returns ``(calc, changed)``."""
        version = await self._versions.get(org_id, candidate.treaty_version_id)
        if version is None:
            raise NotFoundError("the candidate's treaty version no longer exists")
        layer = next((x for x in version.layers if x.id == candidate.treaty_layer_id), None)
        if layer is None:
            raise NotFoundError("the candidate's treaty layer no longer exists")

        _, gross_loss, mismatch = await self._gross_for_event(
            org_id, candidate.loss_event_id, layer.currency
        )
        new_hash = self._input_hash(candidate, layer, version, gross_loss)
        current = self.current_calculation(candidate)
        if current is not None and current.input_hash == new_hash:
            return current, False

        calc = await self._run_and_store(candidate, version, layer, gross_loss)
        candidate.current_calculation_id = calc.id
        candidate.gross_event_incurred = gross_loss.amount
        candidate.currency_mismatch = mismatch
        return calc, True

    # --- review ---------------------------------------------

    async def review(
        self,
        context: AuthenticatedContext,
        candidate_id: UUID,
        *,
        decision: ReviewDecision,
        reason: str | None = None,
    ) -> RecoveryCandidate:
        if decision not in _REVIEW_DECISIONS:
            raise ValidationError(
                f"a recovery candidate can be confirmed, rejected, or sent back for info "
                f"— not {decision.value!r}"
            )
        candidate = await self.get_candidate(context, candidate_id)
        if candidate.status in (
            RecoveryCandidateStatus.CONFIRMED,
            RecoveryCandidateStatus.NOTICE_DRAFTED,
        ):
            raise ConflictError(f"this candidate is already {candidate.status.value}")
        if decision is ReviewDecision.CONFIRM and self.current_calculation(candidate) is None:
            raise ConflictError("the candidate has no calculation to confirm")

        status_before = candidate.status
        if decision is ReviewDecision.CONFIRM:
            candidate.status = RecoveryCandidateStatus.CONFIRMED
        elif decision is ReviewDecision.REJECT:
            candidate.status = RecoveryCandidateStatus.REJECTED
        else:  # REQUEST_INFO — stays open for follow-up
            candidate.status = RecoveryCandidateStatus.NEEDS_REVIEW
        candidate.reviewed_at = dt.datetime.now(dt.UTC)
        candidate.reviewed_by = context.user.id
        # a human has looked at the current number — drift is acknowledged
        candidate.drifted_at = None
        candidate.pre_drift_recovery = None

        self._reviews.add(
            Review(
                organization_id=context.organization.id,
                subject_type=ReviewSubjectType.RECOVERY_CANDIDATE,
                subject_id=candidate.id,
                reviewer_id=context.user.id,
                decision=decision,
                value_before={"status": status_before.value},
                value_after={"status": candidate.status.value},
                reason=reason,
            )
        )
        self._audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="recovery_candidate.reviewed",
                entity_type="recovery_candidate",
                entity_id=candidate.id,
                summary=f"{context.user.email} {decision.value} recovery candidate",
                payload={"decision": decision.value, "status": candidate.status.value},
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        return await self.get_candidate(context, candidate.id)

    # --- helpers ------------------------------------------

    async def _executable_layers(
        self, context: AuthenticatedContext, treaty_id: UUID
    ) -> tuple[TreatyVersion, list[TreatyLayer]]:
        treaty = await self._treaties.get(context.organization.id, treaty_id)
        if treaty is None or treaty.current_version_id is None:
            raise NotFoundError("treaty not found")
        version = await self._versions.get(context.organization.id, treaty.current_version_id)
        if version is None:
            raise NotFoundError("treaty version not found")
        if version.status not in _VALID_VERSION_STATES:
            raise ConflictError("the treaty must be validated before a recovery can be computed")
        if not version.layers:
            raise ConflictError("the validated treaty version has no layer")
        return version, sorted(version.layers, key=lambda x: x.layer_no)

    async def _gross_for_event(
        self, organization_id: UUID, loss_event_id: UUID, currency: str
    ) -> tuple[UUID, Money, bool]:
        event = await self._events.get(organization_id, loss_event_id)
        if event is None:
            raise NotFoundError("loss event not found")
        losses = await self._losses.for_event(organization_id, loss_event_id)
        if not losses:
            raise ConflictError("this loss event has no committed underlying losses")

        in_currency = [x for x in losses if x.currency == currency]
        mismatch = any(x.currency != currency for x in losses)
        gross = sum((Decimal(x.gross_incurred) for x in in_currency), Decimal("0"))
        return event.id, Money.round(gross, currency), mismatch

    async def _run_and_store(
        self,
        candidate: RecoveryCandidate,
        version: TreatyVersion,
        layer: TreatyLayer,
        gross_loss: Money,
    ) -> RecoveryCalculation:
        currency = layer.currency
        participations = _participations(version, layer)
        result = calculate_recovery(
            gross_loss=gross_loss,
            attachment=Money(Decimal(layer.attachment), currency),
            limit=Money(Decimal(layer.limit), currency),
            participations=participations,
        )
        calc = RecoveryCalculation(
            organization_id=candidate.organization_id,
            engine_version=result.engine_version,
            treaty_version_id=version.id,
            treaty_layer_id=layer.id,
            currency=currency,
            inputs={
                "gross_loss": str(gross_loss.amount),
                "attachment": str(Decimal(layer.attachment)),
                "limit": str(Decimal(layer.limit)),
                "participations": [
                    {"reinsurer_id": p.key, "reinsurer_name": p.label, "share": str(p.share)}
                    for p in participations
                ],
            },
            gross_loss=result.xol.gross_loss.amount,
            attachment=result.xol.attachment.amount,
            amount_above_attachment=result.xol.amount_above_attachment.amount,
            layer_limit=result.xol.limit.amount,
            layer_recovery=result.xol.layer_recovery.amount,
            cedent_retention=result.cedent_retention.amount,
            total_ceded=result.total_ceded.amount,
            trace=[
                {"label": s.label, "expression": s.expression, "result": s.result}
                for s in result.xol.trace
            ],
            input_hash=self._input_hash(candidate, layer, version, gross_loss),
            recovery_candidate_id=candidate.id,
        )
        self._session.add(calc)
        await self._session.flush()
        for allocation in result.allocations:
            self._session.add(
                RecoveryAllocation(
                    organization_id=candidate.organization_id,
                    recovery_calculation_id=calc.id,
                    reinsurer_id=UUID(allocation.key),
                    participation_share=allocation.share,
                    allocated_recovery=allocation.amount.amount,
                )
            )
        await self._session.flush()
        return calc

    @staticmethod
    def _input_hash(
        candidate: RecoveryCandidate,
        layer: TreatyLayer,
        version: TreatyVersion,
        gross_loss: Money,
    ) -> str:
        return recovery_input_hash(
            engine_version=ENGINE_VERSION,
            treaty_version_id=str(version.id),
            treaty_layer_id=str(layer.id),
            loss_event_id=str(candidate.loss_event_id),
            currency=layer.currency,
            gross_loss=gross_loss.amount,
            attachment=Decimal(layer.attachment),
            limit=Decimal(layer.limit),
            participations=[
                (str(p.reinsurer_id), Decimal(p.placed_share))
                for p in _participation_rows(version, layer)
            ],
        )


def _participation_rows(
    version: TreatyVersion, layer: TreatyLayer | None
) -> list[TreatyParticipation]:
    """The panel that applies to ``layer``: its own rows if it has any, otherwise the
    programme-wide panel (``treaty_layer_id IS NULL``)."""
    if layer is not None:
        own = [p for p in version.participations if p.treaty_layer_id == layer.id]
        if own:
            return own
    return [p for p in version.participations if p.treaty_layer_id is None]


def _participations(
    version: TreatyVersion, layer: TreatyLayer | None = None
) -> list[Participation]:
    return [
        Participation(
            key=str(p.reinsurer_id),
            label=p.reinsurer.name,
            share=Decimal(p.placed_share),
        )
        for p in _participation_rows(version, layer)
    ]
