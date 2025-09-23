"""Experiment endpoints."""

import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.middleware.auth import auth
from app.schemas.experiments import (
    ExperimentCreate,
    ExperimentResponse,
    ExperimentUpdate
)
from app.models.models import Experiment, Variant, ExperimentStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    experiment_data: ExperimentCreate,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """Create a new experiment with variants."""
    try:
        # Check if experiment key already exists
        result = await db.execute(
            select(Experiment).where(Experiment.key == experiment_data.key)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Experiment with key '{experiment_data.key}' already exists"
            )
        
        # Create experiment
        experiment = Experiment(
            key=experiment_data.key,
            name=experiment_data.name,
            description=experiment_data.description,
            seed=str(uuid.uuid4()),  # Generate unique seed for hashing
            status=ExperimentStatus.DRAFT,
            starts_at=experiment_data.starts_at,
            ends_at=experiment_data.ends_at,
            config=experiment_data.config
        )
        db.add(experiment)
        
        # Create variants
        for variant_data in experiment_data.variants:
            variant = Variant(
                experiment=experiment,
                key=variant_data.key,
                name=variant_data.name,
                description=variant_data.description,
                allocation_pct=variant_data.allocation_pct,
                is_control=variant_data.is_control,
                config=variant_data.config
            )
            db.add(variant)
        
        await db.commit()
        await db.refresh(experiment, ["variants"])
        
        logger.info(f"Created experiment {experiment.key} with {len(experiment.variants)} variants")
        
        return experiment
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create experiment: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create experiment"
        )


@router.get("/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """Get experiment by ID."""
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id)
    )
    experiment = result.scalar_one_or_none()
    
    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found"
        )
    
    # Load variants
    await db.refresh(experiment, ["variants"])
    
    return experiment


@router.get("/", response_model=List[ExperimentResponse])
async def list_experiments(
    status: Optional[ExperimentStatus] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """List experiments with optional filtering."""
    query = select(Experiment).limit(limit).offset(offset)
    
    if status:
        query = query.where(Experiment.status == status)
    
    result = await db.execute(query.order_by(Experiment.created_at.desc()))
    experiments = result.scalars().all()
    
    # Load variants for each experiment
    for experiment in experiments:
        await db.refresh(experiment, ["variants"])
    
    return experiments


@router.patch("/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    experiment_id: int,
    update_data: ExperimentUpdate,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """Update experiment details."""
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id)
    )
    experiment = result.scalar_one_or_none()
    
    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found"
        )
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(experiment, field, value)
    
    # Increment version if status changed to active
    if "status" in update_dict and update_dict["status"] == ExperimentStatus.ACTIVE:
        experiment.version += 1
    
    await db.commit()
    await db.refresh(experiment, ["variants"])
    
    logger.info(f"Updated experiment {experiment.key}")
    
    return experiment


@router.post("/{experiment_id}/activate", response_model=ExperimentResponse)
async def activate_experiment(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """Activate an experiment."""
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id)
    )
    experiment = result.scalar_one_or_none()
    
    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found"
        )
    
    if experiment.status == ExperimentStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Experiment is already active"
        )
    
    experiment.status = ExperimentStatus.ACTIVE
    experiment.version += 1
    
    await db.commit()
    await db.refresh(experiment, ["variants"])
    
    logger.info(f"Activated experiment {experiment.key}")
    
    return experiment


@router.post("/{experiment_id}/pause", response_model=ExperimentResponse)
async def pause_experiment(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """Pause an active experiment."""
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id)
    )
    experiment = result.scalar_one_or_none()
    
    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found"
        )
    
    if experiment.status != ExperimentStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only active experiments can be paused"
        )
    
    experiment.status = ExperimentStatus.PAUSED
    
    await db.commit()
    await db.refresh(experiment, ["variants"])
    
    logger.info(f"Paused experiment {experiment.key}")
    
    return experiment
