"""Organization endpoints (MVP: read the current org only)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies.context import AuthedContext
from app.api.schemas.auth import OrganizationSummary

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get(
    "/current",
    response_model=OrganizationSummary,
    summary="The caller's current organization",
    operation_id="getCurrentOrganization",
)
async def get_current_organization(context: AuthedContext) -> OrganizationSummary:
    return OrganizationSummary(
        id=context.organization.id,
        name=context.organization.name,
        slug=context.organization.slug,
    )
