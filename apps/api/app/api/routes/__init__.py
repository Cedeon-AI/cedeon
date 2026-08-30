"""Route aggregation."""

from fastapi import APIRouter

from app.api.routes import (
    auth,
    documents,
    health,
    losses,
    memberships,
    organizations,
    recoveries,
    reinsurance,
    treaties,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(memberships.router)
api_router.include_router(documents.router)
api_router.include_router(reinsurance.router)
api_router.include_router(treaties.router)
api_router.include_router(losses.imports_router)
api_router.include_router(losses.events_router)
api_router.include_router(recoveries.router)

__all__ = ["api_router"]
