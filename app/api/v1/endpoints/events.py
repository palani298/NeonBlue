"""Event endpoints."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth import auth
from app.schemas.events import (
    EventCreate,
    EventResponse,
    EventUpdate,
    BatchEventCreate,
    BatchEventResponse
)
from app.services.events_v2 import event_service_v2 as event_service
from app.services.events import outbox_processor
from app.services.bulk_operations import bulk_operations_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=EventResponse, status_code=status.HTTP_202_ACCEPTED)
async def record_event(
    event_data: EventCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.require_scope("events:write"))
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
    token_data: dict = Depends(auth.require_scope("events:write"))
):
    """
    Record multiple events using true bulk operations.
    
    Useful for reducing API calls when tracking multiple events.
    """
    try:
        events_data = [event.model_dump() for event in batch_data.events]
        result = await bulk_operations_service.record_bulk_events(db, events_data)
        
        # Process outbox in background
        background_tasks.add_task(process_outbox_background, db)
        
        return BatchEventResponse(
            recorded=result["recorded"],
            failed=result["failed"],
            total=len(batch_data.events),
            events=result["events"]
        )
        
    except Exception as e:
        logger.error(f"Failed to record batch events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record batch events"
        )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.require_scope("events:read"))
):
    """Get event by ID."""
    from app.models.models import Event
    from sqlalchemy import select
    
    result = await db.execute(
        select(Event).where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found"
        )
    
    return event


@router.get("/", response_model=List[EventResponse])
async def list_events(
    experiment_id: Optional[int] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.require_scope("events:read"))
):
    """List events with optional filtering."""
    from app.models.models import Event
    from sqlalchemy import select
    
    query = select(Event).limit(limit).offset(offset)
    
    if experiment_id:
        query = query.where(Event.experiment_id == experiment_id)
    if user_id:
        query = query.where(Event.user_id == user_id)
    if event_type:
        query = query.where(Event.event_type == event_type)
    
    result = await db.execute(query.order_by(Event.timestamp.desc()))
    events = result.scalars().all()
    
    return events


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str,
    update_data: EventUpdate,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.require_scope("events:write"))
):
    """Update event details."""
    from app.models.models import Event
    from sqlalchemy import select
    
    result = await db.execute(
        select(Event).where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found"
        )
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(event, field, value)
    
    await db.commit()
    await db.refresh(event)
    
    logger.info(f"Updated event {event_id}")
    
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.require_scope("events:write"))
):
    """Delete an event."""
    from app.models.models import Event
    from sqlalchemy import select
    
    result = await db.execute(
        select(Event).where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found"
        )
    
    await db.delete(event)
    await db.commit()
    
    logger.info(f"Deleted event {event_id}")
    
    return None


async def process_outbox_background(db: AsyncSession):
    """Background task to process outbox events."""
    try:
        await outbox_processor.process_outbox(db)
    except Exception as e:
        logger.error(f"Failed to process outbox: {e}")
