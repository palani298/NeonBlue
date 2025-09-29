"""User schemas."""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, EmailStr


class UserCreate(BaseModel):
    """Schema for creating a user."""
    
    user_id: str = Field(..., min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    name: Optional[str] = Field(default=None, max_length=255)
    properties: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = Field(default=True)


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    
    email: Optional[EmailStr] = None
    name: Optional[str] = Field(default=None, max_length=255)
    properties: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    """Schema for user response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    user_id: str
    email: Optional[str]
    name: Optional[str]
    properties: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    """Schema for user list response."""
    
    users: List[UserResponse]
    total: int
    page: int
    page_size: int
