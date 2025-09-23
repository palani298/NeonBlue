"""API v1 router aggregator."""

from fastapi import APIRouter

from app.api.v1.endpoints import experiments, assignments, events, results

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(
    experiments.router,
    prefix="/experiments",
    tags=["experiments"]
)

api_router.include_router(
    assignments.router,
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
