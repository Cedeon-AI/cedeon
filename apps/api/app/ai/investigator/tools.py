"""Read-only, org-scoped tools for the Recovery Investigator.

Hard rules (docs/AI_ARCHITECTURE.md §2b):
- No raw DB access from the agent — only these typed tools.
- No write tools. No side effects. Nothing that sends, creates, or updates.
- Every tool enforces ``organization_id`` from ``RunContext`` deps.
The deterministic recovery numbers are returned here as facts to explain, never
to recompute.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.documents import DocumentChunk
from app.db.models.recoveries import RecoveryCandidate
from app.repositories.documents import DocumentRepository
from app.repositories.losses import LossEventRepository, UnderlyingLossRepository
from app.repositories.recoveries import RecoveryCandidateRepository
from app.repositories.reinsurance import TreatyVersionRepository

_MAX_LOSSES = 200
_MAX_PASSAGES = 8


@dataclass(slots=True)
class InvestigatorDeps:
    session: AsyncSession
    organization_id: UUID
    candidate_id: UUID


# --- typed views the agent sees -------------------------------------


class CalculationView(BaseModel):
    engine_version: str
    currency: str
    gross_event_incurred: str
    attachment: str
    limit: str
    amount_above_attachment: str
    layer_recovery: str
    cedent_retention: str
    trace: list[str]
    note: str = (
        "These figures are computed by Cedeon's deterministic engine and are authoritative. "
        "Explain or question them; do not recompute them."
    )


class TermView(BaseModel):
    key: str
    value: str
    currency: str | None


class LayerView(BaseModel):
    attachment: str
    limit: str
    currency: str
    reinstatements: int | None


class ValidatedTermsView(BaseModel):
    layer: LayerView | None
    terms: list[TermView]


class ParticipantView(BaseModel):
    reinsurer_name: str
    placed_share_percent: str


class CurrencyTotal(BaseModel):
    currency: str
    claim_count: int
    gross_incurred: str


class LossEventView(BaseModel):
    name: str
    event_identifier: str | None
    catastrophe_code: str | None
    date_of_loss_from: str | None
    date_of_loss_to: str | None
    totals: list[CurrencyTotal]


class UnderlyingLossView(BaseModel):
    claim_id: str
    date_of_loss: str
    cause_of_loss: str | None
    location: str | None
    currency: str
    gross_incurred: str


class Passage(BaseModel):
    page_from: int
    page_to: int
    section_path: str
    heading: str | None
    text: str


class ToolError(BaseModel):
    error: str


async def _candidate(deps: InvestigatorDeps) -> RecoveryCandidate | None:
    return await RecoveryCandidateRepository(deps.session).get(
        deps.organization_id, deps.candidate_id
    )


async def get_recovery_calculation(deps: InvestigatorDeps) -> CalculationView | ToolError:
    candidate = await _candidate(deps)
    if candidate is None:
        return ToolError(error="recovery candidate not found")
    calc = next(
        (c for c in candidate.calculations if c.id == candidate.current_calculation_id), None
    )
    if calc is None:
        return ToolError(error="the candidate has no calculation")
    return CalculationView(
        engine_version=calc.engine_version,
        currency=calc.currency,
        gross_event_incurred=str(candidate.gross_event_incurred),
        attachment=str(calc.attachment),
        limit=str(calc.layer_limit),
        amount_above_attachment=str(calc.amount_above_attachment),
        layer_recovery=str(calc.layer_recovery),
        cedent_retention=str(calc.cedent_retention),
        trace=[f"{s['label']}: {s['expression']} = {s['result']}" for s in calc.trace],
    )


async def get_validated_terms(deps: InvestigatorDeps) -> ValidatedTermsView | ToolError:
    candidate = await _candidate(deps)
    if candidate is None:
        return ToolError(error="recovery candidate not found")
    version = await TreatyVersionRepository(deps.session).get(
        deps.organization_id, candidate.treaty_version_id
    )
    if version is None:
        return ToolError(error="treaty version not found")
    layer = next((x for x in version.layers if x.id == candidate.treaty_layer_id), None)
    return ValidatedTermsView(
        layer=(
            LayerView(
                attachment=str(layer.attachment),
                limit=str(layer.limit),
                currency=layer.currency,
                reinstatements=layer.reinstatements,
            )
            if layer is not None
            else None
        ),
        terms=[
            TermView(
                key=t.key,
                value=str(t.value.get("value", t.value)),
                currency=t.currency,
            )
            for t in version.terms
        ],
    )


async def get_participants(deps: InvestigatorDeps) -> list[ParticipantView] | ToolError:
    candidate = await _candidate(deps)
    if candidate is None:
        return ToolError(error="recovery candidate not found")
    version = await TreatyVersionRepository(deps.session).get(
        deps.organization_id, candidate.treaty_version_id
    )
    if version is None:
        return ToolError(error="treaty version not found")
    # The panel that applies to this candidate's layer: its own rows, else the programme panel.
    own = [p for p in version.participations if p.treaty_layer_id == candidate.treaty_layer_id]
    panel = own or [p for p in version.participations if p.treaty_layer_id is None]
    return [
        ParticipantView(
            reinsurer_name=p.reinsurer.name,
            placed_share_percent=str((Decimal(p.placed_share) * 100).normalize()),
        )
        for p in panel
    ]


async def get_loss_event(deps: InvestigatorDeps) -> LossEventView | ToolError:
    candidate = await _candidate(deps)
    if candidate is None:
        return ToolError(error="recovery candidate not found")
    events = LossEventRepository(deps.session)
    event = await events.get(deps.organization_id, candidate.loss_event_id)
    if event is None:
        return ToolError(error="loss event not found")
    aggregates = await events.aggregates(deps.organization_id)
    totals = aggregates.get(event.id, {})
    return LossEventView(
        name=event.name,
        event_identifier=event.event_identifier,
        catastrophe_code=event.catastrophe_code,
        date_of_loss_from=event.date_of_loss_from.isoformat() if event.date_of_loss_from else None,
        date_of_loss_to=event.date_of_loss_to.isoformat() if event.date_of_loss_to else None,
        totals=[
            CurrencyTotal(currency=ccy, claim_count=count, gross_incurred=str(total))
            for ccy, (count, total) in sorted(totals.items())
        ],
    )


async def list_underlying_losses(
    deps: InvestigatorDeps, limit: int = 50
) -> list[UnderlyingLossView] | ToolError:
    candidate = await _candidate(deps)
    if candidate is None:
        return ToolError(error="recovery candidate not found")
    losses = await UnderlyingLossRepository(deps.session).for_event(
        deps.organization_id, candidate.loss_event_id
    )
    capped = losses[: max(1, min(limit, _MAX_LOSSES))]
    return [
        UnderlyingLossView(
            claim_id=x.claim_id,
            date_of_loss=x.date_of_loss.isoformat(),
            cause_of_loss=x.cause_of_loss,
            location=x.location,
            currency=x.currency,
            gross_incurred=str(x.gross_incurred),
        )
        for x in capped
    ]


async def search_treaty(
    deps: InvestigatorDeps, query: str, k: int = 5
) -> list[Passage] | ToolError:
    candidate = await _candidate(deps)
    if candidate is None:
        return ToolError(error="recovery candidate not found")
    version = await TreatyVersionRepository(deps.session).get(
        deps.organization_id, candidate.treaty_version_id
    )
    if version is None or version.source_document_id is None:
        return ToolError(error="the treaty version has no source document to search")

    documents = DocumentRepository(deps.session)
    parse = await documents.current_parse(deps.organization_id, version.source_document_id)
    if parse is None:
        return ToolError(error="the treaty document has not been parsed")

    k = max(1, min(k, _MAX_PASSAGES))
    ts_query = func.plainto_tsquery("english", query)
    ts_vector = func.to_tsvector("english", DocumentChunk.text)
    stmt = (
        select(DocumentChunk)
        .where(
            DocumentChunk.organization_id == deps.organization_id,
            DocumentChunk.parse_id == parse.id,
        )
        .order_by(func.ts_rank(ts_vector, ts_query).desc(), DocumentChunk.ordinal)
        .limit(k)
    )
    rows = list((await deps.session.execute(stmt)).scalars().all())
    if not rows:  # query had no lexical hits — fall back to the opening clauses
        rows = await documents.list_chunks(deps.organization_id, parse.id)
        rows = rows[:k]
    return [
        Passage(
            page_from=c.page_from,
            page_to=c.page_to,
            section_path=c.section_path,
            heading=c.heading,
            text=c.text,
        )
        for c in rows
    ]
