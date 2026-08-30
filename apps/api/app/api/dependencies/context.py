"""Request-scoped dependencies: DB session, settings, auth service, and the
authenticated context that carries the tenant scope."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_sessionmaker
from app.domain.organizations import Role
from app.services.auth import AuthenticatedContext, AuthService
from app.services.errors import AuthenticationError, PermissionDeniedError


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def get_settings_dep() -> Settings:
    return get_settings()


DbSession = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings_dep)]


def get_auth_service(session: DbSession, settings: AppSettings) -> AuthService:
    return AuthService(session, settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def current_context(
    request: Request,
    settings: AppSettings,
    auth: AuthServiceDep,
) -> AuthenticatedContext:
    token = request.cookies.get(settings.cookie_name, "")
    context = await auth.authenticate(token)
    if context is None:
        raise AuthenticationError("authentication required")
    return context


AuthedContext = Annotated[AuthenticatedContext, Depends(current_context)]


def require_role(
    minimum: Role,
) -> Callable[[AuthenticatedContext], Awaitable[AuthenticatedContext]]:
    """Build a FastAPI dependency that enforces a minimum role."""

    async def _dependency(context: AuthedContext) -> AuthenticatedContext:
        if not context.role.satisfies(minimum):
            raise PermissionDeniedError(f"requires the {minimum.value} role or higher")
        return context

    return _dependency
