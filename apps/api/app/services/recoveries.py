"""Read-only 'what would this treaty recover' preview.

Uses the deterministic engine against a *validated* treaty version. Nothing is
persisted — the real RecoveryCandidate machinery is Phase 6."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.money import Money, MoneyError
from app.domain.recoveries import Participation, RecoveryCalculation, calculate_recovery
from app.domain.treaties import TreatyVersionStatus
from app.repositories.reinsurance import TreatyRepository, TreatyVersionRepository
from app.services.auth import AuthenticatedContext
from app.services.errors import ConflictError, NotFoundError, ValidationError


class RecoveryPreviewService:
    def __init__(self, session: AsyncSession) -> None:
        self._treaties = TreatyRepository(session)
        self._versions = TreatyVersionRepository(session)

    async def preview(
        self, context: AuthenticatedContext, treaty_id: UUID, *, gross_loss_amount: str
    ) -> RecoveryCalculation:
        treaty = await self._treaties.get(context.organization.id, treaty_id)
        if treaty is None or treaty.current_version_id is None:
            raise NotFoundError("treaty not found")
        version = await self._versions.get(context.organization.id, treaty.current_version_id)
        if version is None:
            raise NotFoundError("treaty version not found")
        if version.status not in (
            TreatyVersionStatus.VALIDATED,
            TreatyVersionStatus.ACTIVE,
        ):
            raise ConflictError("the treaty must be validated before a recovery can be computed")
        if not version.layers:
            raise ConflictError("the validated treaty version has no layer")

        layer = min(version.layers, key=lambda x: x.layer_no)
        currency = layer.currency

        try:
            gross_loss = Money(Decimal(gross_loss_amount), currency)
        except (InvalidOperation, MoneyError) as exc:
            raise ValidationError(f"gross loss is not a valid amount: {exc}") from exc

        participations = [
            Participation(
                key=str(p.reinsurer_id),
                label=p.reinsurer.name,
                share=Decimal(p.placed_share),
            )
            for p in version.participations
        ]

        return calculate_recovery(
            gross_loss=gross_loss,
            attachment=Money(Decimal(layer.attachment), currency),
            limit=Money(Decimal(layer.limit), currency),
            participations=participations,
        )
