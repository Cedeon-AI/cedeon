from __future__ import annotations

import datetime as dt
from uuid import UUID

from pydantic import EmailStr

from app.api.schemas import ApiModel
from app.domain.organizations import Role


class MemberOut(ApiModel):
    user_id: UUID
    email: EmailStr
    name: str
    role: Role
    joined_at: dt.datetime
    is_self: bool = False


class MemberList(ApiModel):
    members: list[MemberOut]


class ChangeRoleRequest(ApiModel):
    role: Role
