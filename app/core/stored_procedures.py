"""Database access layer using stored procedures."""

import json
import logging
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
from decimal import Decimal

from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, DatabaseError

logger = logging.getLogger(__name__)


class StoredProcedureDAO:
    """Data Access Object for stored procedures."""
    
    # =====================================================
    # EXPERIMENT PROCEDURES
    # =====================================================
    
    @staticmethod
    async def create_experiment(
        db: AsyncSession,
        key: str,
        name: str,
        description: str,
        variants: List[Dict[str, Any]],
        status: str = "draft",
        starts_at: Optional[datetime] = None,
        ends_at: Optional[datetime] = None,
        config: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Create experiment using stored procedure."""
        try:
            result = await db.execute(
                text("""
                    SELECT * FROM create_experiment(
                        :key, :name, :description, :status,
                        :starts_at, :ends_at, :config::jsonb, :variants::jsonb
                    )
                """),
                {
                    "key": key,
                    "name": name,
                    "description": description,
                    "status": status,
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                    "config": json.dumps(config or {}),
                    "variants": json.dumps(variants)
                }
            )
            row = result.fetchone()
            
            if row:
                return {
                    "id": row.experiment_id,
                    "key": row.experiment_key,
                    "name": row.experiment_name,
                    "status": row.experiment_status,
                    "version": row.experiment_version,
                    "created_at": row.created_at
                }
            raise DatabaseError("Failed to create experiment")
            
        except IntegrityError as e:
            if "duplicate key" in str(e):
                raise ValueError(f"Experiment with key '{key}' already exists")
            raise
        except Exception as e:
            logger.error(f"Error creating experiment: {e}")
            raise
    
    @staticmethod
    async def get_experiment_with_variants(
        db: AsyncSession,
        experiment_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get experiment with variants using stored procedure."""
        try:
            result = await db.execute(
                text("SELECT * FROM get_experiment_with_variants(:experiment_id)"),
                {"experiment_id": experiment_id}
            )
            rows = result.fetchall()
            
            if not rows:
                return None
            
            # Group rows by experiment (all rows have same experiment data)
            first_row = rows[0]
            experiment = {
                "id": first_row.id,
                "key": first_row.key,
                "name": first_row.name,
                "description": first_row.description,
                "status": first_row.status.value if hasattr(first_row.status, 'value') else str(first_row.status),
                "seed": first_row.seed,
                "version": first_row.version,
                "config": first_row.config,
                "starts_at": first_row.starts_at,
                "ends_at": first_row.ends_at,
                "created_at": first_row.created_at,
                "updated_at": first_row.updated_at,
                "variants": []
            }
            
            # Add variants
            for row in rows:
                if row.variant_id:  # Only add rows that have variant data
                    variant = {
                        "id": row.variant_id,
                        "key": row.variant_key,
                        "name": row.variant_name,
                        "description": row.variant_description,
                        "allocation_pct": row.variant_allocation_pct,
                        "is_control": row.variant_is_control,
                        "config": row.variant_config,
                        "created_at": row.variant_created_at,
                        "updated_at": row.variant_updated_at
                    }
                    experiment["variants"].append(variant)
            
            return experiment
            
        except Exception as e:
            logger.error(f"Error getting experiment: {e}")
            raise
    
    @staticmethod
    async def list_active_experiments(
        db: AsyncSession,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List active experiments using stored procedure."""
        try:
            result = await db.execute(
                text("SELECT * FROM list_active_experiments(:limit, :offset)"),
                {"limit": limit, "offset": offset}
            )
            
            experiments = []
            for row in result:
                experiments.append({
                    "id": row.experiment_id,
                    "key": row.experiment_key,
                    "name": row.experiment_name,
                    "status": row.experiment_status,
                    "version": row.experiment_version,
                    "starts_at": row.starts_at,
                    "ends_at": row.ends_at,
                    "variant_count": row.variant_count
                })
            
            return experiments
            
        except Exception as e:
            logger.error(f"Error listing experiments: {e}")
            raise
    
    @staticmethod
    async def activate_experiment(
        db: AsyncSession,
        experiment_id: int
    ) -> Tuple[bool, str, Optional[int]]:
        """Activate experiment using stored procedure."""
        try:
            result = await db.execute(
                text("SELECT * FROM activate_experiment(:experiment_id)"),
                {"experiment_id": experiment_id}
            )
            row = result.fetchone()
            
            if row:
                return row.success, row.message, row.new_version
            return False, "Unknown error", None
            
        except Exception as e:
            logger.error(f"Error activating experiment: {e}")
            raise
    
    # =====================================================
    # ASSIGNMENT PROCEDURES
    # =====================================================
    
    @staticmethod
    async def get_assignment(
        db: AsyncSession,
        experiment_id: int,
        user_id: str,
        enroll: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get or create assignment using stored procedure."""
        try:
            result = await db.execute(
                text("SELECT * FROM get_or_create_assignment(:experiment_id, :user_id, :enroll)"),
                {
                    "experiment_id": experiment_id,
                    "user_id": user_id,
                    "enroll": enroll
                }
            )
            
            row = result.fetchone()
            if row:
                return {
                    "assignment_id": row.assignment_id,
                    "experiment_id": row.experiment_id,
                    "user_id": row.user_id,
                    "variant_id": row.variant_id,
                    "variant_key": row.variant_key,
                    "variant_name": row.variant_name,
                    "enrolled_at": row.enrolled_at,
                    "created_at": row.created_at
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting assignment: {e}")
            raise
    
    @staticmethod
    async def get_or_create_assignment(
        db: AsyncSession,
        experiment_id: int,
        user_id: str,
        enroll: bool = False
    ) -> Dict[str, Any]:
        """Get or create assignment using stored procedure."""
        try:
            result = await db.execute(
                text("""
                    SELECT * FROM get_or_create_assignment(
                        :experiment_id, :user_id, :enroll
                    )
                """),
                {
                    "experiment_id": experiment_id,
                    "user_id": user_id,
                    "enroll": enroll
                }
            )
            row = result.fetchone()
            
            if row:
                return {
                    "id": row.assignment_id,
                    "experiment_id": row.experiment_id,
                    "user_id": row.user_id,
                    "variant_id": row.variant_id,
                    "variant_key": row.variant_key,
                    "variant_name": row.variant_name,
                    "enrolled_at": row.enrolled_at,
                    "created_at": row.created_at
                }
            raise DatabaseError("Failed to get/create assignment")
            
        except Exception as e:
            logger.error(f"Error with assignment: {e}")
            raise
    
    @staticmethod
    async def get_bulk_assignments(
        db: AsyncSession,
        user_id: str,
        experiment_ids: List[int]
    ) -> List[Dict[str, Any]]:
        """Get bulk assignments using stored procedure."""
        try:
            result = await db.execute(
                text("SELECT * FROM get_bulk_assignments(:user_id, :experiment_ids)"),
                {
                    "user_id": user_id,
                    "experiment_ids": experiment_ids
                }
            )
            
            assignments = []
            for row in result:
                assignments.append({
                    "experiment_id": row.experiment_id,
                    "user_id": row.user_id,
                    "variant_id": row.variant_id,
                    "variant_key": row.variant_key,
                    "variant_name": row.variant_name,
                    "enrolled_at": row.enrolled_at,
                    "created_at": row.created_at
                })
            
            return assignments
            
        except Exception as e:
            logger.error(f"Error getting bulk assignments: {e}")
            raise
    
    # =====================================================
    # EVENT PROCEDURES
    # =====================================================
    
    @staticmethod
    async def record_event(
        db: AsyncSession,
        experiment_id: int,
        user_id: str,
        event_type: str,
        properties: Optional[Dict] = None,
        value: Optional[float] = None
    ) -> Dict[str, Any]:
        """Record event using stored procedure."""
        try:
            result = await db.execute(
                text("""
                    SELECT * FROM record_event(
                        :experiment_id, :user_id, :event_type, 
                        :properties, :value
                    )
                """),
                {
                    "experiment_id": experiment_id,
                    "user_id": user_id,
                    "event_type": event_type,
                    "properties": json.dumps(properties or {}),
                    "value": value
                }
            )
            row = result.fetchone()
            
            if row:
                return {
                    "id": row.event_id,
                    "experiment_id": row.experiment_id,
                    "user_id": row.user_id,
                    "variant_id": row.variant_id,
                    "event_type": row.event_type,
                    "timestamp": row.event_timestamp,
                    "status": row.status
                }
            raise DatabaseError("Failed to record event")
            
        except Exception as e:
            logger.error(f"Error recording event: {e}")
            raise
    
    @staticmethod
    async def record_batch_events(
        db: AsyncSession,
        events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Record batch events using stored procedure."""
        try:
            result = await db.execute(
                text("SELECT * FROM record_batch_events(:events::jsonb)"),
                {"events": json.dumps(events)}
            )
            row = result.fetchone()
            
            if row:
                return {
                    "success_count": row.success_count,
                    "error_count": row.error_count,
                    "errors": row.errors
                }
            raise DatabaseError("Failed to record batch events")
            
        except Exception as e:
            logger.error(f"Error recording batch events: {e}")
            raise
    
    # =====================================================
    # ANALYTICS PROCEDURES
    # =====================================================
    
    @staticmethod
    async def get_experiment_metrics(
        db: AsyncSession,
        experiment_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get experiment metrics using stored procedure."""
        try:
            result = await db.execute(
                text("""
                    SELECT * FROM get_experiment_metrics(
                        :experiment_id, :start_date, :end_date, :event_types
                    )
                """),
                {
                    "experiment_id": experiment_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "event_types": event_types
                }
            )
            
            metrics = []
            for row in result:
                metrics.append({
                    "variant_id": row.variant_id,
                    "variant_key": row.variant_key,
                    "variant_name": row.variant_name,
                    "is_control": row.is_control,
                    "unique_users": row.unique_users,
                    "total_events": row.total_events,
                    "conversion_count": row.conversion_count,
                    "conversion_rate": float(row.conversion_rate) if row.conversion_rate else 0.0,
                    "avg_value": float(row.avg_value) if row.avg_value else None
                })
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting experiment metrics: {e}")
            raise
    
    @staticmethod
    async def get_daily_metrics(
        db: AsyncSession,
        experiment_id: int,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get daily metrics using stored procedure."""
        try:
            result = await db.execute(
                text("SELECT * FROM get_daily_metrics(:experiment_id, :days)"),
                {"experiment_id": experiment_id, "days": days}
            )
            
            metrics = []
            for row in result:
                metrics.append({
                    "date": row.date.isoformat() if row.date else None,
                    "variant_key": row.variant_key,
                    "unique_users": row.unique_users,
                    "total_events": row.total_events,
                    "conversions": row.conversions
                })
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting daily metrics: {e}")
            raise
    
    @staticmethod
    async def get_funnel_metrics(
        db: AsyncSession,
        experiment_id: int,
        funnel_steps: List[str]
    ) -> List[Dict[str, Any]]:
        """Get funnel metrics using stored procedure."""
        try:
            result = await db.execute(
                text("SELECT * FROM get_funnel_metrics(:experiment_id, :funnel_steps)"),
                {"experiment_id": experiment_id, "funnel_steps": funnel_steps}
            )
            
            metrics = []
            for row in result:
                metrics.append({
                    "variant_key": row.variant_key,
                    "step": row.step,
                    "step_order": row.step_order,
                    "users_reached": row.users_reached,
                    "conversion_rate": float(row.conversion_rate) if row.conversion_rate else 0.0
                })
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting funnel metrics: {e}")
            raise
    
    @staticmethod
    async def get_experiment_stats(
        db: AsyncSession,
        experiment_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get experiment statistics using stored procedure."""
        try:
            result = await db.execute(
                text("SELECT * FROM get_experiment_stats(:experiment_id)"),
                {"experiment_id": experiment_id}
            )
            row = result.fetchone()
            
            if row:
                return {
                    "total_users": row.total_users,
                    "enrolled_users": row.enrolled_users,
                    "total_events": row.total_events,
                    "avg_events_per_user": float(row.avg_events_per_user) if row.avg_events_per_user else 0.0,
                    "days_running": row.days_running,
                    "status": row.status
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting experiment stats: {e}")
            raise
    
    # =====================================================
    # UTILITY PROCEDURES
    # =====================================================
    
    @staticmethod
    async def cleanup_old_events(
        db: AsyncSession,
        days_to_keep: int = 90
    ) -> Dict[str, int]:
        """Clean up old events using stored procedure."""
        try:
            result = await db.execute(
                text("SELECT * FROM cleanup_old_events(:days_to_keep)"),
                {"days_to_keep": days_to_keep}
            )
            row = result.fetchone()
            
            if row:
                return {
                    "deleted_events": row.deleted_events,
                    "deleted_outbox": row.deleted_outbox
                }
            return {"deleted_events": 0, "deleted_outbox": 0}
            
        except Exception as e:
            logger.error(f"Error cleaning up events: {e}")
            raise


# Global DAO instance
stored_procedure_dao = StoredProcedureDAO()
