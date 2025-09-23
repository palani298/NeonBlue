"""Event service using stored procedures."""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.stored_procedures import stored_procedure_dao
from app.core.metrics import metrics

logger = logging.getLogger(__name__)


class EventServiceV2:
    """Service for managing events using stored procedures."""
    
    async def record_event(
        self,
        db: AsyncSession,
        experiment_id: int,
        user_id: str,
        event_type: str,
        properties: Optional[Dict] = None,
        value: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Record a single event using stored procedure.
        
        The stored procedure handles:
        - Checking for existing assignment
        - Creating outbox event for CDC
        - Atomic transaction
        
        Args:
            db: Database session
            experiment_id: Experiment ID
            user_id: User ID
            event_type: Type of event
            properties: Event properties
            value: Numeric value (for revenue events)
        """
        try:
            # Record event using stored procedure
            result = await stored_procedure_dao.record_event(
                db=db,
                experiment_id=experiment_id,
                user_id=user_id,
                event_type=event_type,
                properties=properties,
                value=value
            )
            
            # Commit transaction
            await db.commit()
            
            # Update metrics
            metrics.event_counter.labels(
                experiment_id=str(experiment_id),
                event_type=event_type,
                variant=result["variant_key"]
            ).inc()
            
            # Return formatted response
            return {
                "id": result["id"],
                "experiment_id": experiment_id,
                "user_id": user_id,
                "event_type": event_type,
                "variant_key": result["variant_key"],
                "properties": properties,
                "value": value,
                "created_at": result["created_at"].isoformat() if result["created_at"] else None
            }
            
        except Exception as e:
            await db.rollback()
            
            # Check if it's a missing assignment error
            if "No assignment found" in str(e):
                logger.warning(f"No assignment for user {user_id} in experiment {experiment_id}")
                raise ValueError(f"User {user_id} not assigned to experiment {experiment_id}")
            
            logger.error(f"Error recording event: {e}")
            raise
    
    async def record_batch_events(
        self,
        db: AsyncSession,
        events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Record multiple events in batch using stored procedure.
        
        Args:
            db: Database session
            events: List of event dictionaries
        
        Returns:
            Summary of batch operation
        """
        try:
            # Validate and format events
            formatted_events = []
            for event in events:
                formatted_events.append({
                    "experiment_id": event["experiment_id"],
                    "user_id": event["user_id"],
                    "event_type": event.get("event_type", "custom"),
                    "properties": event.get("properties", {}),
                    "value": event.get("value")
                })
            
            # Record batch using stored procedure
            result = await stored_procedure_dao.record_batch_events(
                db=db,
                events=formatted_events
            )
            
            # Commit transaction
            await db.commit()
            
            # Update metrics
            metrics.batch_event_counter.labels(
                success=str(result["success_count"]),
                error=str(result["error_count"])
            ).inc()
            
            # Log errors if any
            if result["error_count"] > 0:
                logger.warning(f"Batch event recording had {result['error_count']} errors: {result['errors']}")
            
            return {
                "success_count": result["success_count"],
                "error_count": result["error_count"],
                "total_count": len(events),
                "errors": result["errors"] if result["error_count"] > 0 else []
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error recording batch events: {e}")
            raise
    
    async def get_user_events(
        self,
        db: AsyncSession,
        user_id: str,
        experiment_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get events for a user.
        
        Note: This uses direct query since it's a simple read operation.
        Could be converted to stored procedure if needed.
        """
        from sqlalchemy import select, desc
        from app.models.models import Event, Assignment, Variant
        
        try:
            query = (
                select(Event, Variant.key)
                .join(Assignment, Assignment.id == Event.assignment_id)
                .join(Variant, Variant.id == Assignment.variant_id)
                .where(Event.user_id == user_id)
                .order_by(desc(Event.created_at))
                .limit(limit)
            )
            
            if experiment_id:
                query = query.where(Event.experiment_id == experiment_id)
            
            result = await db.execute(query)
            
            events = []
            for row in result:
                event = row[0]
                variant_key = row[1]
                
                events.append({
                    "id": event.id,
                    "experiment_id": event.experiment_id,
                    "user_id": event.user_id,
                    "event_type": event.event_type,
                    "variant_key": variant_key,
                    "properties": event.properties,
                    "value": float(event.value) if event.value else None,
                    "created_at": event.created_at.isoformat()
                })
            
            return events
            
        except Exception as e:
            logger.error(f"Error getting user events: {e}")
            raise
    
    async def get_event_stats(
        self,
        db: AsyncSession,
        experiment_id: int,
        event_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get event statistics for an experiment.
        
        Uses the experiment stats stored procedure.
        """
        try:
            # Get overall stats
            stats = await stored_procedure_dao.get_experiment_stats(
                db=db,
                experiment_id=experiment_id
            )
            
            if not stats:
                return {
                    "experiment_id": experiment_id,
                    "total_events": 0,
                    "unique_users": 0,
                    "avg_events_per_user": 0
                }
            
            # If specific event type requested, get metrics for it
            if event_type:
                metrics = await stored_procedure_dao.get_experiment_metrics(
                    db=db,
                    experiment_id=experiment_id,
                    event_types=[event_type]
                )
                
                # Sum up metrics across variants
                total_events = sum(m["total_events"] for m in metrics)
                unique_users = len(set(m["unique_users"] for m in metrics))
                
                stats["event_type_stats"] = {
                    "event_type": event_type,
                    "total_events": total_events,
                    "unique_users": unique_users
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting event stats: {e}")
            raise


# Global service instance
event_service_v2 = EventServiceV2()