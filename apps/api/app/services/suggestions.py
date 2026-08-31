"""Which of the org's validated treaties look like they respond to a loss event,
that nobody has opened a recovery for yet.

A deterministic screen (``app.domain.recoveries.suggestions``) over validated
treaty layers. Cedeon *proposes*; the analyst promotes a suggestion to a real
``RecoveryCandidate`` through the normal endpoint. No AI, read-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.losses import LossEvent
from app.db.models.reinsurance import TreatyLayer, TreatyVersion
from app.domain.recoveries.suggestions import (
    EventFacts,
    LayerWindow,
    Suggestion,
    evaluate_suggestion,
)
from app.domain.treaties import TreatyVersionStatus
from app.repositories.losses import LossEventRepository, UnderlyingLossRepository
from app.repositories.recoveries import RecoveryCandidateRepository
from app.repositories.reinsurance import TreatyRepository, TreatyVersionRepository
from app.services.auth import AuthenticatedContext

_EXECUTABLE = (TreatyVersionStatus.VALIDATED, TreatyVersionStatus.ACTIVE)


@dataclass(slots=True)
class SuggestedRecovery:
    treaty_id: UUID
    treaty_name: str
    treaty_version_id: UUID
    treaty_layer_id: UUID
    loss_event_id: UUID
    loss_event_name: str
    suggestion: Suggestion


class SuggestionService:
    def __init__(self, session: AsyncSession) -> None:
        self._treaties = TreatyRepository(session)
        self._versions = TreatyVersionRepository(session)
        self._events = LossEventRepository(session)
        self._losses = UnderlyingLossRepository(session)
        self._candidates = RecoveryCandidateRepository(session)

    async def for_organization(self, context: AuthenticatedContext) -> list[SuggestedRecovery]:
        org_id = context.organization.id
        events = await self._events.list_for_org(org_id)
        if not events:
            return []

        open_pairs = {
            (c.treaty_version_id, c.treaty_layer_id, c.loss_event_id)
            for c in await self._candidates.list(org_id)
        }
        gross_cache: dict[tuple[UUID, str], Decimal] = {}
        out: list[SuggestedRecovery] = []

        for treaty in await self._treaties.list(org_id):
            if treaty.current_version_id is None:
                continue
            version = await self._versions.get(org_id, treaty.current_version_id)
            if version is None or version.status not in _EXECUTABLE or not version.layers:
                continue
            layer = min(version.layers, key=lambda x: x.layer_no)
            window = _layer_window(version, layer)

            for event in events:
                gross = await self._gross(org_id, event, layer.currency, gross_cache)
                result = evaluate_suggestion(
                    EventFacts(
                        currency=event.currency,
                        date_from=event.date_of_loss_from,
                        date_to=event.date_of_loss_to,
                        gross_in_currency=gross,
                    ),
                    window,
                    has_open_candidate=(version.id, layer.id, event.id) in open_pairs,
                )
                if isinstance(result, Suggestion):
                    out.append(
                        SuggestedRecovery(
                            treaty_id=treaty.id,
                            treaty_name=treaty.name,
                            treaty_version_id=version.id,
                            treaty_layer_id=layer.id,
                            loss_event_id=event.id,
                            loss_event_name=event.name,
                            suggestion=result,
                        )
                    )
        return out

    async def _gross(
        self,
        org_id: UUID,
        event: LossEvent,
        currency: str,
        cache: dict[tuple[UUID, str], Decimal],
    ) -> Decimal:
        key = (event.id, currency)
        if key not in cache:
            losses = await self._losses.for_event(org_id, event.id)
            cache[key] = sum(
                (Decimal(x.gross_incurred) for x in losses if x.currency == currency),
                Decimal("0"),
            )
        return cache[key]


def _layer_window(version: TreatyVersion, layer: TreatyLayer) -> LayerWindow:
    return LayerWindow(
        currency=layer.currency,
        attachment=Decimal(layer.attachment),
        limit=Decimal(layer.limit),
        effective_date=version.effective_date,
        expiration_date=version.expiration_date,
    )
