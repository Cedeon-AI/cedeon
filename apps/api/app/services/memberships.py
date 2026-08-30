"""Membership management. A proper email invitation flow is deferred; for MVP an
admin creates the member directly with an initial password."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_correlation_id
from app.core.security import hash_password
from app.core.security.passwords import WeakPasswordError
from app.core.text import normalize_email
from app.db.models.identity import Membership, User
from app.domain.audit import ActorType, AuditRecord
from app.domain.organizations import Role
from app.repositories.audit import AuditRepository
from app.repositories.identity import MembershipRepository, UserRepository
from app.services.auth import AuthenticatedContext
from app.services.errors import ConflictError, PermissionDeniedError, ValidationError


class MembershipService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.users = UserRepository(session)
        self.memberships = MembershipRepository(session)
        self.audit = AuditRepository(session)

    async def list_members(self, context: AuthenticatedContext) -> list[Membership]:
        return await self.memberships.list_for_organization(context.organization.id)

    async def add_member(
        self,
        context: AuthenticatedContext,
        *,
        email: str,
        name: str,
        role: Role,
        initial_password: str,
    ) -> Membership:
        if not context.role.can_manage_members:
            raise PermissionDeniedError("only admins and owners can add members")
        if role is Role.OWNER and context.role is not Role.OWNER:
            raise PermissionDeniedError("only an owner can grant the owner role")

        email = normalize_email(email)
        if not name.strip():
            raise ValidationError("member name is required")

        user = await self.users.get_by_email(email)
        if user is None:
            try:
                password_hash = hash_password(initial_password)
            except WeakPasswordError as exc:
                raise ValidationError(str(exc)) from exc
            user = User(email=email, name=name.strip(), password_hash=password_hash)
            self.users.add(user)
            await self._session.flush()
        else:
            existing = await self.memberships.get(context.organization.id, user.id)
            if existing is not None:
                raise ConflictError("that person is already a member of this organization")

        membership = Membership(organization_id=context.organization.id, user=user, role=role)
        self.memberships.add(membership)
        await self._session.flush()

        self.audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="membership.added",
                entity_type="membership",
                entity_id=membership.id,
                summary=f"{context.user.email} added {email} as {role.value}",
                payload={"role": role.value, "member_email": email},
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        return membership
