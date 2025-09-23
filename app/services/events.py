"""Event service with transactional outbox pattern."""

import json
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Event, Assignment, OutboxEvent, OutboxEventType
)
from app.core.cache import cache_manager
from app.services.assignment import assignment_service

logger = logging.getLogger(__name__)


class EventService:
    """Service for managing events with transactional outbox."""
    
    async def record_event(
        self,
        db: AsyncSession,
        experiment_id: int,
        user_id: str,
        event_type: str,
        properties: Dict[str, Any],
        timestamp: Optional[datetime] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record an event with transactional outbox pattern.
        
        Events are written to the events table and outbox atomically.
        Only events after assignment are valid for metrics.
        """
        # Use provided timestamp or current time
        event_timestamp = timestamp or datetime.now(timezone.utc)
        
        # Get assignment (this also creates it if needed)
        assignment = await assignment_service.get_assignment(
            db,
            experiment_id,
            user_id,
            enroll=(event_type == "exposure")  # Auto-enroll on exposure events
        )
        
        if not assignment:
            raise ValueError(f"Could not get assignment for user {user_id} in experiment {experiment_id}")
        
        # Create event with denormalized assignment timestamp
        event = Event(
            id=uuid.uuid4(),
            experiment_id=experiment_id,
            user_id=user_id,
            variant_id=assignment["variant_id"],
            event_type=event_type,
            timestamp=event_timestamp,
            assignment_at=datetime.fromisoformat(assignment["assigned_at"]),
            properties=properties,
            session_id=session_id,
            request_id=request_id
        )
        
        db.add(event)
        
        # Add to outbox for CDC (only events, not assignments)
        outbox_event = OutboxEvent(
            aggregate_id=str(event.id),
            aggregate_type="event",
            event_type=OutboxEventType.EVENT_CREATED,
            payload={
                "id": str(event.id),
                "experiment_id": experiment_id,
                "user_id": user_id,
                "variant_id": assignment["variant_id"],
                "variant_key": assignment["variant_key"],
                "event_type": event_type,
                "timestamp": event_timestamp.isoformat(),
                "assignment_at": assignment["assigned_at"],
                "properties": properties,
                "is_valid": event_timestamp >= datetime.fromisoformat(assignment["assigned_at"])
            }
        )
        db.add(outbox_event)
        
        # Commit transaction (event + outbox are atomic)
        await db.commit()
        
        # Update real-time metrics in Redis (fire and forget)
        await self._update_metrics(
            experiment_id,
            assignment["variant_id"],
            event_type,
            event_timestamp
        )
        
        return {
            "id": str(event.id),
            "experiment_id": experiment_id,
            "user_id": user_id,
            "variant_id": assignment["variant_id"],
            "variant_key": assignment["variant_key"],
            "event_type": event_type,
            "timestamp": event_timestamp.isoformat(),
            "status": "recorded"
        }
    
    async def record_batch_events(
        self,
        db: AsyncSession,
        events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Record multiple events in a single transaction."""
        recorded = []
        failed = []
        
        for event_data in events:
            try:
                result = await self.record_event(
                    db,
                    experiment_id=event_data["experiment_id"],
                    user_id=event_data["user_id"],
                    event_type=event_data["event_type"],
                    properties=event_data.get("properties", {}),
                    timestamp=event_data.get("timestamp"),
                    session_id=event_data.get("session_id"),
                    request_id=event_data.get("request_id")
                )
                recorded.append(result)
            except Exception as e:
                logger.error(f"Failed to record event: {e}")
                failed.append({
                    "event": event_data,
                    "error": str(e)
                })
        
        return {
            "recorded": len(recorded),
            "failed": len(failed),
            "events": recorded,
            "errors": failed
        }
    
    async def _update_metrics(
        self,
        experiment_id: int,
        variant_id: int,
        event_type: str,
        timestamp: datetime
    ):
        """Update real-time metrics in Redis."""
        try:
            # Hourly metric key
            hour = timestamp.strftime("%Y%m%d%H")
            metric_key = f"metrics:{experiment_id}:{variant_id}:{event_type}:{hour}"
            
            # Increment counter
            await cache_manager.increment(metric_key)
            
            # Set expiration (keep for 25 hours)
            await cache_manager.expire(metric_key, 90000)
            
            # Update daily unique users (using HyperLogLog)
            day = timestamp.strftime("%Y%m%d")
            unique_key = f"unique:{experiment_id}:{variant_id}:{event_type}:{day}"
            await cache_manager.redis.pfadd(unique_key, timestamp.isoformat())
            await cache_manager.expire(unique_key, 172800)  # 2 days
            
        except Exception as e:
            logger.error(f"Failed to update metrics: {e}")


class OutboxProcessor:
    """Process outbox events for CDC."""
    
    def __init__(self):
        self.batch_size = 100
        self.enabled = True
    
    async def process_outbox(self, db: AsyncSession) -> int:
        """Process pending outbox events."""
        if not self.enabled:
            return 0
        
        # Fetch unprocessed events
        result = await db.execute(
            select(OutboxEvent)
            .where(OutboxEvent.processed_at.is_(None))
            .order_by(OutboxEvent.created_at)
            .limit(self.batch_size)
            .with_for_update(skip_locked=True)  # Skip locked rows
        )
        events = result.scalars().all()
        
        if not events:
            return 0
        
        # Process events (in production, send to Kafka)
        processed_count = 0
        for event in events:
            try:
                await self._send_to_kafka(event)
                event.processed_at = datetime.now(timezone.utc)
                processed_count += 1
            except Exception as e:
                logger.error(f"Failed to process outbox event {event.id}: {e}")
        
        # Commit processed events
        await db.commit()
        
        logger.info(f"Processed {processed_count} outbox events")
        return processed_count
    
    async def _send_to_kafka(self, event: OutboxEvent):
        """Send event to Kafka (placeholder for actual implementation)."""
        # In production, use aiokafka to send to Kafka
        # For now, just log
        logger.debug(f"Would send to Kafka: {event.event_type} - {event.aggregate_id}")
        
        # Example Kafka producer code:
        # from aiokafka import AIOKafkaProducer
        # producer = AIOKafkaProducer(bootstrap_servers='localhost:9092')
        # await producer.send(
        #     topic=f"experiments.{event.aggregate_type}",
        #     key=event.aggregate_id.encode(),
        #     value=json.dumps(event.payload).encode()
        # )


# Global service instances
event_service = EventService()
outbox_processor = OutboxProcessor()
