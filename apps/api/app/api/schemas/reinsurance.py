from __future__ import annotations

import datetime as dt
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.api.schemas import ApiModel
from app.domain.treaties import TreatyType, TreatyVersionStatus


class CedentOut(ApiModel):
    id: UUID
    name: str


class CedentCreate(ApiModel):
    name: str = Field(min_length=1, max_length=300)


class CedentList(ApiModel):
    cedents: list[CedentOut]


class ReinsurerOut(ApiModel):
    id: UUID
    name: str


class ReinsurerCreate(ApiModel):
    name: str = Field(min_length=1, max_length=300)


class ReinsurerList(ApiModel):
    reinsurers: list[ReinsurerOut]


class ProgramOut(ApiModel):
    id: UUID
    name: str
    treaty_year: int
    description: str | None
    cedent_id: UUID
    cedent_name: str
    treaty_count: int


class ProgramCreate(ApiModel):
    cedent_id: UUID
    name: str = Field(min_length=1, max_length=300)
    treaty_year: int = Field(ge=1900, le=2100)
    description: str | None = Field(default=None, max_length=2000)


class ProgramList(ApiModel):
    programs: list[ProgramOut]


class ParticipationOut(ApiModel):
    reinsurer_id: UUID
    reinsurer_name: str
    placed_share: Decimal
    signed_share: Decimal | None
    broker_name: str | None
    treaty_layer_id: UUID | None = None


class LayerOut(ApiModel):
    layer_no: int
    attachment: Decimal
    limit: Decimal
    currency: str
    reinstatements: int | None
    description: str | None
    # This layer's own reinsurer panel; empty means it uses the programme panel.
    participations: list[ParticipationOut]
    # Reinstatement premium terms (human-validated).
    deposit_premium: Decimal | None = None
    reinstatement_rates: list[str] | None = None
    reinstatement_basis: str | None = None


class LayerParticipationInput(ApiModel):
    reinsurer_name: str = Field(min_length=1, max_length=300)
    placed_share_percent: Decimal = Field(ge=0, le=100)


class SetLayerParticipationsRequest(ApiModel):
    """The reinsurer panel for one layer. An empty list clears the override."""

    panel: list[LayerParticipationInput] = Field(default_factory=list)


class SetReinstatementTermsRequest(ApiModel):
    """Reinstatement premium terms for one layer. Empty ``rates`` clears the terms."""

    deposit_premium: Decimal | None = Field(default=None, ge=0)
    rates: list[Decimal] = Field(default_factory=list)
    basis: str = "flat"  # flat | pro_rata_time


class TermOut(ApiModel):
    key: str
    value: dict
    status: str


class TreatyVersionOut(ApiModel):
    id: UUID
    version_no: int
    status: TreatyVersionStatus
    effective_date: dt.date | None
    expiration_date: dt.date | None
    currency: str | None
    source_document_id: UUID | None
    validated_at: dt.datetime | None
    layers: list[LayerOut]
    participations: list[ParticipationOut]
    terms: list[TermOut]


class TreatyVersionSummary(ApiModel):
    id: UUID
    version_no: int
    status: TreatyVersionStatus
    source_document_id: UUID | None


class TreatyOut(ApiModel):
    id: UUID
    name: str
    treaty_type: TreatyType
    program_id: UUID
    program_name: str
    cedent_name: str
    created_at: dt.datetime
    current_version: TreatyVersionSummary | None


class TreatyList(ApiModel):
    treaties: list[TreatyOut]


class TreatyCreate(ApiModel):
    program_id: UUID
    name: str = Field(min_length=1, max_length=300)
    source_document_id: UUID | None = None


class NewTreatyVersionRequest(ApiModel):
    """Supersede the current version — the path an endorsement takes."""

    note: str = Field(
        min_length=1, max_length=300, description="what changed, e.g. 'Endorsement 3'"
    )
    source_document_id: UUID | None = Field(
        default=None, description="the endorsement document, if uploaded"
    )


class TreatyDetail(ApiModel):
    treaty: TreatyOut
    current_version: TreatyVersionOut | None
    versions: list[TreatyVersionSummary] = Field(default_factory=list)
