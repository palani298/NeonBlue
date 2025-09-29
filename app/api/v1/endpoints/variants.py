"""Variant endpoints."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.middleware.auth import auth
from app.schemas.experiments import (
    VariantCreate,
    VariantResponse,
    VariantUpdate,
)
from app.models.models import Variant, Experiment

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=VariantResponse, status_code=status.HTTP_201_CREATED)
async def create_variant(
    variant_data: VariantCreate,
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """Create a new variant for an experiment."""
    try:
        # Check if experiment exists
        result = await db.execute(
            select(Experiment).where(Experiment.id == experiment_id)
        )
        experiment = result.scalar_one_or_none()
        
        if not experiment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Experiment {experiment_id} not found"
            )
        
        # Check if variant key already exists for this experiment
        existing = await db.execute(
            select(Variant).where(
                Variant.experiment_id == experiment_id,
                Variant.key == variant_data.key
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Variant with key '{variant_data.key}' already exists for this experiment"
            )
        
        # Create variant
        variant = Variant(
            experiment_id=experiment_id,
            key=variant_data.key,
            name=variant_data.name,
            description=variant_data.description,
            allocation_pct=variant_data.allocation_pct,
            is_control=variant_data.is_control,
            config=variant_data.config
        )
        db.add(variant)
        await db.commit()
        await db.refresh(variant)
        
        logger.info(f"Created variant {variant.key} for experiment {experiment_id}")
        
        return variant
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create variant: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create variant"
        )


@router.get("/{variant_id}", response_model=VariantResponse)
async def get_variant(
    variant_id: int,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """Get variant by ID."""
    result = await db.execute(
        select(Variant).where(Variant.id == variant_id)
    )
    variant = result.scalar_one_or_none()
    
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant {variant_id} not found"
        )
    
    return variant


@router.get("/", response_model=List[VariantResponse])
async def list_variants(
    experiment_id: Optional[int] = Query(default=None),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """List variants with optional filtering by experiment."""
    query = select(Variant).limit(limit).offset(offset)
    
    if experiment_id:
        query = query.where(Variant.experiment_id == experiment_id)
    
    result = await db.execute(query.order_by(Variant.created_at.desc()))
    variants = result.scalars().all()
    
    return variants


@router.patch("/{variant_id}", response_model=VariantResponse)
async def update_variant(
    variant_id: int,
    update_data: VariantUpdate,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """Update variant details."""
    result = await db.execute(
        select(Variant).where(Variant.id == variant_id)
    )
    variant = result.scalar_one_or_none()
    
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant {variant_id} not found"
        )
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(variant, field, value)
    
    await db.commit()
    await db.refresh(variant)
    
    logger.info(f"Updated variant {variant.key}")
    
    return variant


@router.delete("/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_variant(
    variant_id: int,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """Delete a variant."""
    result = await db.execute(
        select(Variant).where(Variant.id == variant_id)
    )
    variant = result.scalar_one_or_none()
    
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant {variant_id} not found"
        )
    
    # Check if this is the only variant for the experiment
    count_result = await db.execute(
        select(func.count(Variant.id)).where(Variant.experiment_id == variant.experiment_id)
    )
    variant_count = count_result.scalar()
    
    if variant_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the last variant of an experiment"
        )
    
    await db.delete(variant)
    await db.commit()
    
    logger.info(f"Deleted variant {variant.key}")
    
    return None
