from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from app.api.schemas import ApiModel


class RecoveryPreviewRequest(ApiModel):
    gross_loss: str = Field(min_length=1, max_length=40, description="gross event incurred")


class CalcStepOut(ApiModel):
    label: str
    expression: str
    result: str


class AllocationOut(ApiModel):
    reinsurer_id: str
    reinsurer_name: str
    share: Decimal
    amount: Decimal


class RecoveryPreviewResponse(ApiModel):
    engine_version: str
    currency: str
    gross_loss: Decimal
    attachment: Decimal
    limit: Decimal
    amount_above_attachment: Decimal
    layer_recovery: Decimal
    cedent_retention: Decimal
    allocations: list[AllocationOut]
    trace: list[CalcStepOut]
