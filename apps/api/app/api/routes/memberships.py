"""Organization members: list, change role, remove. Adding people is the
invitation flow (see routes/invitations.py)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies.context import AdminContext, AuthedContext, DbSession
from app.api.schemas.memberships import ChangeRoleRequest, MemberList, MemberOut
from app.services.memberships import MembershipService

router = APIRouter(prefix="/memberships", tags=["memberships"])


def _member_out(m, *, self_user_id) -> MemberOut:  # type: ignore[no-untyped-def]
    return MemberOut(
        user_id=m.user_id,
        email=m.user.email,
        name=m.user.name,
        role=m.role,
        joined_at=m.created_at,
        is_self=m.user_id == self_user_id,
    )


@router.get(
    "",
    response_model=MemberList,
    summary="List members of the current organization",
    operation_id="listMembers",
)
async def list_members(context: AuthedContext, session: DbSession) -> MemberList:
    members = await MembershipService(session).list_members(context)
    return MemberList(members=[_member_out(m, self_user_id=context.user.id) for m in members])


@router.patch(
    "/{user_id}",
    response_model=MemberOut,
    summary="Change a member's role (admin only)",
    operation_id="changeMemberRole",
)
async def change_member_role(
    user_id: UUID,
    payload: ChangeRoleRequest,
    context: AdminContext,
    session: DbSession,
) -> MemberOut:
    membership = await MembershipService(session).change_role(context, user_id, payload.role)
    return _member_out(membership, self_user_id=context.user.id)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from the current organization (admin only)",
    operation_id="removeMember",
)
async def remove_member(user_id: UUID, context: AdminContext, session: DbSession) -> None:
    await MembershipService(session).remove_member(context, user_id)
