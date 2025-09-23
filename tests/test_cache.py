"""Tests for Redis caching functionality."""

import pytest
import json
from app.core.cache import cache_manager, redis_client


class TestCache:
    """Test Redis cache operations."""
    
    @pytest.mark.asyncio
    async def test_cache_set_get(self, clean_redis):
        """Test basic cache set and get operations."""
        key = "test_key"
        value = {"data": "test_value", "number": 42}
        
        # Set value
        success = await cache_manager.set(key, value, ttl=60)
        assert success is True
        
        # Get value
        retrieved = await cache_manager.get(key)
        assert retrieved == value
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, clean_redis):
        """Test cache TTL expiration."""
        import asyncio
        
        key = "expiring_key"
        value = "test_value"
        
        # Set with 1 second TTL
        await cache_manager.set(key, value, ttl=1)
        
        # Value should exist immediately
        assert await cache_manager.get(key) == value
        
        # Wait for expiration
        await asyncio.sleep(1.5)
        
        # Value should be gone
        assert await cache_manager.get(key) is None
    
    @pytest.mark.asyncio
    async def test_cache_delete(self, clean_redis):
        """Test cache deletion."""
        key = "delete_key"
        value = "test_value"
        
        # Set value
        await cache_manager.set(key, value)
        assert await cache_manager.get(key) == value
        
        # Delete value
        success = await cache_manager.delete(key)
        assert success is True
        
        # Value should be gone
        assert await cache_manager.get(key) is None
    
    @pytest.mark.asyncio
    async def test_cache_mget_mset(self, clean_redis):
        """Test batch get/set operations."""
        mapping = {
            "key1": {"value": 1},
            "key2": {"value": 2},
            "key3": {"value": 3}
        }
        
        # Batch set
        success = await cache_manager.mset(mapping, ttl=60)
        assert success is True
        
        # Batch get
        keys = list(mapping.keys())
        results = await cache_manager.mget(keys)
        
        assert len(results) == 3
        for key, value in mapping.items():
            assert results[key] == value
    
    @pytest.mark.asyncio
    async def test_cache_increment(self, clean_redis):
        """Test atomic increment operation."""
        key = "counter"
        
        # First increment (creates key)
        result = await cache_manager.increment(key)
        assert result == 1
        
        # Multiple increments
        await cache_manager.increment(key, 5)
        await cache_manager.increment(key, 3)
        
        # Check final value
        value = await redis_client.get(key)
        assert int(value) == 9
    
    @pytest.mark.asyncio
    async def test_cache_invalidate_pattern(self, clean_redis):
        """Test pattern-based cache invalidation."""
        # Set multiple keys with pattern
        await cache_manager.set("experiment:1:assignment:user1", "value1")
        await cache_manager.set("experiment:1:assignment:user2", "value2")
        await cache_manager.set("experiment:2:assignment:user1", "value3")
        await cache_manager.set("other:key", "value4")
        
        # Invalidate experiment 1 assignments
        count = await cache_manager.invalidate_pattern("experiment:1:assignment:*")
        assert count == 2
        
        # Check what remains
        assert await cache_manager.get("experiment:1:assignment:user1") is None
        assert await cache_manager.get("experiment:1:assignment:user2") is None
        assert await cache_manager.get("experiment:2:assignment:user1") == "value3"
        assert await cache_manager.get("other:key") == "value4"
    
    @pytest.mark.asyncio
    async def test_cache_api_versioning(self, clean_redis):
        """Test that cache keys include API version for isolation."""
        # This tests the pattern used in the actual service
        api_version = "v1"
        experiment_id = 1
        user_id = "test_user"
        
        # Create versioned cache key (as done in assignment service)
        cache_key = f"assignment:{api_version}:exp:{experiment_id}:user:{user_id}"
        
        # Set value with version
        await cache_manager.set(cache_key, {"variant": "control"})
        
        # Verify retrieval with correct version
        value = await cache_manager.get(cache_key)
        assert value == {"variant": "control"}
        
        # Different version should not find the value
        v2_cache_key = f"assignment:v2:exp:{experiment_id}:user:{user_id}"
        value = await cache_manager.get(v2_cache_key)
        assert value is None