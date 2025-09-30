"""User endpoints."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.middleware.auth import auth
from app.schemas.users import (
    UserCreate,
    UserResponse,
    UserUpdate,
    UserListResponse,
)
from app.models.models import User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.require_scope("users:write"))
):
    """Create a new user."""
    try:
        # Check if user already exists
        result = await db.execute(
            select(User).where(User.user_id == user_data.user_id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with ID '{user_data.user_id}' already exists"
            )
        
        # Check if email already exists (if provided)
        if user_data.email:
            email_result = await db.execute(
                select(User).where(User.email == user_data.email)
            )
            if email_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User with email '{user_data.email}' already exists"
                )
        
        # Create user
        user = User(
            user_id=user_data.user_id,
            email=user_data.email,
            name=user_data.name,
            properties=user_data.properties,
            is_active=user_data.is_active
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"Created user {user.user_id}")
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.require_scope("users:read"))
):
    """Get user by ID."""
    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )
    
    return user


@router.get("/", response_model=UserListResponse)
async def list_users(
    is_active: Optional[bool] = Query(default=None),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.require_scope("users:read"))
):
    """List users with optional filtering."""
    query = select(User).limit(limit).offset(offset)
    
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    
    # Get total count
    count_query = select(func.count(User.user_id))
    if is_active is not None:
        count_query = count_query.where(User.is_active == is_active)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get users
    result = await db.execute(query.order_by(User.created_at.desc()))
    users = result.scalars().all()
    
    return UserListResponse(
        users=users,
        total=total,
        page=offset // limit + 1,
        page_size=limit
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    update_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.require_scope("users:write"))
):
    """Update user details."""
    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )
    
    # Check if email already exists (if being updated)
    if update_data.email and update_data.email != user.email:
        email_result = await db.execute(
            select(User).where(User.email == update_data.email)
        )
        if email_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with email '{update_data.email}' already exists"
            )
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    
    logger.info(f"Updated user {user_id}")
    
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    hard_delete: bool = Query(default=False, description="Permanently delete user"),
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.require_scope("users:write"))
):
    """Delete a user."""
    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )
    
    if hard_delete:
        # Hard delete - this will cascade to assignments, events, etc.
        await db.delete(user)
        await db.commit()
        logger.info(f"Hard deleted user {user_id}")
    else:
        # Soft delete by setting is_active to False
        user.is_active = False
        await db.commit()
        logger.info(f"Soft deleted user {user_id}")
    
    return None
