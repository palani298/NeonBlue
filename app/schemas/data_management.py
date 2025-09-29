"""Schemas for data management operations."""

from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class DataStatsResponse(BaseModel):
    """Schema for data statistics response."""
    
    postgresql: Dict[str, Any]
    clickhouse: Dict[str, Any]
    generated_at: datetime


class RetentionPolicy(BaseModel):
    """Schema for data retention policy."""
    
    table_name: str
    retention_days: int
    description: str


class DataCleanupRequest(BaseModel):
    """Schema for data cleanup request."""
    
    cleanup_events: bool = Field(default=True, description="Clean up old events")
    cleanup_outbox: bool = Field(default=True, description="Clean up old outbox events")
    cleanup_clickhouse: bool = Field(default=False, description="Clean up old ClickHouse data")
    
    events_retention_days: int = Field(default=90, ge=1, le=365, description="Events retention in days")
    outbox_retention_days: int = Field(default=30, ge=1, le=90, description="Outbox retention in days")
    clickhouse_retention_days: int = Field(default=365, ge=30, le=1095, description="ClickHouse retention in days")
    
    dry_run: bool = Field(default=False, description="Preview what would be deleted without actually deleting")


class DataCleanupResponse(BaseModel):
    """Schema for data cleanup response."""
    
    cleaned_records: Dict[str, Any]
    cleanup_date: datetime
    retention_policy: DataCleanupRequest


class DataArchivalRequest(BaseModel):
    """Schema for data archival request."""
    
    table_name: str
    archive_before: datetime
    destination: str = Field(default="clickhouse", description="Archive destination")
    compress: bool = Field(default=True, description="Compress archived data")


class DataArchivalResponse(BaseModel):
    """Schema for data archival response."""
    
    table_name: str
    records_archived: int
    archive_location: str
    archive_date: datetime
    compressed: bool
