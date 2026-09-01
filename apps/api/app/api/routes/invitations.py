"""Team invitations.

Managing them (`/invitations*`) requires admin. The public preview and accept
endpoints (`/auth/invitation/*`) mint a session and so require no existing session.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, Response, status

from app.api.dependencies.context import (
    AdminContext,
    AppSettings,
    AuthServiceDep,
    InvitationServiceDep,
    OptionalContext,
)
from app.api.routes.auth import _client_ip, _me, _set_session_cookie
from app.api.schemas.auth import MeResponse
from app.api.schemas.invitations import (
    AcceptInvitationRequest,
    InvitationList,
    InvitationOut,
    InvitationPreviewOut,
    InviteRequest,
)
from app.services.invitations import IssuedInvitation

manage_router = APIRouter(prefix="/invitations", tags=["invitations"])
public_router = APIRouter(prefix="/auth/invitation", tags=["invitations"])


def _invitation_out(issued: IssuedInvitation, *, settings: AppSettings) -> InvitationOut:
    inv = issued.invitation
    return InvitationOut(
        id=inv.id,
        email=inv.email,
        role=inv.role,
        invited_by_name=inv.invited_by.name if inv.invited_by else None,
        created_at=inv.created_at,
        expires_at=inv.expires_at,
        accept_url=issued.accept_url if settings.email_sender == "console" else None,
    )


@manage_router.get(
    "", response_model=InvitationList, summary="Pending invitations", operation_id="listInvitations"
)
async def list_invitations(
    context: AdminContext, service: InvitationServiceDep, settings: AppSettings
) -> InvitationList:
    pending = await service.list_pending(context)
    return InvitationList(
        invitations=[
            InvitationOut(
                id=inv.id,
                email=inv.email,
                role=inv.role,
                invited_by_name=inv.invited_by.name if inv.invited_by else None,
                created_at=inv.created_at,
                expires_at=inv.expires_at,
                accept_url=None,
            )
            for inv in pending
        ]
    )


@manage_router.post(
    "",
    response_model=InvitationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a teammate by email (admin only)",
    operation_id="createInvitation",
)
async def create_invitation(
    payload: InviteRequest,
    context: AdminContext,
    service: InvitationServiceDep,
    settings: AppSettings,
) -> InvitationOut:
    issued = await service.invite(context, email=payload.email, role=payload.role)
    return _invitation_out(issued, settings=settings)


@manage_router.post(
    "/{invitation_id}/resend",
    response_model=InvitationOut,
    summary="Rotate the token and re-send (admin only)",
    operation_id="resendInvitation",
)
async def resend_invitation(
    invitation_id: UUID,
    context: AdminContext,
    service: InvitationServiceDep,
    settings: AppSettings,
) -> InvitationOut:
    issued = await service.resend(context, invitation_id)
    return _invitation_out(issued, settings=settings)


@manage_router.post(
    "/{invitation_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a pending invitation (admin only)",
    operation_id="revokeInvitation",
)
async def revoke_invitation(
    invitation_id: UUID, context: AdminContext, service: InvitationServiceDep
) -> None:
    await service.revoke(context, invitation_id)


@public_router.get(
    "/{token}",
    response_model=InvitationPreviewOut,
    summary="What an invitation link offers — organization, role, inviter",
    operation_id="previewInvitation",
)
async def preview_invitation(token: str, service: InvitationServiceDep) -> InvitationPreviewOut:
    preview = await service.preview(token)
    return InvitationPreviewOut(
        organization_name=preview.organization_name,
        invited_email=preview.invited_email,
        role=preview.role,
        invited_by_name=preview.invited_by_name,
        expired=preview.expired,
        account_exists=preview.account_exists,
    )


@public_router.post(
    "/{token}/accept",
    response_model=MeResponse,
    summary="Join the organization the invitation names",
    operation_id="acceptInvitation",
)
async def accept_invitation(
    token: str,
    payload: AcceptInvitationRequest,
    request: Request,
    response: Response,
    auth: AuthServiceDep,
    settings: AppSettings,
    current: OptionalContext,
) -> MeResponse:
    issue = await auth.accept_invitation(
        raw_token=token,
        name=payload.name,
        password=payload.password,
        current=current,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )
    _set_session_cookie(response, issue.token, settings)
    return _me(issue.context)
