"""Pydantic request/response models. These define the OpenAPI contract that the
web client is generated from."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
