"""Experiment schemas."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator


class VariantCreate(BaseModel):
    """Schema for creating a variant."""
    
    key: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    allocation_pct: int = Field(..., ge=0, le=100)
    is_control: bool = Field(default=False)
    config: Dict[str, Any] = Field(default_factory=dict)


class VariantResponse(BaseModel):
    """Schema for variant response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    experiment_id: int
    key: str
    name: str
    description: Optional[str]
    allocation_pct: int
    is_control: bool
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ExperimentCreate(BaseModel):
    """Schema for creating an experiment."""
    
    key: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    variants: List[VariantCreate] = Field(..., min_length=2)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("variants")
    @classmethod
    def validate_variants(cls, v: List[VariantCreate]) -> List[VariantCreate]:
        """Validate variants configuration."""
        # Check total allocation
        total_allocation = sum(variant.allocation_pct for variant in v)
        if total_allocation != 100:
            raise ValueError(f"Total allocation must be 100%, got {total_allocation}%")
        
        # Check for single control
        controls = [variant for variant in v if variant.is_control]
        if len(controls) != 1:
            raise ValueError(f"Exactly one control variant required, got {len(controls)}")
        
        # Check for unique keys
        keys = [variant.key for variant in v]
        if len(keys) != len(set(keys)):
            raise ValueError("Variant keys must be unique")
        
        return v
    
    @field_validator("ends_at")
    @classmethod
    def validate_dates(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate experiment dates."""
        if v and "starts_at" in info.data:
            starts_at = info.data["starts_at"]
            if starts_at and v <= starts_at:
                raise ValueError("End date must be after start date")
        return v


class ExperimentResponse(BaseModel):
    """Schema for experiment response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    key: str
    name: str
    description: Optional[str]
    status: str
    seed: str
    version: int
    config: Dict[str, Any]
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    variants: List[VariantResponse]


class ExperimentUpdate(BaseModel):
    """Schema for updating an experiment."""
    
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    config: Optional[Dict[str, Any]] = None
