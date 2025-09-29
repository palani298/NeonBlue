"""Results endpoints."""

import logging
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth import auth
from app.services.analytics_v2 import analytics_service_v2 as analytics_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/experiments/{experiment_id}/results")
async def get_experiment_results(
    experiment_id: int,
    start_date: Optional[datetime] = Query(
        default=None,
        description="Start date for analysis (ISO format)"
    ),
    end_date: Optional[datetime] = Query(
        default=None,
        description="End date for analysis (ISO format)"
    ),
    event_type: Optional[List[str]] = Query(
        default=None,
        description="Event types to analyze"
    ),
    granularity: str = Query(
        default="day",
        regex="^(realtime|hour|day)$",
        description="Time granularity for results"
    ),
    metrics: Optional[List[str]] = Query(
        default=None,
        description="Metrics to calculate"
    ),
    include_ci: bool = Query(
        default=True,
        description="Include confidence intervals"
    ),
    min_sample: int = Query(
        default=100,
        description="Minimum sample size for reporting"
    ),
    db: AsyncSession = Depends(get_db),
    token_data: dict = Depends(auth.verify_token)
):
    """
    Get experiment performance results with flexible analysis options.
    
    This endpoint provides:
    - Conversion rates with confidence intervals
    - Statistical significance calculations
    - Time series data at various granularities
    - Lift vs control calculations
    
    Results use PostgreSQL for recent data (hot path) and are prepared
    for ClickHouse integration for historical data (cold path).
    """
    try:
        results = await analytics_service.get_experiment_results(
            db=db,
            experiment_id=experiment_id,
            start_date=start_date,
            end_date=end_date,
            event_types=event_type,
            granularity=granularity,
            metrics=metrics,
            include_ci=include_ci,
            min_sample=min_sample
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to get experiment results: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get experiment results"
        )
