"""API timing middleware."""

import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import settings
from app.core.metrics import metrics

logger = logging.getLogger(__name__)


class TimingMiddleware(BaseHTTPMiddleware):
    """Middleware to track API response times."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.enabled = settings.enable_timing_middleware
        self.slow_threshold_ms = settings.slow_api_threshold_ms
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add timing information to responses."""
        if not self.enabled:
            return await call_next(request)
        
        # Skip timing for health checks and metrics
        if request.url.path in ["/health", "/ready", "/metrics"]:
            return await call_next(request)
        
        start_time = time.perf_counter()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Add timing header
        response.headers["X-Response-Time-ms"] = f"{duration_ms:.2f}"
        
        # Log slow requests
        if duration_ms > self.slow_threshold_ms:
            logger.warning(
                f"Slow API call: {request.method} {request.url.path} "
                f"took {duration_ms:.2f}ms (threshold: {self.slow_threshold_ms}ms)"
            )
        
        # Record metrics
        if metrics:
            metrics.record_request_duration(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms
            )
        
        # Log request
        logger.info(
            f"{request.method} {request.url.path} "
            f"status={response.status_code} "
            f"duration={duration_ms:.2f}ms"
        )
        
        return response