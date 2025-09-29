"""Assignment schemas."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class AssignmentResponse(BaseModel):
    """Schema for assignment response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    experiment_id: int
    experiment_key: Optional[str]
    user_id: str
    variant_id: int
    variant_key: Optional[str]
    variant_name: Optional[str]
    is_control: bool
    assigned_at: Optional[datetime]
    enrolled_at: Optional[datetime]
    version: int
    source: str


class BulkAssignmentRequest(BaseModel):
    """Schema for bulk assignment request."""
    
    user_id: str = Field(..., min_length=1, max_length=255)
    experiment_ids: List[int] = Field(..., min_length=1, max_length=100)


class BulkAssignmentResponse(BaseModel):
    """Schema for bulk assignment response."""
    
    user_id: str
    assignments: Dict[int, AssignmentResponse]


class AssignmentUpdate(BaseModel):
    """Schema for updating an assignment."""
    
    variant_id: Optional[int] = Field(default=None, gt=0)
    source: Optional[str] = Field(default=None, max_length=50)
    context: Optional[Dict[str, Any]] = None


class AssignmentListResponse(BaseModel):
    """Schema for assignment list response."""
    
    assignments: List[AssignmentResponse]
    total: int
    page: int
    page_size: int


class BulkAssignmentCreate(BaseModel):
    """Schema for creating multiple assignments."""
    
    assignments: List[Dict[str, Any]] = Field(..., min_length=1, max_length=1000)


class BulkAssignmentUpdate(BaseModel):
    """Schema for updating multiple assignments."""
    
    assignment_ids: List[int] = Field(..., min_length=1, max_length=1000)
    updates: AssignmentUpdate


class BulkAssignmentDelete(BaseModel):
    """Schema for deleting multiple assignments."""
    
    assignment_ids: List[int] = Field(..., min_length=1, max_length=1000)


class BulkAssignmentOperationResponse(BaseModel):
    """Schema for bulk assignment operation response."""
    
    successful: List[Dict[str, Any]]
    failed: List[Dict[str, Any]]
    total_successful: int
    total_failed: int
