"""API Token schemas."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ApiTokenCreate(BaseModel):
    """Schema for creating an API token."""
    
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    expires_at: Optional[datetime] = None
    scopes: List[str] = Field(default_factory=list)
    rate_limit: Optional[int] = Field(default=None, gt=0)


class ApiTokenUpdate(BaseModel):
    """Schema for updating an API token."""
    
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None
    scopes: Optional[List[str]] = None
    rate_limit: Optional[int] = Field(default=None, gt=0)


class ApiTokenResponse(BaseModel):
    """Schema for API token response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    token: str
    name: str
    description: Optional[str]
    is_active: bool
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    scopes: List[str]
    rate_limit: Optional[int]
    created_at: datetime
    updated_at: datetime


class ApiTokenListResponse(BaseModel):
    """Schema for API token list response."""
    
    tokens: List[ApiTokenResponse]
    total: int
    page: int
    page_size: int
