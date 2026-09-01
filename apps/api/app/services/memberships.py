"""Membership management: list members, change a member's role, remove a member.

Adding people is the invitation flow (``app/services/invitations.py``). An
organization always keeps at least one admin — that rule replaces a single
immutable owner (ADR-0026).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_correlation_id
from app.db.models.identity import Membership
from app.domain.audit import ActorType, AuditRecord
from app.domain.organizations import ASSIGNABLE_ROLES, Role
from app.repositories.audit import AuditRepository
from app.repositories.identity import MembershipRepository, UserRepository
from app.services.auth import AuthenticatedContext
from app.services.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)


class MembershipService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.users = UserRepository(session)
        self.memberships = MembershipRepository(session)
        self.audit = AuditRepository(session)

    async def list_members(self, context: AuthenticatedContext) -> list[Membership]:
        return await self.memberships.list_for_organization(context.organization.id)

    async def change_role(
        self, context: AuthenticatedContext, user_id: UUID, new_role: Role
    ) -> Membership:
        self._require_admin(context)
        if new_role not in ASSIGNABLE_ROLES:
            raise ValidationError(f"role must be one of {[r.value for r in ASSIGNABLE_ROLES]}")

        membership = await self._member(context, user_id)
        if membership.role is new_role:
            return membership

        # Demoting the last admin would lock the organization out of member management.
        if membership.role is Role.ADMIN and new_role is not Role.ADMIN:
            await self._guard_last_admin(context, "demote")

        old_role = membership.role
        membership.role = new_role
        self.audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="membership.role_changed",
                entity_type="membership",
                entity_id=membership.id,
                summary=(
                    f"{context.user.email} changed {membership.user.email} "
                    f"from {old_role.value} to {new_role.value}"
                ),
                payload={"from": old_role.value, "to": new_role.value},
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        return membership

    async def remove_member(self, context: AuthenticatedContext, user_id: UUID) -> None:
        self._require_admin(context)
        membership = await self._member(context, user_id)
        if membership.role is Role.ADMIN:
            await self._guard_last_admin(context, "remove")

        removed_email = membership.user.email
        await self.memberships.delete(membership)
        self.audit.record(
            AuditRecord(
                organization_id=context.organization.id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="membership.removed",
                entity_type="user",
                entity_id=user_id,
                summary=(
                    f"{context.user.email} removed {removed_email} from "
                    f"{context.organization.name}"
                    + (" (left the organization)" if user_id == context.user.id else "")
                ),
                payload={"member_email": removed_email},
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()

    # --- helpers -----------------------------------------------------

    @staticmethod
    def _require_admin(context: AuthenticatedContext) -> None:
        if not context.role.can_manage_members:
            raise PermissionDeniedError("only admins can manage members")

    async def _member(self, context: AuthenticatedContext, user_id: UUID) -> Membership:
        membership = await self.memberships.get(context.organization.id, user_id)
        if membership is None:
            raise NotFoundError("that person is not a member of this organization")
        return membership

    async def _guard_last_admin(self, context: AuthenticatedContext, verb: str) -> None:
        if await self.memberships.count_admins(context.organization.id) <= 1:
            raise ConflictError(
                f"cannot {verb} the last admin — promote another member to admin first"
            )
