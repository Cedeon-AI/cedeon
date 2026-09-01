from __future__ import annotations

from pydantic import Field

from app.api.schemas import ApiModel


class RenameOrganizationRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)
