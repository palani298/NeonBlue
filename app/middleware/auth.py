"""Authentication middleware."""

from typing import Optional, List
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import logging

from app.core.config import settings
from app.core.database import get_db
from app.core.cache import get_redis
from app.models.models import ApiToken

logger = logging.getLogger(__name__)

security = HTTPBearer()


class AuthMiddleware:
    """Bearer token authentication middleware."""
    
    def __init__(self):
        self.static_tokens = set(settings.bearer_tokens)
        self.cache_prefix = "auth:token:"
        self.cache_ttl = 300  # 5 minutes
    
    async def verify_token(
        self,
        credentials: HTTPAuthorizationCredentials = Security(security),
        db: AsyncSession = Depends(get_db),
        redis = Depends(get_redis)
    ) -> dict:
        """Verify bearer token."""
        token = credentials.credentials
        
        # Check static tokens first (for development/testing)
        if token in self.static_tokens:
            return {
                "token": token,
                "source": "static",
                "scopes": ["*"]
            }
        
        # Check Redis cache
        cache_key = f"{self.cache_prefix}{token}"
        cached = await redis.get(cache_key)
        if cached:
            import json
            token_data = json.loads(cached)
            logger.debug(f"Token {token[:8]}... found in cache")
            return token_data
        
        # Check database
        result = await db.execute(
            select(ApiToken).where(
                ApiToken.token == token,
                ApiToken.is_active == True
            )
        )
        api_token = result.scalar_one_or_none()
        
        if not api_token:
            logger.warning(f"Invalid token attempt: {token[:8]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check expiration
        if api_token.expires_at and api_token.expires_at < datetime.now(timezone.utc):
            logger.warning(f"Expired token used: {token[:8]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Update last used timestamp
        api_token.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        
        # Prepare token data
        token_data = {
            "token": token,
            "source": "database",
            "scopes": api_token.scopes or [],
            "rate_limit": api_token.rate_limit,
            "name": api_token.name
        }
        
        # Cache token data
        import json
        await redis.setex(
            cache_key,
            self.cache_ttl,
            json.dumps(token_data)
        )
        
        logger.info(f"Token {api_token.name} authenticated successfully")
        return token_data
    
    def require_scope(self, required_scope: str):
        """Decorator to require specific scope."""
        async def scope_checker(
            token_data: dict = Depends(self.verify_token)
        ):
            scopes = token_data.get("scopes", [])
            if "*" not in scopes and required_scope not in scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Token does not have required scope: {required_scope}"
                )
            return token_data
        return scope_checker


# Global auth instance
auth = AuthMiddleware()