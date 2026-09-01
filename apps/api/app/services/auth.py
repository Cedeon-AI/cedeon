"""Authentication & registration.

Tenant scope is always derived from the authenticated session here — never from
client input (see docs/SECURITY.md §1).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_correlation_id, get_logger
from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.core.security.passwords import TIMING_GUARD_HASH, WeakPasswordError
from app.core.security.sessions import tokens_equal
from app.core.text import normalize_email, slugify
from app.db.models.identity import Membership, Organization, User, UserSession
from app.domain.audit import ActorType, AuditRecord
from app.domain.organizations import Role
from app.domain.organizations.invitations import InvitationStatus, is_live
from app.repositories.audit import AuditRepository
from app.repositories.identity import (
    InvitationRepository,
    MembershipRepository,
    OrganizationRepository,
    SessionRepository,
    UserRepository,
)
from app.services.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)

log = get_logger(__name__)


@dataclass(slots=True)
class AuthenticatedContext:
    user: User
    organization: Organization
    membership: Membership
    session: UserSession

    @property
    def role(self) -> Role:
        return self.membership.role


@dataclass(slots=True)
class SessionIssue:
    """The result of establishing a session — raw token goes into the cookie."""

    token: str
    session: UserSession
    context: AuthenticatedContext


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self.organizations = OrganizationRepository(session)
        self.users = UserRepository(session)
        self.memberships = MembershipRepository(session)
        self.invitations = InvitationRepository(session)
        self.sessions = SessionRepository(session)
        self.audit = AuditRepository(session)

    # --- registration -----------------------------------------------------

    async def register_organization(
        self,
        *,
        organization_name: str,
        email: str,
        name: str,
        password: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> SessionIssue:
        email = normalize_email(email)
        if not organization_name.strip():
            raise ValidationError("organization name is required")
        if not name.strip():
            raise ValidationError("your name is required")

        if await self.users.get_by_email(email) is not None:
            raise ConflictError("an account with this email already exists")

        try:
            password_hash = hash_password(password)
        except WeakPasswordError as exc:
            raise ValidationError(str(exc)) from exc

        organization = Organization(
            name=organization_name.strip(),
            slug=await self._unique_slug(slugify(organization_name)),
        )
        self.organizations.add(organization)

        user = User(email=email, name=name.strip(), password_hash=password_hash)
        self.users.add(user)

        await self._session.flush()  # assign ids

        membership = Membership(organization_id=organization.id, user_id=user.id, role=Role.ADMIN)
        self.memberships.add(membership)
        await self._session.flush()

        self.audit.record(
            AuditRecord(
                organization_id=organization.id,
                actor_type=ActorType.USER,
                actor_id=user.id,
                action="organization.registered",
                entity_type="organization",
                entity_id=organization.id,
                summary=f"{user.email} registered organization {organization.name!r}",
                correlation_id=get_correlation_id(),
            )
        )

        issue = await self._issue_session(
            user=user,
            organization=organization,
            membership=membership,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        try:
            await self._session.commit()
        except IntegrityError as exc:  # pragma: no cover - race on unique email/slug
            await self._session.rollback()
            raise ConflictError("could not create organization, please retry") from exc
        return issue

    async def accept_invitation(
        self,
        *,
        raw_token: str,
        name: str | None = None,
        password: str | None = None,
        current: AuthenticatedContext | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> SessionIssue:
        """Join the organization an invitation names. Signed in → the invited email
        must match; signed out → a new account is created from ``name`` + ``password``
        (or the caller is told to sign in first if that email already has an account)."""
        token_hash = hash_session_token(raw_token, self._settings.session_secret)
        invitation = await self.invitations.get_by_token_hash(token_hash)
        now = dt.datetime.now(dt.UTC)
        if invitation is None or not tokens_equal(invitation.token_hash, token_hash):
            raise NotFoundError("this invitation link is not valid")
        if not is_live(invitation.status, invitation.expires_at, now=now):
            raise ConflictError("this invitation has expired or is no longer valid")

        organization = invitation.organization
        existing = await self.users.get_by_email(invitation.email)

        if current is not None:
            if normalize_email(current.user.email) != invitation.email:
                raise PermissionDeniedError("this invitation was sent to a different email address")
            user = current.user
        elif existing is not None:
            raise ConflictError(
                "an account already exists for this email — sign in, then open the link again"
            )
        else:
            if not (name and name.strip()):
                raise ValidationError("your name is required")
            if not password:
                raise ValidationError("a password is required")
            try:
                password_hash = hash_password(password)
            except WeakPasswordError as exc:
                raise ValidationError(str(exc)) from exc
            user = User(email=invitation.email, name=name.strip(), password_hash=password_hash)
            self.users.add(user)
            await self._session.flush()

        if await self.memberships.get(organization.id, user.id) is not None:
            raise ConflictError("you are already a member of this organization")

        membership = Membership(
            organization_id=organization.id, user_id=user.id, role=invitation.role
        )
        self.memberships.add(membership)
        invitation.status = InvitationStatus.ACCEPTED
        invitation.accepted_at = now
        user.last_login_at = now
        await self._session.flush()

        self.audit.record(
            AuditRecord(
                organization_id=organization.id,
                actor_type=ActorType.USER,
                actor_id=user.id,
                action="invitation.accepted",
                entity_type="membership",
                entity_id=membership.id,
                summary=f"{user.email} joined {organization.name} as {invitation.role.value}",
                payload={"role": invitation.role.value, "invitation_id": str(invitation.id)},
                correlation_id=get_correlation_id(),
            )
        )
        issue = await self._issue_session(
            user=user,
            organization=organization,
            membership=membership,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        try:
            await self._session.commit()
        except IntegrityError as exc:  # pragma: no cover - race
            await self._session.rollback()
            raise ConflictError("could not accept the invitation, please retry") from exc
        return issue

    # --- login / logout -------------------------------------------------

    async def login(
        self,
        *,
        email: str,
        password: str,
        organization_id: UUID | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> SessionIssue:
        email = normalize_email(email)
        user = await self.users.get_by_email(email)

        candidate_hash = user.password_hash if user and user.password_hash else TIMING_GUARD_HASH
        password_ok = verify_password(password, candidate_hash)

        if user is None or not password_ok:
            raise AuthenticationError("invalid email or password")
        if not user.is_active:
            raise AuthenticationError("this account is disabled")

        memberships = await self.memberships.list_for_user(user.id)
        membership = self._select_membership(memberships, organization_id)
        organization = membership.organization

        user.last_login_at = dt.datetime.now(dt.UTC)

        self.audit.record(
            AuditRecord(
                organization_id=organization.id,
                actor_type=ActorType.USER,
                actor_id=user.id,
                action="auth.login",
                entity_type="user",
                entity_id=user.id,
                summary=f"{user.email} signed in",
                correlation_id=get_correlation_id(),
            )
        )

        issue = await self._issue_session(
            user=user,
            organization=organization,
            membership=membership,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        await self._session.commit()
        return issue

    async def logout(self, context: AuthenticatedContext) -> None:
        SessionRepository.revoke(context.session, at=dt.datetime.now(dt.UTC))
        self.audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="auth.logout",
                entity_type="user",
                entity_id=context.user.id,
                summary=f"{context.user.email} signed out",
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()

    # --- session validation --------------------------------------------

    async def authenticate(self, token: str) -> AuthenticatedContext | None:
        if not token:
            return None
        token_hash = hash_session_token(token, self._settings.session_secret)
        session_row = await self.sessions.get_by_token_hash(token_hash)
        if session_row is None:
            return None

        now = dt.datetime.now(dt.UTC)
        if session_row.revoked_at is not None:
            return None
        if session_row.expires_at <= now:
            return None
        idle_limit = dt.timedelta(hours=self._settings.session_idle_timeout_hours)
        idle_for = now - session_row.last_seen_at
        if idle_for > idle_limit:
            return None

        membership = await self.memberships.get(session_row.organization_id, session_row.user_id)
        if membership is None:
            return None
        user = await self.users.get(session_row.user_id)
        organization = await self.organizations.get(session_row.organization_id)
        if user is None or organization is None or not user.is_active:
            return None

        # Throttle the "last seen" write to at most once per minute per session.
        if idle_for > dt.timedelta(seconds=60):
            SessionRepository.touch(session_row, at=now)
            await self._session.commit()

        return AuthenticatedContext(
            user=user,
            organization=organization,
            membership=membership,
            session=session_row,
        )

    # --- helpers ------------------------------------------------------

    async def _unique_slug(self, base: str) -> str:
        slug = base
        suffix = 2
        while await self.organizations.slug_exists(slug):
            slug = f"{base}-{suffix}"
            suffix += 1
        return slug

    def _select_membership(
        self, memberships: list[Membership], organization_id: UUID | None
    ) -> Membership:
        if not memberships:
            raise AuthenticationError("this account is not a member of any organization")
        if organization_id is not None:
            for membership in memberships:
                if membership.organization_id == organization_id:
                    return membership
            raise AuthenticationError("invalid email or password")
        if len(memberships) == 1:
            return memberships[0]
        raise ValidationError(
            "this account belongs to multiple organizations; specify organization_id",
            detail={
                "organizations": [
                    {"id": str(m.organization_id), "name": m.organization.name} for m in memberships
                ]
            },
        )

    async def _issue_session(
        self,
        *,
        user: User,
        organization: Organization,
        membership: Membership,
        user_agent: str | None,
        ip_address: str | None,
    ) -> SessionIssue:
        token = generate_session_token()
        now = dt.datetime.now(dt.UTC)
        session_row = UserSession(
            user_id=user.id,
            organization_id=organization.id,
            token_hash=hash_session_token(token, self._settings.session_secret),
            expires_at=now + dt.timedelta(hours=self._settings.session_ttl_hours),
            last_seen_at=now,
            user_agent=(user_agent or None),
            ip_address=(ip_address or None),
        )
        self.sessions.add(session_row)
        await self._session.flush()
        context = AuthenticatedContext(
            user=user,
            organization=organization,
            membership=membership,
            session=session_row,
        )
        return SessionIssue(token=token, session=session_row, context=context)
