"""Event endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth import auth
from app.schemas.events import (
    EventCreate,
    EventResponse,
    BatchEventCreate,
    BatchEventResponse
)
from app.services.events import event_service, outbox_processor

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=EventResponse, status_code=status.HTTP_202_ACCEPTED)
async def record_event(
    event_data: EventCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """
    Record an event for an experiment.
    
    Events are recorded with the transactional outbox pattern for CDC.
    Only events that occur after assignment are counted in metrics.
    """
    try:
        result = await event_service.record_event(
            db=db,
            experiment_id=event_data.experiment_id,
            user_id=event_data.user_id,
            event_type=event_data.event_type,
            properties=event_data.properties,
            timestamp=event_data.timestamp,
            session_id=event_data.session_id,
            request_id=event_data.request_id
        )
        
        # Process outbox in background
        background_tasks.add_task(process_outbox_background, db)
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to record event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record event"
        )


@router.post("/batch", response_model=BatchEventResponse, status_code=status.HTTP_202_ACCEPTED)
async def record_batch_events(
    batch_data: BatchEventCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """
    Record multiple events in a batch.
    
    Useful for reducing API calls when tracking multiple events.
    """
    try:
        events_data = [event.model_dump() for event in batch_data.events]
        result = await event_service.record_batch_events(db, events_data)
        
        # Process outbox in background
        background_tasks.add_task(process_outbox_background, db)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to record batch events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record batch events"
        )


async def process_outbox_background(db: AsyncSession):
    """Background task to process outbox events."""
    try:
        await outbox_processor.process_outbox(db)
    except Exception as e:
        logger.error(f"Failed to process outbox: {e}")
