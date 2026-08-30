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
from app.services.documents import DocumentService, ParseEnqueuer
from app.services.errors import AuthenticationError, PermissionDeniedError
from app.storage import ObjectStore, build_object_store


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


def get_object_store(settings: AppSettings) -> ObjectStore:
    return build_object_store(settings)


ObjectStoreDep = Annotated[ObjectStore, Depends(get_object_store)]


async def get_parse_enqueuer() -> ParseEnqueuer:
    # Imported lazily so the Procrastinate connector is not constructed at import time.
    from app.jobs.tasks import enqueue_parse_document

    return enqueue_parse_document


def get_document_service(
    session: DbSession,
    settings: AppSettings,
    store: ObjectStoreDep,
    enqueue_parse: Annotated[ParseEnqueuer, Depends(get_parse_enqueuer)],
) -> DocumentService:
    return DocumentService(
        session,
        store,
        enqueue_parse=enqueue_parse,
        max_upload_bytes=settings.document_max_upload_mb * 1024 * 1024,
    )


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]


def require_role(
    minimum: Role,
) -> Callable[[AuthenticatedContext], Awaitable[AuthenticatedContext]]:
    """Build a FastAPI dependency that enforces a minimum role."""

    async def _dependency(context: AuthedContext) -> AuthenticatedContext:
        if not context.role.satisfies(minimum):
            raise PermissionDeniedError(f"requires the {minimum.value} role or higher")
        return context

    return _dependency
