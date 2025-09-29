"""API Token endpoints."""

import logging
import secrets
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.middleware.auth import auth
from app.schemas.api_tokens import (
    ApiTokenCreate,
    ApiTokenResponse,
    ApiTokenUpdate,
    ApiTokenListResponse,
)
from app.models.models import ApiToken

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=ApiTokenResponse, status_code=status.HTTP_201_CREATED)
async def create_api_token(
    token_data: ApiTokenCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(auth.verify_token)
):
    """Create a new API token."""
    try:
        # Generate a secure token
        token_value = f"sk-{secrets.token_urlsafe(32)}"
        
        # Create token
        api_token = ApiToken(
            token=token_value,
            name=token_data.name,
            description=token_data.description,
            expires_at=token_data.expires_at,
            scopes=token_data.scopes,
            rate_limit=token_data.rate_limit
        )
        db.add(api_token)
        await db.commit()
        await db.refresh(api_token)
        
        logger.info(f"Created API token {api_token.name}")
        
        return api_token
        
    except Exception as e:
        logger.error(f"Failed to create API token: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API token"
        )


@router.get("/{token_id}", response_model=ApiTokenResponse)
async def get_api_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """Get API token by ID."""
    result = await db.execute(
        select(ApiToken).where(ApiToken.id == token_id)
    )
    api_token = result.scalar_one_or_none()
    
    if not api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API token {token_id} not found"
        )
    
    return api_token


@router.get("/", response_model=ApiTokenListResponse)
async def list_api_tokens(
    is_active: Optional[bool] = Query(default=None),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """List API tokens with optional filtering."""
    query = select(ApiToken).limit(limit).offset(offset)
    
    if is_active is not None:
        query = query.where(ApiToken.is_active == is_active)
    
    # Get total count
    count_query = select(func.count(ApiToken.id))
    if is_active is not None:
        count_query = count_query.where(ApiToken.is_active == is_active)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get tokens
    result = await db.execute(query.order_by(ApiToken.created_at.desc()))
    tokens = result.scalars().all()
    
    return ApiTokenListResponse(
        tokens=tokens,
        total=total,
        page=offset // limit + 1,
        page_size=limit
    )


@router.patch("/{token_id}", response_model=ApiTokenResponse)
async def update_api_token(
    token_id: int,
    update_data: ApiTokenUpdate,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """Update API token details."""
    result = await db.execute(
        select(ApiToken).where(ApiToken.id == token_id)
    )
    api_token = result.scalar_one_or_none()
    
    if not api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API token {token_id} not found"
        )
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(api_token, field, value)
    
    await db.commit()
    await db.refresh(api_token)
    
    logger.info(f"Updated API token {api_token.name}")
    
    return api_token


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """Delete an API token."""
    result = await db.execute(
        select(ApiToken).where(ApiToken.id == token_id)
    )
    api_token = result.scalar_one_or_none()
    
    if not api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API token {token_id} not found"
        )
    
    await db.delete(api_token)
    await db.commit()
    
    logger.info(f"Deleted API token {api_token.name}")
    
    return None


@router.post("/{token_id}/regenerate", response_model=ApiTokenResponse)
async def regenerate_api_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """Regenerate an API token."""
    result = await db.execute(
        select(ApiToken).where(ApiToken.id == token_id)
    )
    api_token = result.scalar_one_or_none()
    
    if not api_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API token {token_id} not found"
        )
    
    # Generate new token
    new_token = f"sk-{secrets.token_urlsafe(32)}"
    api_token.token = new_token
    
    await db.commit()
    await db.refresh(api_token)
    
    logger.info(f"Regenerated API token {api_token.name}")
    
    return api_token
