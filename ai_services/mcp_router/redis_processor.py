# Redis Processor - Cache and session data with cache-aside pattern
"""
Redis processor for MCP system that implements cache-aside pattern:

1. Check Redis cache first before database operations
2. Store frequently accessed data in Redis
3. Implement data deduplication
4. Provide real-time metrics aggregation
5. Support cache invalidation patterns

This processor helps other processors by providing a fast cache layer
and reducing database load through intelligent caching strategies.
"""

import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import traceback

import redis.asyncio as redis
from structlog import get_logger

from ..core.config import config

logger = get_logger(__name__)


class RedisProcessor:
    """
    Redis processor for cache and session data with cache-aside pattern
    
    Handles:
    - High-frequency data caching
    - Session data storage
    - Real-time metrics aggregation
    - Cache-aside pattern for other processors
    - Data deduplication
    """
    
    def __init__(self):
        self.name = "Redis"
        self.redis_client = None
        self.connection_pool = None
        self.initialized = False
        
        # Cache TTL strategies for different data types
        self.cache_ttl_strategies = {
            'experiment': 86400,      # 24 hours
            'assignment': 3600,       # 1 hour
            'user_data': 1800,        # 30 minutes
            'event_metrics': 900,     # 15 minutes
            'analytics': 7200,        # 2 hours
            'session': 1800,          # 30 minutes
            'processed': 86400,       # 24 hours (deduplication)
            'default': 3600           # 1 hour
        }
        
        self.stats = {
            'processed_count': 0,
            'error_count': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'last_processed': None,
            'last_error': None
        }
    
    async def initialize(self):
        """Initialize Redis connection pool"""
        try:
            # Create Redis connection pool
            self.connection_pool = redis.ConnectionPool.from_url(
                config.redis_url,
                max_connections=10,
                decode_responses=True
            )
            
            self.redis_client = redis.Redis(connection_pool=self.connection_pool)
            
            # Test connection
            await self.redis_client.ping()
            
            self.initialized = True
            logger.info("Redis processor initialized", redis_url=config.redis_url)
            
        except Exception as e:
            logger.error("Failed to initialize Redis processor", error=str(e))
            raise
    
    async def process_data(self, data: Dict[str, Any], routing_task: Dict[str, Any]) -> Dict[str, Any]:
        """Process data for Redis storage with cache-aside pattern"""
        try:
            classification = routing_task.get('classification', {})
            data_type = classification.get('data_type', 'unknown')
            
            # Generate cache key based on data type and content
            cache_key = self._generate_cache_key(data, data_type, routing_task)
            
            # Check if data already exists in cache (deduplication)
            if await self._is_duplicate(cache_key, routing_task):
                self.stats['cache_hits'] += 1
                logger.info("Data already processed - cache hit", 
                           cache_key=cache_key,
                           routing_id=routing_task.get('routing_id'))
                return {'status': 'cached', 'cache_key': cache_key}
            
            # Transform data for Redis storage
            transformed_data = self._transform_for_redis(data, routing_task)
            
            # Store data based on type
            if data_type == 'experiment':
                result = await self._store_experiment_cache(transformed_data, cache_key)
            elif data_type == 'assignment':
                result = await self._store_assignment_cache(transformed_data, cache_key)
            elif data_type == 'user_data':
                result = await self._store_user_cache(transformed_data, cache_key)
            elif data_type == 'event':
                result = await self._store_event_metrics(transformed_data, cache_key)
            elif data_type == 'analytics':
                result = await self._store_analytics_cache(transformed_data, cache_key)
            else:
                result = await self._store_generic_cache(transformed_data, cache_key, data_type)
            
            # Mark as processed for deduplication
            await self._mark_processed(cache_key, routing_task)
            
            self.stats['processed_count'] += 1
            self.stats['last_processed'] = datetime.utcnow().isoformat()
            
            logger.info("Redis processing completed",
                       data_type=data_type,
                       cache_key=cache_key,
                       routing_id=routing_task.get('routing_id'))
            
            return result
            
        except Exception as e:
            error_msg = f"Redis processing failed: {str(e)}"
            self.stats['error_count'] += 1
            self.stats['last_error'] = error_msg
            logger.error("Redis processing failed",
                        error=str(e),
                        routing_id=routing_task.get('routing_id'),
                        traceback=traceback.format_exc())
            raise
    
    def _generate_cache_key(self, data: Dict[str, Any], data_type: str, routing_task: Dict[str, Any]) -> str:
        """Generate cache key based on data type and content"""
        routing_id = routing_task.get('routing_id', 'unknown')
        
        if data_type == 'experiment':
            experiment_id = data.get('experiment_id', 'unknown')
            return f"experiment:{experiment_id}"
            
        elif data_type == 'assignment':
            experiment_id = data.get('experiment_id', 'unknown')
            user_id = data.get('user_id', 'unknown')
            return f"assignment:{experiment_id}:{user_id}"
            
        elif data_type == 'user_data':
            user_id = data.get('user_id', 'unknown')
            return f"user:{user_id}:profile"
            
        elif data_type == 'event':
            experiment_id = data.get('experiment_id', 'unknown')
            variant_id = data.get('variant_id', 'unknown')
            event_type = data.get('event_type', 'unknown')
            hour = datetime.utcnow().strftime("%Y%m%d%H")
            return f"metrics:{experiment_id}:{variant_id}:{event_type}:{hour}"
            
        elif data_type == 'analytics':
            experiment_id = data.get('experiment_id', 'unknown')
            date = datetime.utcnow().strftime("%Y%m%d")
            return f"analytics:{experiment_id}:{date}"
            
        else:
            # Generic key for unknown types
            return f"generic:{data_type}:{routing_id}"
    
    def _transform_for_redis(self, data: Dict[str, Any], routing_task: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data for Redis storage"""
        return {
            **data,
            'mcp_routing_id': routing_task.get('routing_id'),
            'mcp_processed_at': datetime.utcnow().isoformat(),
            'mcp_classification': routing_task.get('classification', {}),
            'mcp_source': routing_task.get('source', 'unknown'),
            'cached_at': datetime.utcnow().isoformat()
        }
    
    async def _is_duplicate(self, cache_key: str, routing_task: Dict[str, Any]) -> bool:
        """Check if data is already processed (deduplication)"""
        routing_id = routing_task.get('routing_id')
        if not routing_id:
            return False
            
        duplicate_key = f"processed:{routing_id}"
        return await self.redis_client.exists(duplicate_key) > 0
    
    async def _mark_processed(self, cache_key: str, routing_task: Dict[str, Any]):
        """Mark data as processed for deduplication"""
        routing_id = routing_task.get('routing_id')
        if routing_id:
            duplicate_key = f"processed:{routing_id}"
            ttl = self.cache_ttl_strategies['processed']
            await self.redis_client.setex(duplicate_key, ttl, "true")
    
    async def _store_experiment_cache(self, data: Dict[str, Any], cache_key: str) -> Dict[str, Any]:
        """Store experiment data in Redis cache"""
        ttl = self.cache_ttl_strategies['experiment']
        
        # Store experiment data
        await self.redis_client.setex(cache_key, ttl, json.dumps(data))
        
        # Store experiment variants separately for quick access
        if 'variants' in data:
            variants_key = f"{cache_key}:variants"
            await self.redis_client.setex(variants_key, ttl, json.dumps(data['variants']))
        
        return {
            'cache_key': cache_key,
            'ttl': ttl,
            'stored_at': datetime.utcnow().isoformat(),
            'type': 'experiment'
        }
    
    async def _store_assignment_cache(self, data: Dict[str, Any], cache_key: str) -> Dict[str, Any]:
        """Store assignment data in Redis cache"""
        ttl = self.cache_ttl_strategies['assignment']
        
        # Store assignment data
        await self.redis_client.setex(cache_key, ttl, json.dumps(data))
        
        # Store user's experiment list for quick lookup
        user_id = data.get('user_id')
        if user_id:
            user_experiments_key = f"user:{user_id}:experiments"
            experiment_id = data.get('experiment_id')
            
            # Add to set of user's experiments
            await self.redis_client.sadd(user_experiments_key, str(experiment_id))
            await self.redis_client.expire(user_experiments_key, ttl)
        
        return {
            'cache_key': cache_key,
            'ttl': ttl,
            'stored_at': datetime.utcnow().isoformat(),
            'type': 'assignment'
        }
    
    async def _store_user_cache(self, data: Dict[str, Any], cache_key: str) -> Dict[str, Any]:
        """Store user data in Redis cache"""
        ttl = self.cache_ttl_strategies['user_data']
        
        # Store user profile data
        await self.redis_client.setex(cache_key, ttl, json.dumps(data))
        
        # Store user segments for quick filtering
        if 'segment' in data:
            segment_key = f"segment:{data['segment']}:users"
            user_id = data.get('user_id')
            await self.redis_client.sadd(segment_key, str(user_id))
            await self.redis_client.expire(segment_key, ttl)
        
        return {
            'cache_key': cache_key,
            'ttl': ttl,
            'stored_at': datetime.utcnow().isoformat(),
            'type': 'user_data'
        }
    
    async def _store_event_metrics(self, data: Dict[str, Any], cache_key: str) -> Dict[str, Any]:
        """Store event metrics in Redis with aggregation"""
        ttl = self.cache_ttl_strategies['event_metrics']
        
        # Increment counter for metrics
        current_count = await self.redis_client.incr(cache_key)
        await self.redis_client.expire(cache_key, ttl)
        
        # Store detailed event data with TTL
        event_data_key = f"{cache_key}:data"
        await self.redis_client.setex(event_data_key, ttl, json.dumps(data))
        
        # Update daily unique users using HyperLogLog
        day = datetime.utcnow().strftime("%Y%m%d")
        unique_key = f"unique:{cache_key.split(':')[1]}:{day}"
        user_id = data.get('user_id', 'anonymous')
        await self.redis_client.pfadd(unique_key, user_id)
        await self.redis_client.expire(unique_key, 172800)  # 2 days
        
        return {
            'cache_key': cache_key,
            'count': current_count,
            'ttl': ttl,
            'stored_at': datetime.utcnow().isoformat(),
            'type': 'event_metrics'
        }
    
    async def _store_analytics_cache(self, data: Dict[str, Any], cache_key: str) -> Dict[str, Any]:
        """Store analytics data in Redis cache"""
        ttl = self.cache_ttl_strategies['analytics']
        
        # Store analytics data
        await self.redis_client.setex(cache_key, ttl, json.dumps(data))
        
        # Store aggregated metrics separately
        if 'metrics' in data:
            metrics_key = f"{cache_key}:metrics"
            await self.redis_client.setex(metrics_key, ttl, json.dumps(data['metrics']))
        
        return {
            'cache_key': cache_key,
            'ttl': ttl,
            'stored_at': datetime.utcnow().isoformat(),
            'type': 'analytics'
        }
    
    async def _store_generic_cache(self, data: Dict[str, Any], cache_key: str, data_type: str) -> Dict[str, Any]:
        """Store generic data in Redis cache"""
        ttl = self.cache_ttl_strategies.get(data_type, self.cache_ttl_strategies['default'])
        
        await self.redis_client.setex(cache_key, ttl, json.dumps(data))
        
        return {
            'cache_key': cache_key,
            'ttl': ttl,
            'stored_at': datetime.utcnow().isoformat(),
            'type': 'generic'
        }
    
    async def get_cached_data(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get data from cache (for cache-aside pattern)"""
        try:
            data = await self.redis_client.get(cache_key)
            if data:
                self.stats['cache_hits'] += 1
                return json.loads(data)
            else:
                self.stats['cache_misses'] += 1
                return None
        except Exception as e:
            logger.error(f"Failed to get cached data for key {cache_key}", error=str(e))
            self.stats['cache_misses'] += 1
            return None
    
    async def invalidate_cache(self, pattern: str) -> int:
        """Invalidate cache keys matching pattern"""
        try:
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                deleted = await self.redis_client.delete(*keys)
                logger.info(f"Invalidated {deleted} cache keys matching pattern: {pattern}")
                return deleted
            
            return 0
        except Exception as e:
            logger.error(f"Failed to invalidate cache pattern {pattern}", error=str(e))
            return 0
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Redis processor health"""
        try:
            if not self.redis_client:
                return {'status': 'unhealthy', 'error': 'No Redis client'}
            
            # Test with ping
            await self.redis_client.ping()
            
            # Get Redis info
            info = await self.redis_client.info()
            
            return {
                'status': 'healthy',
                'initialized': self.initialized,
                'stats': self.stats.copy(),
                'redis_info': {
                    'version': info.get('redis_version'),
                    'used_memory': info.get('used_memory_human'),
                    'connected_clients': info.get('connected_clients'),
                    'total_commands_processed': info.get('total_commands_processed')
                }
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'stats': self.stats.copy()
            }
    
    async def shutdown(self):
        """Clean shutdown of Redis processor"""
        if self.connection_pool:
            try:
                await self.connection_pool.disconnect()
            except Exception as e:
                logger.warning(f"Error closing Redis connection pool", error=str(e))
        
        logger.info("Redis processor shutdown complete")
