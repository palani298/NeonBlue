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