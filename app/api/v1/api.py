"""API v1 router aggregator."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    experiments, 
    assignments, 
    events, 
    results, 
    variants, 
    users, 
    api_tokens,
    data_management,
    analytics
)

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(
    experiments.router,
    prefix="/experiments",
    tags=["experiments"]
)

api_router.include_router(
    variants.router,
    prefix="/variants",
    tags=["variants"]
)

api_router.include_router(
    assignments.router,
    prefix="/assignments",
    tags=["assignments"]
)

api_router.include_router(
    events.router,
    prefix="/events",
    tags=["events"]
)

api_router.include_router(
    results.router,
    tags=["results"]
)

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["users"]
)

api_router.include_router(
    api_tokens.router,
    prefix="/api-tokens",
    tags=["api-tokens"]
)

api_router.include_router(
    data_management.router,
    prefix="/data-management",
    tags=["data-management"]
)

api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["analytics"]
)
