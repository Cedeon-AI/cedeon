"""Repositories for organizations, users, memberships, invitations, and sessions."""

from __future__ import annotations

import datetime as dt
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.identity import (
    Invitation,
    Membership,
    Organization,
    User,
    UserSession,
)
from app.domain.organizations import Role
from app.domain.organizations.invitations import InvitationStatus


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, org_id: UUID) -> Organization | None:
        return await self._session.get(Organization, org_id)

    async def get_by_slug(self, slug: str) -> Organization | None:
        result = await self._session.execute(select(Organization).where(Organization.slug == slug))
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str) -> bool:
        result = await self._session.execute(
            select(Organization.id).where(Organization.slug == slug)
        )
        return result.first() is not None

    def add(self, organization: Organization) -> None:
        self._session.add(organization)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    def add(self, user: User) -> None:
        self._session.add(user)


class MembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, organization_id: UUID, user_id: UUID) -> Membership | None:
        result = await self._session.execute(
            select(Membership)
            .where(
                Membership.organization_id == organization_id,
                Membership.user_id == user_id,
            )
            .options(selectinload(Membership.user))
        )
        return result.scalar_one_or_none()

    async def list_for_organization(self, organization_id: UUID) -> list[Membership]:
        result = await self._session.execute(
            select(Membership)
            .where(Membership.organization_id == organization_id)
            .options(selectinload(Membership.user))
            .order_by(Membership.created_at)
        )
        return list(result.scalars().all())

    async def list_for_user(self, user_id: UUID) -> list[Membership]:
        result = await self._session.execute(
            select(Membership)
            .where(Membership.user_id == user_id)
            .options(selectinload(Membership.organization))
            .order_by(Membership.created_at)
        )
        return list(result.scalars().all())

    def add(self, membership: Membership) -> None:
        self._session.add(membership)

    async def count_admins(self, organization_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.organization_id == organization_id,
                Membership.role == Role.ADMIN,
            )
        )
        return int(result.scalar_one())

    async def delete(self, membership: Membership) -> None:
        await self._session.delete(membership)


class InvitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, invitation: Invitation) -> None:
        self._session.add(invitation)

    async def get(self, organization_id: UUID, invitation_id: UUID) -> Invitation | None:
        result = await self._session.execute(
            select(Invitation).where(
                Invitation.id == invitation_id,
                Invitation.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_token_hash(self, token_hash: str) -> Invitation | None:
        result = await self._session.execute(
            select(Invitation)
            .where(Invitation.token_hash == token_hash)
            .options(selectinload(Invitation.organization), selectinload(Invitation.invited_by))
        )
        return result.scalar_one_or_none()

    async def pending_for_email(self, organization_id: UUID, email: str) -> Invitation | None:
        result = await self._session.execute(
            select(Invitation).where(
                Invitation.organization_id == organization_id,
                Invitation.email == email,
                Invitation.status == InvitationStatus.PENDING,
            )
        )
        return result.scalar_one_or_none()

    async def list_pending(self, organization_id: UUID) -> list[Invitation]:
        result = await self._session.execute(
            select(Invitation)
            .where(
                Invitation.organization_id == organization_id,
                Invitation.status == InvitationStatus.PENDING,
            )
            .options(selectinload(Invitation.invited_by))
            .order_by(Invitation.created_at.desc())
        )
        return list(result.scalars().all())


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_token_hash(self, token_hash: str) -> UserSession | None:
        result = await self._session.execute(
            select(UserSession).where(UserSession.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    def add(self, user_session: UserSession) -> None:
        self._session.add(user_session)

    @staticmethod
    def revoke(user_session: UserSession, *, at: dt.datetime) -> None:
        user_session.revoked_at = at

    @staticmethod
    def touch(user_session: UserSession, *, at: dt.datetime) -> None:
        user_session.last_seen_at = at
