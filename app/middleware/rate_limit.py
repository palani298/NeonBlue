"""Rate limiting middleware."""

import time
import hashlib
import logging
from typing import Optional, Tuple
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.core.cache import redis_client

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token bucket rate limiting middleware."""
    
    def __init__(self, app):
        super().__init__(app)
        self.enabled = settings.rate_limit_enabled
        self.default_limit = settings.rate_limit_requests
        self.window_seconds = settings.rate_limit_period
    
    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting."""
        if not self.enabled:
            return await call_next(request)
        
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/ready", "/metrics"]:
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Get rate limit for this client
        rate_limit = await self._get_rate_limit(request)
        
        # Check rate limit
        allowed, retry_after = await self._check_rate_limit(client_id, rate_limit)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for {client_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(rate_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + retry_after)
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = await self._get_remaining(client_id, rate_limit)
        response.headers["X-RateLimit-Limit"] = str(rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + self.window_seconds)
        
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Try to get from bearer token first
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return f"token:{hashlib.sha256(token.encode()).hexdigest()[:16]}"
        
        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    
    async def _get_rate_limit(self, request: Request) -> int:
        """Get rate limit for this request."""
        # Check if token has custom rate limit
        if hasattr(request.state, "token_data"):
            token_rate_limit = request.state.token_data.get("rate_limit")
            if token_rate_limit:
                return token_rate_limit
        
        return self.default_limit
    
    async def _check_rate_limit(
        self,
        client_id: str,
        limit: int
    ) -> Tuple[bool, Optional[int]]:
        """Check if request is within rate limit using token bucket."""
        now = int(time.time())
        key = f"rate_limit:{client_id}:{now // self.window_seconds}"
        
        try:
            # Increment counter
            current = await redis_client.incr(key)
            
            # Set expiry on first request
            if current == 1:
                await redis_client.expire(key, self.window_seconds + 1)
            
            # Check limit
            if current > limit:
                retry_after = self.window_seconds - (now % self.window_seconds)
                return False, retry_after
            
            return True, None
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow request if Redis is down
            return True, None
    
    async def _get_remaining(self, client_id: str, limit: int) -> int:
        """Get remaining requests in current window."""
        now = int(time.time())
        key = f"rate_limit:{client_id}:{now // self.window_seconds}"
        
        try:
            current = await redis_client.get(key)
            if current:
                return max(0, limit - int(current))
            return limit
        except:
            return limit


class RetryMiddleware(BaseHTTPMiddleware):
    """Middleware to handle retries with exponential backoff."""
    
    def __init__(self, app):
        super().__init__(app)
        self.max_retries = 3
        self.backoff_factor = 2
    
    async def dispatch(self, request: Request, call_next):
        """Handle retries for failed requests."""
        # Only retry on specific status codes
        retryable_status_codes = {502, 503, 504}
        
        attempt = 0
        last_exception = None
        
        while attempt < self.max_retries:
            try:
                response = await call_next(request)
                
                # Check if we should retry
                if response.status_code not in retryable_status_codes:
                    return response
                
                # Log retry attempt
                attempt += 1
                if attempt < self.max_retries:
                    wait_time = self.backoff_factor ** attempt
                    logger.warning(
                        f"Retrying request {request.url.path} "
                        f"(attempt {attempt}/{self.max_retries}) "
                        f"after {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                last_exception = e
                attempt += 1
                if attempt < self.max_retries:
                    wait_time = self.backoff_factor ** attempt
                    logger.warning(
                        f"Request failed with error: {e}. "
                        f"Retrying (attempt {attempt}/{self.max_retries}) "
                        f"after {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
        
        # All retries exhausted
        if last_exception:
            raise last_exception
        
        return response