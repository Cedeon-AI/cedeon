from __future__ import annotations

import datetime as dt
from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field

from app.api.schemas import ApiModel
from app.domain.organizations import Role


class RegisterRequest(ApiModel):
    organization_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=12, max_length=1024)
    # Required only when signup_mode is "code" (surfaced by GET /auth/config).
    signup_code: str | None = Field(default=None, max_length=200)


class AuthConfigResponse(ApiModel):
    """Public. Tells the web client how registration is gated (ADR-0028)."""

    signup_mode: Literal["open", "code", "closed"]


class LoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)
    organization_id: UUID | None = None


class OrganizationSummary(ApiModel):
    id: UUID
    name: str
    slug: str


class UserProfile(ApiModel):
    id: UUID
    email: EmailStr
    name: str


class SessionInfo(ApiModel):
    expires_at: dt.datetime


class MeResponse(ApiModel):
    user: UserProfile
    organization: OrganizationSummary
    role: Role
    session: SessionInfo
