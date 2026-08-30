"""Route aggregation."""

from fastapi import APIRouter

from app.api.routes import (
    auth,
    documents,
    health,
    memberships,
    organizations,
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

__all__ = ["api_router"]
