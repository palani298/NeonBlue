"""Redis cache connection and utilities."""

import json
import logging
from typing import Optional, Any, Dict, List
import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create Redis connection pool
redis_pool = ConnectionPool.from_url(
    str(settings.redis_url),
    max_connections=settings.redis_pool_size,
    decode_responses=settings.redis_decode_responses,
)

# Create Redis client
redis_client = redis.Redis(connection_pool=redis_pool)


async def get_redis():
    """Dependency to get Redis client."""
    return redis_client


class CacheManager:
    """Cache management utilities."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.default_ttl = 3600  # 1 hour
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value) if isinstance(value, str) else value
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache."""
        try:
            ttl = ttl or self.default_ttl
            value_str = json.dumps(value) if not isinstance(value, str) else value
            await self.redis.setex(key, ttl, value_str)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def mget(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache."""
        try:
            values = await self.redis.mget(keys)
            result = {}
            for key, value in zip(keys, values):
                if value:
                    result[key] = json.loads(value) if isinstance(value, str) else value
            return result
        except Exception as e:
            logger.error(f"Cache mget error: {e}")
            return {}
    
    async def mset(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple values in cache."""
        try:
            # Convert values to JSON strings
            str_mapping = {
                k: json.dumps(v) if not isinstance(v, str) else v
                for k, v in mapping.items()
            }
            
            # Use pipeline for atomic operation
            async with self.redis.pipeline() as pipe:
                for key, value in str_mapping.items():
                    pipe.setex(key, ttl or self.default_ttl, value)
                await pipe.execute()
            return True
        except Exception as e:
            logger.error(f"Cache mset error: {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter in cache."""
        try:
            return await self.redis.incrby(key, amount)
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return None
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on key."""
        try:
            await self.redis.expire(key, ttl)
            return True
        except Exception as e:
            logger.error(f"Cache expire error for key {key}: {e}")
            return False
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern."""
        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                await self.redis.delete(*keys)
            
            return len(keys)
        except Exception as e:
            logger.error(f"Cache invalidate pattern error for {pattern}: {e}")
            return 0


# Global cache manager instance
cache_manager = CacheManager(redis_client)


async def init_cache():
    """Initialize cache connection."""
    try:
        await redis_client.ping()
        logger.info("Redis cache connected successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise


async def close_cache():
    """Close cache connection."""
    await redis_client.close()
    await redis_pool.disconnect()
    logger.info("Redis cache connection closed")
