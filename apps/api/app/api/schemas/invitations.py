from __future__ import annotations

import datetime as dt
from uuid import UUID

from pydantic import EmailStr, Field

from app.api.schemas import ApiModel
from app.domain.organizations import Role


class InviteRequest(ApiModel):
    email: EmailStr
    role: Role = Role.MEMBER


class InvitationOut(ApiModel):
    id: UUID
    email: EmailStr
    role: Role
    invited_by_name: str | None
    created_at: dt.datetime
    expires_at: dt.datetime
    # Present only in dev / console-email mode so the flow is walkable without a mailbox.
    accept_url: str | None = None


class InvitationList(ApiModel):
    invitations: list[InvitationOut]


class InvitationPreviewOut(ApiModel):
    organization_name: str
    invited_email: EmailStr
    role: Role
    invited_by_name: str | None
    expired: bool
    account_exists: bool


class AcceptInvitationRequest(ApiModel):
    name: str | None = Field(default=None, max_length=200)
    password: str | None = Field(default=None, max_length=1024)
