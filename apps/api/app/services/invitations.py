"""Team invitations — create, list, resend, revoke, and the public preview.

Accepting an invitation lives in ``AuthService`` (it mints users and sessions).
Only an admin can manage invitations; the invited email is the only identity that
can accept (ADR-0026).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_correlation_id, get_logger
from app.core.security import generate_session_token, hash_session_token
from app.core.text import normalize_email
from app.db.models.identity import Invitation
from app.domain.audit import ActorType, AuditRecord
from app.domain.organizations import ASSIGNABLE_ROLES, Role
from app.domain.organizations.invitations import InvitationStatus, is_live
from app.notifications import EmailMessage, EmailSender
from app.repositories.audit import AuditRepository
from app.repositories.identity import InvitationRepository, MembershipRepository, UserRepository
from app.services.auth import AuthenticatedContext
from app.services.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError

log = get_logger(__name__)


@dataclass(slots=True)
class IssuedInvitation:
    invitation: Invitation
    accept_url: str


@dataclass(slots=True)
class InvitationPreview:
    organization_name: str
    invited_email: str
    role: Role
    invited_by_name: str | None
    expired: bool
    account_exists: bool


class InvitationService:
    def __init__(self, session: AsyncSession, settings: Settings, *, email: EmailSender) -> None:
        self._session = session
        self._settings = settings
        self._email = email
        self._invitations = InvitationRepository(session)
        self._memberships = MembershipRepository(session)
        self._users = UserRepository(session)
        self._audit = AuditRepository(session)

    # --- reading -------------------------------------------------------

    async def list_pending(self, context: AuthenticatedContext) -> list[Invitation]:
        if not context.role.can_manage_members:
            raise PermissionDeniedError("only admins can view invitations")
        return await self._invitations.list_pending(context.organization.id)

    async def preview(self, raw_token: str) -> InvitationPreview:
        invitation = await self._resolve(raw_token)
        now = dt.datetime.now(dt.UTC)
        account = await self._users.get_by_email(invitation.email)
        return InvitationPreview(
            organization_name=invitation.organization.name,
            invited_email=invitation.email,
            role=invitation.role,
            invited_by_name=invitation.invited_by.name if invitation.invited_by else None,
            expired=not is_live(invitation.status, invitation.expires_at, now=now),
            account_exists=account is not None,
        )

    # --- writing ------------------------------------------------------

    async def invite(
        self, context: AuthenticatedContext, *, email: str, role: Role
    ) -> IssuedInvitation:
        self._require_admin(context)
        email = normalize_email(email)
        if role not in ASSIGNABLE_ROLES:
            raise ValidationError(f"role must be one of {[r.value for r in ASSIGNABLE_ROLES]}")

        existing_user = await self._users.get_by_email(email)
        if existing_user is not None and (
            await self._memberships.get(context.organization.id, existing_user.id) is not None
        ):
            raise ConflictError("that person is already a member of this organization")
        if await self._invitations.pending_for_email(context.organization.id, email) is not None:
            raise ConflictError("there is already a pending invitation for that email — resend it")

        return await self._issue(context, email=email, role=role, action="invitation.sent")

    async def resend(self, context: AuthenticatedContext, invitation_id: UUID) -> IssuedInvitation:
        self._require_admin(context)
        invitation = await self._get_pending(context, invitation_id)
        # rotate the token and refresh the clock on the same row
        raw_token = generate_session_token()
        invitation.token_hash = hash_session_token(raw_token, self._settings.session_secret)
        invitation.expires_at = dt.datetime.now(dt.UTC) + dt.timedelta(
            days=self._settings.invitation_ttl_days
        )
        accept_url = f"{self._settings.public_base_url.rstrip('/')}/invite/{raw_token}"
        await self._deliver(context, invitation, accept_url, action="invitation.resent")
        await self._session.commit()
        return IssuedInvitation(invitation=invitation, accept_url=accept_url)

    async def revoke(self, context: AuthenticatedContext, invitation_id: UUID) -> None:
        self._require_admin(context)
        invitation = await self._get_pending(context, invitation_id)
        invitation.status = InvitationStatus.REVOKED
        self._audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="invitation.revoked",
                entity_type="invitation",
                entity_id=invitation.id,
                summary=f"{context.user.email} revoked the invitation for {invitation.email}",
                payload={"email": invitation.email},
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()

    # --- helpers -----------------------------------------------------

    @staticmethod
    def _require_admin(context: AuthenticatedContext) -> None:
        if not context.role.can_manage_members:
            raise PermissionDeniedError("only admins can manage invitations")

    async def _get_pending(self, context: AuthenticatedContext, invitation_id: UUID) -> Invitation:
        invitation = await self._invitations.get(context.organization.id, invitation_id)
        if invitation is None:
            raise NotFoundError("invitation not found")
        if invitation.status is not InvitationStatus.PENDING:
            raise ConflictError(f"this invitation is already {invitation.status.value}")
        return invitation

    async def _resolve(self, raw_token: str) -> Invitation:
        token_hash = hash_session_token(raw_token, self._settings.session_secret)
        invitation = await self._invitations.get_by_token_hash(token_hash)
        if invitation is None:
            raise NotFoundError("this invitation link is not valid")
        return invitation

    async def _issue(
        self, context: AuthenticatedContext, *, email: str, role: Role, action: str
    ) -> IssuedInvitation:
        raw_token = generate_session_token()
        invitation = Invitation(
            organization_id=context.organization.id,
            email=email,
            role=role,
            token_hash=hash_session_token(raw_token, self._settings.session_secret),
            status=InvitationStatus.PENDING,
            invited_by_user_id=context.user.id,
            expires_at=dt.datetime.now(dt.UTC)
            + dt.timedelta(days=self._settings.invitation_ttl_days),
        )
        self._invitations.add(invitation)
        await self._session.flush()
        accept_url = f"{self._settings.public_base_url.rstrip('/')}/invite/{raw_token}"
        await self._deliver(context, invitation, accept_url, action=action)
        await self._session.commit()
        return IssuedInvitation(invitation=invitation, accept_url=accept_url)

    async def _deliver(
        self, context: AuthenticatedContext, invitation: Invitation, accept_url: str, *, action: str
    ) -> None:
        await self._email.send(
            EmailMessage(
                to=invitation.email,
                from_addr=self._settings.email_from,
                subject=f"{context.user.name} invited you to {context.organization.name} on Cedeon",
                text_body=(
                    f"{context.user.name} ({context.user.email}) invited you to join "
                    f"{context.organization.name} on Cedeon as {invitation.role.value}.\n\n"
                    f"Accept the invitation:\n{accept_url}\n\n"
                    f"This link expires in {self._settings.invitation_ttl_days} days."
                ),
            )
        )
        self._audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action=action,
                entity_type="invitation",
                entity_id=invitation.id,
                summary=(
                    f"{context.user.email} "
                    f"{'re-sent' if action == 'invitation.resent' else 'invited'} "
                    f"{invitation.email} as {invitation.role.value}"
                ),
                payload={"email": invitation.email, "role": invitation.role.value},
                correlation_id=get_correlation_id(),
            )
        )
