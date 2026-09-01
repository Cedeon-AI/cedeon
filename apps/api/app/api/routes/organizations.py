"""Organization endpoints: read the current org, and (admin) rename it."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies.context import AdminContext, AuthedContext, DbSession
from app.api.schemas.auth import OrganizationSummary
from app.api.schemas.organizations import RenameOrganizationRequest
from app.core.logging import get_correlation_id
from app.domain.audit import ActorType, AuditRecord
from app.repositories.audit import AuditRepository
from app.services.errors import ValidationError

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _summary(org) -> OrganizationSummary:  # type: ignore[no-untyped-def]
    return OrganizationSummary(id=org.id, name=org.name, slug=org.slug)


@router.get(
    "/current",
    response_model=OrganizationSummary,
    summary="The caller's current organization",
    operation_id="getCurrentOrganization",
)
async def get_current_organization(context: AuthedContext) -> OrganizationSummary:
    return _summary(context.organization)


@router.patch(
    "/current",
    response_model=OrganizationSummary,
    summary="Rename the current organization (admin only)",
    operation_id="renameOrganization",
)
async def rename_organization(
    payload: RenameOrganizationRequest, context: AdminContext, session: DbSession
) -> OrganizationSummary:
    name = payload.name.strip()
    if not name:
        raise ValidationError("organization name is required")
    old_name = context.organization.name
    context.organization.name = name  # slug is a stable identity, not renamed
    AuditRepository(session).record(
        AuditRecord(
            organization_id=context.organization.id,
            actor_type=ActorType.USER,
            actor_id=context.user.id,
            action="organization.renamed",
            entity_type="organization",
            entity_id=context.organization.id,
            summary=f"{context.user.email} renamed the organization from {old_name!r} to {name!r}",
            payload={"from": old_name, "to": name},
            correlation_id=get_correlation_id(),
        )
    )
    await session.commit()
    return _summary(context.organization)
