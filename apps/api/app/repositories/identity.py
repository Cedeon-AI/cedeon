"""Repositories for organizations, users, memberships, and sessions."""

from __future__ import annotations

import datetime as dt
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.identity import Membership, Organization, User, UserSession


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
            select(Membership).where(
                Membership.organization_id == organization_id,
                Membership.user_id == user_id,
            )
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
