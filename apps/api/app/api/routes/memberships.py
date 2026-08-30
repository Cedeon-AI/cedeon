"""Membership listing and (admin) member creation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencies.context import AuthedContext, DbSession, require_role
from app.api.schemas.memberships import AddMemberRequest, MemberList, MemberOut
from app.domain.organizations import Role
from app.services.memberships import MembershipService

router = APIRouter(prefix="/memberships", tags=["memberships"])


@router.get(
    "",
    response_model=MemberList,
    summary="List members of the current organization",
    operation_id="listMembers",
)
async def list_members(context: AuthedContext, session: DbSession) -> MemberList:
    service = MembershipService(session)
    memberships = await service.list_members(context)
    return MemberList(
        members=[
            MemberOut(
                user_id=m.user_id,
                email=m.user.email,
                name=m.user.name,
                role=m.role,
                joined_at=m.created_at,
            )
            for m in memberships
        ]
    )


@router.post(
    "",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a member to the current organization (admin/owner only)",
    operation_id="addMember",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def add_member(
    payload: AddMemberRequest,
    context: AuthedContext,
    session: DbSession,
) -> MemberOut:
    service = MembershipService(session)
    membership = await service.add_member(
        context,
        email=payload.email,
        name=payload.name,
        role=payload.role,
        initial_password=payload.initial_password,
    )
    return MemberOut(
        user_id=membership.user_id,
        email=membership.user.email,
        name=membership.user.name,
        role=membership.role,
        joined_at=membership.created_at,
    )
