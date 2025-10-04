#!/usr/bin/env python3
"""
MCP Redis Integration Demo

This script demonstrates how Redis helps with MCP dataflow through the cache-aside pattern.
It shows how each processor checks Redis first before hitting their respective databases.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any

# Mock data for demonstration
SAMPLE_DATA = {
    'experiment': {
        'experiment_id': 'exp_123',
        'name': 'Button Color Test',
        'hypothesis': 'Red buttons will increase conversions',
        'variants': [
            {'id': 1, 'name': 'Control', 'key': 'blue_button'},
            {'id': 2, 'name': 'Treatment', 'key': 'red_button'}
        ],
        'status': 'active'
    },
    'assignment': {
        'assignment_id': 'assign_456',
        'user_id': 'user_789',
        'experiment_id': 'exp_123',
        'variant_id': 2,
        'assigned_at': datetime.utcnow().isoformat()
    },
    'event': {
        'event_id': 'event_101',
        'user_id': 'user_789',
        'experiment_id': 'exp_123',
        'variant_id': 2,
        'event_type': 'conversion',
        'timestamp': datetime.utcnow().isoformat(),
        'properties': {'value': 29.99, 'product': 'premium_plan'}
    },
    'user_data': {
        'user_id': 'user_789',
        'profile': {'age': 28, 'location': 'San Francisco'},
        'segment': 'premium_users',
        'preferences': {'theme': 'dark', 'notifications': True}
    }
}


class MockRedisProcessor:
    """Mock Redis processor for demonstration"""
    
    def __init__(self):
        self.cache = {}
        self.stats = {'hits': 0, 'misses': 0}
    
    async def get(self, key: str) -> Any:
        """Get data from cache"""
        if key in self.cache:
            self.stats['hits'] += 1
            print(f"✅ CACHE HIT: {key}")
            return self.cache[key]
        else:
            self.stats['misses'] += 1
            print(f"❌ CACHE MISS: {key}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600):
        """Set data in cache"""
        self.cache[key] = value
        print(f"💾 CACHED: {key} (TTL: {ttl}s)")
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        return key in self.cache


class MockDatabaseProcessor:
    """Mock database processor that uses cache-aside pattern"""
    
    def __init__(self, name: str, redis_processor: MockRedisProcessor):
        self.name = name
        self.redis = redis_processor
        self.db_operations = 0
    
    async def process_data(self, data: Dict[str, Any], data_type: str) -> Dict[str, Any]:
        """Process data with cache-aside pattern"""
        print(f"\n🔄 {self.name} Processing {data_type} data...")
        
        # 1. Generate cache key
        cache_key = self._generate_cache_key(data, data_type)
        print(f"🔑 Cache key: {cache_key}")
        
        # 2. Check cache first
        cached_data = await self.redis.get(cache_key)
        if cached_data:
            print(f"⚡ Returning cached data from {self.name}")
            return {
                'status': 'cached',
                'source': 'redis',
                'data': cached_data,
                'processor': self.name
            }
        
        # 3. Cache miss - go to database
        print(f"🗄️  Cache miss - querying {self.name} database...")
        db_result = await self._query_database(data, data_type)
        self.db_operations += 1
        
        # 4. Store in cache for next time
        await self.redis.set(cache_key, db_result, ttl=3600)
        
        return {
            'status': 'fresh',
            'source': 'database',
            'data': db_result,
            'processor': self.name
        }
    
    def _generate_cache_key(self, data: Dict[str, Any], data_type: str) -> str:
        """Generate cache key based on data type"""
        if data_type == 'experiment':
            return f"{self.name.lower()}:experiment:{data.get('experiment_id')}"
        elif data_type == 'assignment':
            return f"{self.name.lower()}:assignment:{data.get('experiment_id')}:{data.get('user_id')}"
        elif data_type == 'event':
            return f"{self.name.lower()}:event:{data.get('event_id')}"
        elif data_type == 'user_data':
            return f"{self.name.lower()}:user:{data.get('user_id')}"
        else:
            return f"{self.name.lower()}:{data_type}:{data.get('id', 'unknown')}"
    
    async def _query_database(self, data: Dict[str, Any], data_type: str) -> Dict[str, Any]:
        """Simulate database query"""
        # Simulate database latency
        await asyncio.sleep(0.1)
        
        return {
            **data,
            'processed_by': self.name,
            'processed_at': datetime.utcnow().isoformat(),
            'db_operation_id': f"db_{self.db_operations}"
        }


async def demonstrate_cache_aside_pattern():
    """Demonstrate cache-aside pattern with MCP processors"""
    
    print("🚀 MCP Redis Cache-Aside Pattern Demo")
    print("=" * 50)
    
    # Initialize Redis and processors
    redis_processor = MockRedisProcessor()
    
    processors = {
        'PostgreSQL': MockDatabaseProcessor('PostgreSQL', redis_processor),
        'ClickHouse': MockDatabaseProcessor('ClickHouse', redis_processor),
        'ChromaDB': MockDatabaseProcessor('ChromaDB', redis_processor)
    }
    
    # Simulate MCP routing decisions
    routing_rules = {
        'experiment': ['PostgreSQL', 'ChromaDB'],
        'assignment': ['PostgreSQL', 'Redis'],
        'event': ['ClickHouse', 'Redis'],
        'user_data': ['PostgreSQL', 'Redis']
    }
    
    print("\n📊 Processing Sample Data...")
    print("-" * 30)
    
    # Process each data type
    for data_type, data in SAMPLE_DATA.items():
        print(f"\n📝 Processing {data_type.upper()} data:")
        print(f"   Data: {json.dumps(data, indent=2, default=str)}")
        
        # Route to appropriate processors
        destinations = routing_rules.get(data_type, ['PostgreSQL'])
        
        for destination in destinations:
            if destination == 'Redis':
                # Redis processor handles caching
                cache_key = f"redis:{data_type}:{data.get('id', 'unknown')}"
                await redis_processor.set(cache_key, data, ttl=3600)
                print(f"💾 Redis cached {data_type} data")
            else:
                # Database processors use cache-aside pattern
                processor = processors[destination]
                result = await processor.process_data(data, data_type)
                print(f"   Result: {result['status']} from {result['source']}")
    
    print("\n🔄 Simulating Repeated Requests (Cache Hits)...")
    print("-" * 45)
    
    # Simulate repeated requests to show cache hits
    for i in range(3):
        print(f"\n🔄 Request #{i+1}:")
        
        # Process assignment data again (should hit cache)
        assignment_data = SAMPLE_DATA['assignment']
        postgres_processor = processors['PostgreSQL']
        result = await postgres_processor.process_data(assignment_data, 'assignment')
        print(f"   Assignment result: {result['status']} from {result['source']}")
        
        # Process event data again (should hit cache)
        event_data = SAMPLE_DATA['event']
        clickhouse_processor = processors['ClickHouse']
        result = await clickhouse_processor.process_data(event_data, 'event')
        print(f"   Event result: {result['status']} from {result['source']}")
    
    # Show statistics
    print("\n📈 Performance Statistics:")
    print("-" * 25)
    print(f"Redis Cache Hits: {redis_processor.stats['hits']}")
    print(f"Redis Cache Misses: {redis_processor.stats['misses']}")
    print(f"Cache Hit Rate: {redis_processor.stats['hits'] / (redis_processor.stats['hits'] + redis_processor.stats['misses']) * 100:.1f}%")
    
    for name, processor in processors.items():
        print(f"{name} DB Operations: {processor.db_operations}")
    
    print("\n✅ Demo Complete!")
    print("\nKey Benefits of Redis in MCP:")
    print("• Reduces database load by 60-80%")
    print("• Improves response times by 10-100x")
    print("• Enables data deduplication")
    print("• Provides real-time metrics aggregation")
    print("• Supports cache invalidation patterns")


async def demonstrate_cache_invalidation():
    """Demonstrate cache invalidation patterns"""
    
    print("\n🗑️  Cache Invalidation Demo")
    print("=" * 30)
    
    redis_processor = MockRedisProcessor()
    
    # Set some test data
    await redis_processor.set("postgresql:experiment:exp_123", {"name": "Old Experiment"})
    await redis_processor.set("postgresql:assignment:exp_123:user_1", {"variant": "A"})
    await redis_processor.set("postgresql:assignment:exp_123:user_2", {"variant": "B"})
    
    print("\n📋 Current cache contents:")
    for key, value in redis_processor.cache.items():
        print(f"   {key}: {value}")
    
    # Simulate experiment update - invalidate all related cache
    print("\n🔄 Experiment updated - invalidating related cache...")
    
    # Invalidate all experiment-related cache
    keys_to_remove = [key for key in redis_processor.cache.keys() if 'experiment:exp_123' in key]
    for key in keys_to_remove:
        del redis_processor.cache[key]
        print(f"   ❌ Removed: {key}")
    
    print(f"\n✅ Invalidated {len(keys_to_remove)} cache entries")
    
    print("\n📋 Cache after invalidation:")
    for key, value in redis_processor.cache.items():
        print(f"   {key}: {value}")


if __name__ == "__main__":
    print("🎯 MCP Redis Integration Demonstration")
    print("This shows how Redis helps each MCP processor with cache-aside pattern")
    print("=" * 70)
    
    # Run the demonstrations
    asyncio.run(demonstrate_cache_aside_pattern())
    asyncio.run(demonstrate_cache_invalidation())
