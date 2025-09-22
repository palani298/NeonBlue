"""Assignment endpoints."""

import logging
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth import auth
from app.schemas.assignments import (
    AssignmentResponse,
    BulkAssignmentRequest,
    BulkAssignmentResponse
)
from app.services.assignment import assignment_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/experiments/{experiment_id}/assignment/{user_id}",
    response_model=AssignmentResponse
)
async def get_assignment(
    experiment_id: int,
    user_id: str,
    enroll: bool = Query(
        default=False,
        description="Mark user as enrolled (exposed to experiment)"
    ),
    force_refresh: bool = Query(
        default=False,
        description="Force cache refresh"
    ),
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """
    Get or create user's variant assignment for an experiment.
    
    This endpoint is idempotent - once a user is assigned to a variant,
    they will always receive the same assignment.
    """
    try:
        assignment = await assignment_service.get_assignment(
            db=db,
            experiment_id=experiment_id,
            user_id=user_id,
            force_refresh=force_refresh,
            enroll=enroll
        )
        
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Experiment {experiment_id} not found or not active"
            )
        
        return assignment
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get assignment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get assignment"
        )


@router.post(
    "/assignments/bulk",
    response_model=BulkAssignmentResponse
)
async def get_bulk_assignments(
    request: BulkAssignmentRequest,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """
    Get assignments for one user across multiple experiments.
    
    Optimized for page load scenarios where a user might be in multiple experiments.
    """
    try:
        assignments = await assignment_service.get_bulk_assignments(
            db=db,
            user_id=request.user_id,
            experiment_ids=request.experiment_ids
        )
        
        return BulkAssignmentResponse(
            user_id=request.user_id,
            assignments=assignments
        )
        
    except Exception as e:
        logger.error(f"Failed to get bulk assignments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get bulk assignments"
        )