"""Data management endpoints for PostgreSQL and ClickHouse."""

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.middleware.auth import auth
from app.schemas.data_management import (
    DataCleanupRequest,
    DataCleanupResponse,
    DataStatsResponse,
    RetentionPolicy
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats", response_model=DataStatsResponse)
async def get_data_stats(
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """Get data statistics for both PostgreSQL and ClickHouse."""
    try:
        # PostgreSQL stats
        pg_stats = await _get_postgresql_stats(db)
        
        # ClickHouse stats (would need ClickHouse client)
        ch_stats = await _get_clickhouse_stats()
        
        return DataStatsResponse(
            postgresql=pg_stats,
            clickhouse=ch_stats,
            generated_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Failed to get data stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get data statistics"
        )


@router.post("/cleanup", response_model=DataCleanupResponse)
async def cleanup_old_data(
    request: DataCleanupRequest,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """Clean up old data based on retention policies."""
    try:
        results = {}
        
        # Clean up PostgreSQL events
        if request.cleanup_events:
            events_cleaned = await _cleanup_postgresql_events(
                db, request.events_retention_days
            )
            results["postgresql_events"] = events_cleaned
        
        # Clean up outbox events
        if request.cleanup_outbox:
            outbox_cleaned = await _cleanup_postgresql_outbox(
                db, request.outbox_retention_days
            )
            results["postgresql_outbox"] = outbox_cleaned
        
        # Clean up ClickHouse data (if needed)
        if request.cleanup_clickhouse:
            ch_cleaned = await _cleanup_clickhouse_data(request.clickhouse_retention_days)
            results["clickhouse"] = ch_cleaned
        
        return DataCleanupResponse(
            cleaned_records=results,
            cleanup_date=datetime.utcnow(),
            retention_policy=request
        )
        
    except Exception as e:
        logger.error(f"Failed to cleanup data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup data"
        )


@router.get("/retention-policies", response_model=List[RetentionPolicy])
async def get_retention_policies(
    token_data: dict = Depends(auth.verify_token)
):
    """Get current data retention policies."""
    return [
        RetentionPolicy(
            table_name="events",
            retention_days=90,
            description="Events older than 90 days are archived to ClickHouse only"
        ),
        RetentionPolicy(
            table_name="outbox_events",
            retention_days=30,
            description="Outbox events older than 30 days are deleted (CDC processed)"
        ),
        RetentionPolicy(
            table_name="assignments",
            retention_days=365,
            description="Assignments are kept for 1 year for analysis"
        ),
        RetentionPolicy(
            table_name="experiments",
            retention_days=730,
            description="Experiments are kept for 2 years for historical analysis"
        )
    ]


async def _get_postgresql_stats(db: AsyncSession) -> dict:
    """Get PostgreSQL data statistics."""
    try:
        stats = {}
        
        # Get table counts
        tables = ["experiments", "variants", "assignments", "events", "outbox_events", "users"]
        
        for table in tables:
            try:
                result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                stats[f"{table}_count"] = count
            except Exception as e:
                logger.warning(f"Could not get count for table {table}: {e}")
                stats[f"{table}_count"] = 0
        
        # Get date ranges for events
        try:
            result = await db.execute(text("""
                SELECT 
                    MIN(timestamp) as earliest_event,
                    MAX(timestamp) as latest_event
                FROM events
            """))
            date_range = result.fetchone()
            if date_range:
                stats["events_date_range"] = {
                    "earliest": date_range.earliest_event.isoformat() if date_range.earliest_event else None,
                    "latest": date_range.latest_event.isoformat() if date_range.latest_event else None
                }
        except Exception as e:
            logger.warning(f"Could not get events date range: {e}")
            stats["events_date_range"] = {"earliest": None, "latest": None}
        
        return stats
    except Exception as e:
        logger.error(f"Error getting PostgreSQL stats: {e}")
        return {"error": str(e)}


async def _get_clickhouse_stats() -> dict:
    """Get ClickHouse data statistics."""
    try:
        # This would connect to ClickHouse and get stats
        # For now, return mock data
        return {
            "events_count": 0,
            "assignments_count": 0,
            "disk_usage_gb": 0,
            "compression_ratio": 0,
            "status": "not_connected"
        }
    except Exception as e:
        logger.warning(f"ClickHouse stats not available: {e}")
        return {
            "events_count": 0,
            "assignments_count": 0,
            "disk_usage_gb": 0,
            "compression_ratio": 0,
            "status": "error",
            "error": str(e)
        }


async def _cleanup_postgresql_events(db: AsyncSession, retention_days: int) -> dict:
    """Clean up old events from PostgreSQL."""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        # Count records to be deleted
        result = await db.execute(
            text("SELECT COUNT(*) FROM events WHERE timestamp < :cutoff"),
            {"cutoff": cutoff_date}
        )
        count_before = result.scalar()
        
        # Delete old events
        result = await db.execute(
            text("DELETE FROM events WHERE timestamp < :cutoff"),
            {"cutoff": cutoff_date}
        )
        
        await db.commit()
        
        return {
            "table": "events",
            "records_deleted": result.rowcount,
            "cutoff_date": cutoff_date.isoformat(),
            "retention_days": retention_days
        }
    except Exception as e:
        logger.error(f"Error cleaning up events: {e}")
        await db.rollback()
        return {
            "table": "events",
            "records_deleted": 0,
            "error": str(e),
            "retention_days": retention_days
        }


async def _cleanup_postgresql_outbox(db: AsyncSession, retention_days: int) -> dict:
    """Clean up old outbox events from PostgreSQL."""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        # Delete old outbox events
        result = await db.execute(
            text("DELETE FROM outbox_events WHERE created_at < :cutoff"),
            {"cutoff": cutoff_date}
        )
        
        await db.commit()
        
        return {
            "table": "outbox_events",
            "records_deleted": result.rowcount,
            "cutoff_date": cutoff_date.isoformat(),
            "retention_days": retention_days
        }
    except Exception as e:
        logger.error(f"Error cleaning up outbox events: {e}")
        await db.rollback()
        return {
            "table": "outbox_events",
            "records_deleted": 0,
            "error": str(e),
            "retention_days": retention_days
        }


async def _cleanup_clickhouse_data(retention_days: int) -> dict:
    """Clean up old data from ClickHouse."""
    # This would implement ClickHouse cleanup
    # For now, return mock data
    return {
        "table": "events_processed",
        "records_deleted": 0,
        "retention_days": retention_days
    }
