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
from app.db.models.identity import Membership, Organization, SignupCode, User, UserSession
from app.domain.audit import ActorType, AuditRecord
from app.domain.organizations import Role, is_redeemable
from app.domain.organizations.invitations import InvitationStatus, is_live
from app.notifications import EmailMessage, EmailSender
from app.repositories.audit import AuditRepository
from app.repositories.identity import (
    InvitationRepository,
    MembershipRepository,
    OrganizationRepository,
    SessionRepository,
    SignupCodeRepository,
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
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        email: EmailSender | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._email = email
        self.organizations = OrganizationRepository(session)
        self.users = UserRepository(session)
        self.memberships = MembershipRepository(session)
        self.invitations = InvitationRepository(session)
        self.signup_codes = SignupCodeRepository(session)
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
        signup_code: str | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> SessionIssue:
        email = normalize_email(email)
        if not organization_name.strip():
            raise ValidationError("organization name is required")
        if not name.strip():
            raise ValidationError("your name is required")

        # Gate on signup_mode before anything is created (ADR-0028).
        code = await self._resolve_signup_code(signup_code)

        if await self.users.get_by_email(email) is not None:
            raise ConflictError("an account with this email already exists")

        try:
            password_hash = hash_password(password)
        except WeakPasswordError as exc:
            raise ValidationError(str(exc)) from exc

        organization = Organization(
            name=organization_name.strip(),
            slug=await self._unique_slug(slugify(organization_name)),
            ai_budget_usd=code.grant_ai_budget_usd if code is not None else None,
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
                payload=(
                    {"signup_code": code.label, "ai_budget_usd": str(organization.ai_budget_usd)}
                    if code is not None
                    else {}
                ),
                correlation_id=get_correlation_id(),
            )
        )
        if code is not None:
            assert signup_code is not None  # guaranteed in "code" mode
            redeemed = await self.signup_codes.try_redeem(
                hash_session_token(signup_code.strip(), self._settings.session_secret),
                now=dt.datetime.now(dt.UTC),
            )
            if not redeemed:  # lost a race, or revoked between check and here
                raise ConflictError("that access code was just used up — please request a new one")
            self.audit.record(
                AuditRecord(
                    organization_id=organization.id,
                    actor_type=ActorType.USER,
                    actor_id=user.id,
                    action="signup_code.redeemed",
                    entity_type="signup_code",
                    entity_id=code.id,
                    summary=f"access code {code.label!r} redeemed by {user.email}",
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

        await self._notify_ops_of_signup(organization, user, code)
        return issue

    async def _resolve_signup_code(self, raw_code: str | None) -> SignupCode | None:
        """Enforce ``signup_mode``. Returns the redeemable code row in ``code`` mode,
        ``None`` in ``open`` mode, and raises in ``closed`` mode or on a bad code."""
        mode = self._settings.signup_mode
        if mode == "closed":
            raise PermissionDeniedError(
                "Cedeon is invite-only right now — contact us to request access"
            )
        if mode == "open":
            return None

        if not raw_code or not raw_code.strip():
            raise ValidationError("an access code is required to create a workspace")
        code_hash = hash_session_token(raw_code.strip(), self._settings.session_secret)
        code = await self.signup_codes.get_by_code_hash(code_hash)
        if code is None or not tokens_equal(code.code_hash, code_hash):
            raise ValidationError("that access code is not valid")
        if not is_redeemable(
            revoked_at=code.revoked_at,
            expires_at=code.expires_at,
            max_uses=code.max_uses,
            redeemed_count=code.redeemed_count,
            now=dt.datetime.now(dt.UTC),
        ):
            raise ValidationError("that access code has expired or has already been used")
        return code

    async def _notify_ops_of_signup(
        self, organization: Organization, user: User, code: SignupCode | None
    ) -> None:
        if not (self._settings.ops_email and self._email):
            return
        budget = (
            f"${organization.ai_budget_usd}/mo AI budget"
            if organization.ai_budget_usd is not None
            else "unlimited AI budget"
        )
        via = f" via code {code.label!r}" if code is not None else ""
        try:
            await self._email.send(
                EmailMessage(
                    to=self._settings.ops_email,
                    subject=f"[Cedeon] new workspace: {organization.name}",
                    text_body=(
                        f"{user.email} created the workspace {organization.name!r} "
                        f"({organization.slug}){via}.\n{budget}."
                    ),
                    from_addr=self._settings.email_from,
                )
            )
        except Exception:  # a failed ops notice must not fail registration
            log.warning("auth.ops_notify_failed", organization_id=str(organization.id))

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
