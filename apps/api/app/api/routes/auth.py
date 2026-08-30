"""Registration, login, logout, and the current-identity endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.api.dependencies.context import AppSettings, AuthedContext, AuthServiceDep
from app.api.schemas.auth import (
    LoginRequest,
    MeResponse,
    OrganizationSummary,
    RegisterRequest,
    SessionInfo,
    UserProfile,
)
from app.core.config import Settings
from app.services.auth import AuthenticatedContext

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        domain=settings.cookie_domain,
    )


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        domain=settings.cookie_domain,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def _me(context: AuthenticatedContext) -> MeResponse:
    return MeResponse(
        user=UserProfile(id=context.user.id, email=context.user.email, name=context.user.name),
        organization=OrganizationSummary(
            id=context.organization.id,
            name=context.organization.name,
            slug=context.organization.slug,
        ),
        role=context.role,
        session=SessionInfo(expires_at=context.session.expires_at),
    )


@router.post(
    "/register",
    response_model=MeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an organization and its first (owner) user",
    operation_id="register",
)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    auth: AuthServiceDep,
    settings: AppSettings,
) -> MeResponse:
    issue = await auth.register_organization(
        organization_name=payload.organization_name,
        email=payload.email,
        name=payload.name,
        password=payload.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )
    _set_session_cookie(response, issue.token, settings)
    return _me(issue.context)


@router.post(
    "/login",
    response_model=MeResponse,
    summary="Sign in with email and password",
    operation_id="login",
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    auth: AuthServiceDep,
    settings: AppSettings,
) -> MeResponse:
    issue = await auth.login(
        email=payload.email,
        password=payload.password,
        organization_id=payload.organization_id,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )
    _set_session_cookie(response, issue.token, settings)
    return _me(issue.context)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current session",
    operation_id="logout",
)
async def logout(
    context: AuthedContext,
    response: Response,
    auth: AuthServiceDep,
    settings: AppSettings,
) -> None:
    await auth.logout(context)
    _clear_session_cookie(response, settings)


@router.get(
    "/me",
    response_model=MeResponse,
    summary="The signed-in user, organization, and role",
    operation_id="getCurrentUser",
)
async def me(context: AuthedContext) -> MeResponse:
    return _me(context)
