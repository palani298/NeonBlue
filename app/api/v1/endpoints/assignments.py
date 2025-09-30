"""Assignment endpoints."""

import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth import auth
from app.schemas.assignments import (
    AssignmentResponse,
    AssignmentUpdate,
    BulkAssignmentRequest,
    BulkAssignmentResponse,
    BulkAssignmentCreate,
    BulkAssignmentUpdate,
    BulkAssignmentDelete,
    BulkAssignmentOperationResponse
)
from app.services.assignment_v2 import assignment_service_v2 as assignment_service
from app.services.bulk_operations import bulk_operations_service

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
    token_data: dict = Depends(auth.require_scope("assignments:read"))
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
    token_data: dict = Depends(auth.require_scope("assignments:read"))
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


@router.get("/list", response_model=List[AssignmentResponse])
async def list_assignments(
    experiment_id: Optional[int] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.require_scope("assignments:read"))
):
    """List assignments with optional filtering."""
    from app.models.models import Assignment
    from sqlalchemy import select
    
    query = select(Assignment).limit(limit).offset(offset)
    
    if experiment_id:
        query = query.where(Assignment.experiment_id == experiment_id)
    if user_id:
        query = query.where(Assignment.user_id == user_id)
    
    result = await db.execute(query.order_by(Assignment.assigned_at.desc()))
    assignments = result.scalars().all()
    
    return assignments


@router.get("/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment_by_id(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.require_scope("assignments:read"))
):
    """Get assignment by ID."""
    from app.models.models import Assignment
    from sqlalchemy import select
    
    result = await db.execute(
        select(Assignment).where(Assignment.id == assignment_id)
    )
    assignment = result.scalar_one_or_none()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment {assignment_id} not found"
        )
    
    return assignment


@router.patch("/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment(
    assignment_id: int,
    update_data: AssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.require_scope("assignments:write"))
):
    """Update assignment details."""
    from app.models.models import Assignment
    from sqlalchemy import select
    
    result = await db.execute(
        select(Assignment).where(Assignment.id == assignment_id)
    )
    assignment = result.scalar_one_or_none()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment {assignment_id} not found"
        )
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(assignment, field, value)
    
    await db.commit()
    await db.refresh(assignment)
    
    logger.info(f"Updated assignment {assignment_id}")
    
    return assignment


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.require_scope("assignments:write"))
):
    """Delete an assignment."""
    from app.models.models import Assignment
    from sqlalchemy import select
    
    result = await db.execute(
        select(Assignment).where(Assignment.id == assignment_id)
    )
    assignment = result.scalar_one_or_none()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment {assignment_id} not found"
        )
    
    await db.delete(assignment)
    await db.commit()
    
    logger.info(f"Deleted assignment {assignment_id}")
    
    return None


@router.post("/bulk/create", response_model=BulkAssignmentOperationResponse, status_code=status.HTTP_201_CREATED)
async def create_bulk_assignments(
    bulk_data: BulkAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.require_scope("assignments:write"))
):
    """Create multiple assignments using true bulk operations."""
    # Use bulk operations service
    result = await bulk_operations_service.create_bulk_assignments(db, bulk_data.assignments)
    
    return BulkAssignmentOperationResponse(
        successful=result["successful"],
        failed=result["failed"],
        total_successful=len(result["successful"]),
        total_failed=len(result["failed"])
    )


@router.patch("/bulk/update", response_model=BulkAssignmentOperationResponse)
async def update_bulk_assignments(
    bulk_data: BulkAssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.require_scope("assignments:write"))
):
    """Update multiple assignments using true bulk operations."""
    # Convert Pydantic model to dictionary
    updates_dict = bulk_data.updates.dict(exclude_unset=True)
    
    # Use bulk operations service
    result = await bulk_operations_service.update_bulk_assignments(
        db, bulk_data.assignment_ids, updates_dict
    )
    
    return BulkAssignmentOperationResponse(
        successful=result["successful"],
        failed=result["failed"],
        total_successful=len(result["successful"]),
        total_failed=len(result["failed"])
    )


@router.delete("/bulk/delete", response_model=BulkAssignmentOperationResponse)
async def delete_bulk_assignments(
    bulk_data: BulkAssignmentDelete,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.require_scope("assignments:write"))
):
    """Delete multiple assignments using true bulk operations."""
    # Use bulk operations service
    result = await bulk_operations_service.delete_bulk_assignments(
        db, bulk_data.assignment_ids
    )
    
    return BulkAssignmentOperationResponse(
        successful=result["successful"],
        failed=result["failed"],
        total_successful=len(result["successful"]),
        total_failed=len(result["failed"])
    )
