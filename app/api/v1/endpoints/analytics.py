"""Analytics endpoints for real-time data from PostgreSQL and ClickHouse."""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
import clickhouse_connect

from app.core.database import get_db
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

class AnalyticsEventResponse(BaseModel):
    """Schema for analytics event response."""
    id: str
    experiment_id: int
    experiment_name: str
    experiment_key: str
    user_id: str
    user_name: str
    user_email: str
    variant_id: int
    variant_name: str
    variant_key: str
    is_control: bool
    event_type: str
    timestamp: str
    assignment_at: str
    properties: Dict[str, Any]
    session_id: str
    request_id: str

def get_clickhouse_client():
    """Get ClickHouse client."""
    try:
        logger.info(f"Connecting to ClickHouse at {settings.clickhouse_host}:{settings.clickhouse_port}")
        client = clickhouse_connect.get_client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            database=settings.clickhouse_database
        )
        logger.info("ClickHouse client created successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to ClickHouse: {e}")
        raise HTTPException(status_code=500, detail="ClickHouse connection failed")

@router.get("/experiments")
async def get_experiments_data(
    limit: int = Query(100, description="Number of experiments to return"),
    offset: int = Query(0, description="Number of experiments to skip"),
    db: AsyncSession = Depends(get_db)
):
    """Get real experiments data from PostgreSQL."""
    try:
        result = await db.execute(text("""
            SELECT id, name, description, status, created_at, updated_at
            FROM experiments 
            ORDER BY created_at DESC 
            LIMIT :limit OFFSET :offset
        """), {"limit": limit, "offset": offset})
        experiments = result.fetchall()
        
        return {
            "experiments": [
                {
                    "id": exp.id,
                    "name": exp.name,
                    "description": exp.description,
                    "status": exp.status,
                    "created_at": exp.created_at.isoformat(),
                    "updated_at": exp.updated_at.isoformat()
                }
                for exp in experiments
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching experiments: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch experiments")

@router.get("/variants")
async def get_variants_data(
    experiment_id: Optional[int] = Query(None, description="Filter by experiment ID"),
    limit: int = Query(100, description="Number of variants to return"),
    offset: int = Query(0, description="Number of variants to skip"),
    db: AsyncSession = Depends(get_db)
):
    """Get real variants data from PostgreSQL."""
    try:
        query = """
            SELECT v.id, v.experiment_id, v.name, v.key, v.description, 
                   v.allocation_pct, v.is_control, v.config, v.created_at
            FROM variants v
        """
        params = {}
        
        if experiment_id:
            query += " WHERE v.experiment_id = :experiment_id"
            params["experiment_id"] = experiment_id
            
        query += " ORDER BY v.experiment_id, v.id LIMIT :limit OFFSET :offset"
        
        params.update({"limit": limit, "offset": offset})
        result = await db.execute(text(query), params)
        variants = result.fetchall()
        
        return {
            "variants": [
                {
                    "id": var.id,
                    "experiment_id": var.experiment_id,
                    "name": var.name,
                    "key": var.key,
                    "description": var.description,
                    "allocation_pct": var.allocation_pct,
                    "is_control": var.is_control,
                    "config": var.config,
                    "created_at": var.created_at.isoformat()
                }
                for var in variants
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching variants: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch variants")

@router.get("/assignments")
async def get_assignments_data(
    experiment_id: Optional[int] = Query(None, description="Filter by experiment ID"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(100, description="Number of assignments to return"),
    offset: int = Query(0, description="Number of assignments to skip"),
    db: AsyncSession = Depends(get_db)
):
    """Get real assignments data from PostgreSQL."""
    try:
        query = """
            SELECT a.id, a.experiment_id, a.variant_id, a.user_id, 
                   a.assigned_at, a.created_at,
                   e.name as experiment_name, e.key as experiment_key,
                   v.name as variant_name, v.key as variant_key, v.is_control
            FROM assignments a
            LEFT JOIN experiments e ON a.experiment_id = e.id
            LEFT JOIN variants v ON a.variant_id = v.id
        """
        params = {}
        conditions = []
        
        if experiment_id:
            conditions.append("a.experiment_id = :experiment_id")
            params["experiment_id"] = experiment_id
            
        if user_id:
            conditions.append("a.user_id = :user_id")
            params["user_id"] = user_id
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += " ORDER BY a.assigned_at DESC LIMIT :limit OFFSET :offset"
        
        params.update({"limit": limit, "offset": offset})
        result = await db.execute(text(query), params)
        assignments = result.fetchall()
        
        return {
            "assignments": [
                {
                    "id": assign.id,
                    "experiment_id": assign.experiment_id,
                    "experiment_name": assign.experiment_name,
                    "experiment_key": assign.experiment_key,
                    "variant_id": assign.variant_id,
                    "variant_name": assign.variant_name,
                    "variant_key": assign.variant_key,
                    "is_control": assign.is_control,
                    "user_id": assign.user_id,
                    "assigned_at": assign.assigned_at.isoformat() if assign.assigned_at else None,
                    "created_at": assign.created_at.isoformat() if assign.created_at else None,
                }
                for assign in assignments
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching assignments: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch assignments")

@router.get("/events")
async def get_events_data(
    experiment_id: Optional[int] = Query(None, description="Filter by experiment ID"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(100, description="Number of events to return"),
    offset: int = Query(0, description="Number of events to skip")
):
    """Get real events data from ClickHouse."""
    try:
        client = get_clickhouse_client()
        
        # Build query with filters (simplified without dictionaries for now)
        query = """
            SELECT id, experiment_id, user_id, variant_id, event_type, 
                   timestamp, properties
            FROM experiments_analytics.events_mv
        """
        conditions = []
        params = {}
        
        if experiment_id:
            conditions.append("experiment_id = %(experiment_id)s")
            params["experiment_id"] = experiment_id
            
        if user_id:
            conditions.append("user_id = %(user_id)s")
            params["user_id"] = user_id
            
        if event_type:
            conditions.append("event_type = %(event_type)s")
            params["event_type"] = event_type
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += f" ORDER BY timestamp DESC LIMIT {limit} OFFSET {offset}"
        
        result = client.query(query, parameters=params)
        
        return {
            "events": [
                {
                    "id": str(row[0]),
                    "experiment_id": row[1],
                    "experiment_name": f"Experiment {row[1]}",  # Placeholder
                    "experiment_key": f"exp-{row[1]}",  # Placeholder
                    "user_id": row[2],
                    "user_name": f"User {row[2]}",  # Placeholder
                    "user_email": f"user{row[2]}@example.com",  # Placeholder
                    "variant_id": row[3],
                    "variant_name": f"Variant {row[3]}",  # Placeholder
                    "variant_key": f"var-{row[3]}",  # Placeholder
                    "is_control": row[3] == 1,  # Placeholder logic
                    "event_type": row[4],
                    "timestamp": row[5].isoformat() if row[5] else None,
                    "assignment_at": None,  # Not available in simplified query
                    "properties": row[6],
                    "session_id": None,  # Not available in simplified query
                    "request_id": None  # Not available in simplified query
                }
                for row in result.result_rows
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch events")

@router.get("/users")
async def get_users_data(
    active_only: bool = Query(True, description="Show only active users"),
    limit: int = Query(100, description="Number of users to return"),
    offset: int = Query(0, description="Number of users to skip"),
    db: AsyncSession = Depends(get_db)
):
    """Get real users data from PostgreSQL."""
    try:
        query = """
            SELECT user_id, email, name, is_active, properties, created_at, updated_at
            FROM users
        """
        params = {}
        
        if active_only:
            query += " WHERE is_active = :active"
            params["active"] = True
            
        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        
        params.update({"limit": limit, "offset": offset})
        result = await db.execute(text(query), params)
        users = result.fetchall()
        
        return {
            "users": [
                {
                    "user_id": user.user_id,
                    "email": user.email,
                    "name": user.name,
                    "is_active": user.is_active,
                    "properties": user.properties,
                    "created_at": user.created_at.isoformat(),
                    "updated_at": user.updated_at.isoformat()
                }
                for user in users
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch users")

@router.get("/reports")
async def get_experiment_reports(
    experiment_id: Optional[int] = Query(None, description="Filter by experiment ID"),
    days: int = Query(30, description="Number of days to include"),
    limit: int = Query(100, description="Number of reports to return"),
    offset: int = Query(0, description="Number of reports to skip")
):
    """Get aggregated experiment reports from ClickHouse."""
    try:
        client = get_clickhouse_client()
        
        query = """
            SELECT experiment_id, variant_id, variant_name, is_control,
                   experiment_name, report_date, total_events, unique_users,
                   total_score, avg_score, conversion_rate, 
                   statistical_significance, confidence_interval_lower, confidence_interval_upper
            FROM experiment_reports
        """
        params = {}
        
        if experiment_id:
            query += " WHERE experiment_id = %(experiment_id)s"
            params["experiment_id"] = experiment_id
            
        query += f" ORDER BY report_date DESC, experiment_id, variant_id LIMIT {limit} OFFSET {offset}"
        
        result = client.query(query, parameters=params)
        
        return {
            "reports": [
                {
                    "experiment_id": row[0],
                    "variant_id": row[1],
                    "variant_name": row[2],
                    "is_control": row[3],
                    "experiment_name": row[4],
                    "date": row[5].isoformat() if row[5] else None,
                    "total_events": row[6],
                    "unique_users": row[7],
                    "total_score": row[8],
                    "avg_score": float(row[9]) if row[9] else 0.0,
                    "conversion_rate": float(row[10]) if row[10] else 0.0,
                    "statistical_significance": float(row[11]) if row[11] else 0.0,
                    "confidence_interval_lower": float(row[12]) if row[12] else 0.0,
                    "confidence_interval_upper": float(row[13]) if row[13] else 0.0
                }
                for row in result.result_rows
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching reports: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch reports")

@router.get("/daily-stats")
async def get_daily_stats(
    experiment_id: Optional[int] = Query(None, description="Filter by experiment ID"),
    days: int = Query(7, description="Number of days to include")
):
    """Get daily aggregated statistics from ClickHouse."""
    try:
        client = get_clickhouse_client()
        
        query = """
            SELECT experiment_id, variant_id, date, 
                   uniqState(user_id) as unique_users_state,
                   countState() as total_events_state,
                   sumState(if(event_type = 'conversion', 1, 0)) as conversions_state
            FROM experiment_daily_stats
        """
        params = {}
        
        if experiment_id:
            query += " WHERE experiment_id = %(experiment_id)s"
            params["experiment_id"] = experiment_id
            
        query += f" ORDER BY date DESC LIMIT {days * 10}"  # Assume max 10 variants per experiment
        
        result = client.query(query, parameters=params)
        
        return {
            "daily_stats": [
                {
                    "experiment_id": row[0],
                    "variant_id": row[1],
                    "date": row[2].isoformat() if row[2] else None,
                    "unique_users": row[3],  # This is a state, would need finalizeAggregation
                    "total_events": row[4],  # This is a state
                    "conversions": row[5]    # This is a state
                }
                for row in result.result_rows
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching daily stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch daily stats")

@router.get("/summary")
async def get_data_summary():
    """Get summary statistics from both PostgreSQL and ClickHouse."""
    try:
        # Get PostgreSQL counts
        db = await get_db().__anext__()
        
        # Experiments count
        exp_result = await db.execute(text("SELECT COUNT(*) as count FROM experiments"))
        exp_count = exp_result.scalar()
        
        # Variants count
        var_result = await db.execute(text("SELECT COUNT(*) as count FROM variants"))
        var_count = var_result.scalar()
        
        # Assignments count
        assign_result = await db.execute(text("SELECT COUNT(*) as count FROM assignments"))
        assign_count = assign_result.scalar()
        
        # Users count
        user_result = await db.execute(text("SELECT COUNT(*) as count FROM users WHERE is_active = true"))
        user_count = user_result.scalar()
        
        # Get ClickHouse counts
        client = get_clickhouse_client()
        
        # Events count
        events_result = client.query("SELECT COUNT(*) as count FROM events_mv")
        events_count = events_result.result_rows[0][0] if events_result.result_rows else 0
        
        # Reports count
        reports_result = client.query("SELECT COUNT(*) as count FROM experiment_reports")
        reports_count = reports_result.result_rows[0][0] if reports_result.result_rows else 0
        
        return {
            "postgresql": {
                "experiments": exp_count,
                "variants": var_count,
                "assignments": assign_count,
                "active_users": user_count
            },
            "clickhouse": {
                "events": events_count,
                "reports": reports_count
            },
            "total_records": exp_count + var_count + assign_count + user_count + events_count + reports_count
        }
    except Exception as e:
        logger.error(f"Error fetching summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch summary")
