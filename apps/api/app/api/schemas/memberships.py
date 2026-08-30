from __future__ import annotations

import datetime as dt
from uuid import UUID

from pydantic import EmailStr, Field

from app.api.schemas import ApiModel
from app.domain.organizations import Role


class MemberOut(ApiModel):
    user_id: UUID
    email: EmailStr
    name: str
    role: Role
    joined_at: dt.datetime


class MemberList(ApiModel):
    members: list[MemberOut]


class AddMemberRequest(ApiModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    role: Role = Role.MEMBER
    initial_password: str = Field(min_length=12, max_length=1024)
