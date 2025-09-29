"""Event schemas."""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class EventCreate(BaseModel):
    """Schema for creating an event."""
    
    experiment_id: int = Field(..., gt=0)
    user_id: str = Field(..., min_length=1, max_length=255)
    event_type: str = Field(..., min_length=1, max_length=50)
    properties: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[datetime] = None
    session_id: Optional[str] = Field(default=None, max_length=255)
    request_id: Optional[str] = Field(default=None, max_length=255)


class BatchEventCreate(BaseModel):
    """Schema for batch event creation."""
    
    events: List[EventCreate] = Field(..., min_length=1, max_length=1000)


class EventResponse(BaseModel):
    """Schema for event response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    experiment_id: int
    user_id: str
    variant_id: int
    variant_key: str
    event_type: str
    timestamp: datetime
    status: str


class BatchEventResponse(BaseModel):
    """Schema for batch event response."""
    
    recorded: int
    failed: int
    events: List[EventResponse]
    errors: List[Dict[str, Any]]


class EventUpdate(BaseModel):
    """Schema for updating an event."""
    
    event_type: Optional[str] = Field(default=None, min_length=1, max_length=50)
    properties: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = Field(default=None, max_length=255)
    request_id: Optional[str] = Field(default=None, max_length=255)


class EventListResponse(BaseModel):
    """Schema for event list response."""
    
    events: List[EventResponse]
    total: int
    page: int
    page_size: int
