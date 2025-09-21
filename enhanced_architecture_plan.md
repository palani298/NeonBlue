# Enhanced Experimentation Platform Architecture
## Incorporating CDC → ClickHouse & Production Patterns

## Executive Summary
Building a production-ready A/B testing platform with:
- **FastAPI** for async REST API
- **PostgreSQL** as transactional source of truth
- **Redis** for hot-path caching
- **CDC → ClickHouse** for scalable analytics
- **Deterministic hashing** for zero-latency assignments

## 1. Core Architecture Stack

### API Layer: FastAPI Ecosystem
```python
# Production dependencies
fastapi==0.104.0
uvicorn[standard]==0.24.0  # Dev server
gunicorn==21.2.0           # Production WSGI
httpx==0.25.0              # Async HTTP client
pydantic==2.4.0            # Data validation
sqlalchemy==2.0.23         # ORM
asyncpg==0.29.0            # Async PostgreSQL driver
alembic==1.12.0            # Database migrations
redis==5.0.0               # Redis client
```

### Why This Stack?
- **FastAPI**: Async I/O, automatic OpenAPI docs, Pydantic validation
- **Uvicorn + Gunicorn**: Production-ready ASGI deployment
- **SQLAlchemy 2.x**: Modern async support with type hints
- **Asyncpg**: High-performance PostgreSQL driver

## 2. Enhanced Data Model

### PostgreSQL Schema (Source of Truth)
```sql
-- Core experiment metadata
CREATE TABLE experiments (
    id BIGSERIAL PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    version INT NOT NULL DEFAULT 1,
    seed TEXT NOT NULL,  -- For deterministic hashing
    starts_at TIMESTAMPTZ,
    ends_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    config JSONB DEFAULT '{}'  -- Additional settings
);

-- Variant definitions
CREATE TABLE variants (
    id BIGSERIAL PRIMARY KEY,
    experiment_id BIGINT REFERENCES experiments(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    name TEXT NOT NULL,
    allocation_pct INT NOT NULL CHECK (allocation_pct >= 0 AND allocation_pct <= 100),
    is_control BOOLEAN NOT NULL DEFAULT FALSE,
    config JSONB DEFAULT '{}',
    UNIQUE (experiment_id, key)
);

-- User assignments (idempotent)
CREATE TABLE assignments (
    id BIGSERIAL PRIMARY KEY,
    experiment_id BIGINT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    variant_id BIGINT NOT NULL REFERENCES variants(id),
    version INT NOT NULL,  -- Tracks experiment version at assignment
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source TEXT NOT NULL DEFAULT 'hash',  -- 'hash', 'db', 'forced', 'override'
    context JSONB DEFAULT '{}',  -- Additional context (device, country, etc.)
    UNIQUE (experiment_id, user_id)  -- Enforces idempotency
);

-- Indexes for assignments
CREATE INDEX idx_assignments_user ON assignments(user_id);
CREATE INDEX idx_assignments_lookup ON assignments(experiment_id, user_id);
CREATE INDEX idx_assignments_time ON assignments(assigned_at);

-- Events table with partitioning
CREATE TABLE events (
    id BIGSERIAL,
    experiment_id BIGINT NOT NULL,
    user_id TEXT NOT NULL,
    variant_id BIGINT,
    type TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    assignment_at TIMESTAMPTZ,  -- Denormalized for performance
    properties JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (id, ts)
) PARTITION BY RANGE (ts);

-- Create monthly partitions automatically
CREATE OR REPLACE FUNCTION create_monthly_partition()
RETURNS void AS $$
DECLARE
    partition_name TEXT;
    start_date DATE;
    end_date DATE;
BEGIN
    start_date := DATE_TRUNC('month', CURRENT_DATE);
    end_date := start_date + INTERVAL '1 month';
    partition_name := 'events_' || TO_CHAR(start_date, 'YYYY_MM');
    
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I PARTITION OF events 
        FOR VALUES FROM (%L) TO (%L)',
        partition_name, start_date, end_date);
    
    -- Create indexes on new partition
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_exp_ts ON %I (experiment_id, ts)', 
                   partition_name, partition_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_exp_type_ts ON %I (experiment_id, type, ts)', 
                   partition_name, partition_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_user_ts ON %I (user_id, ts)', 
                   partition_name, partition_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_props ON %I USING gin (properties jsonb_path_ops)', 
                   partition_name, partition_name);
END;
$$ LANGUAGE plpgsql;

-- Schedule monthly partition creation
CREATE EXTENSION IF NOT EXISTS pg_cron;
SELECT cron.schedule('create-monthly-partition', '0 0 1 * *', 'SELECT create_monthly_partition()');
```

## 3. Deterministic Assignment Algorithm

### Zero-Latency Assignment with Hash-First Approach
```python
import mmh3  # MurmurHash3 for consistent hashing
from typing import Optional, Tuple
import asyncpg
import redis.asyncio as redis

class AssignmentService:
    def __init__(self, db: asyncpg.Pool, cache: redis.Redis):
        self.db = db
        self.cache = cache
        self.bucket_size = 10000  # Granularity for allocation
    
    async def get_assignment(
        self, 
        experiment_id: int, 
        user_id: str,
        force_refresh: bool = False
    ) -> dict:
        # 1. Check cache first (unless force refresh)
        if not force_refresh:
            cache_key = f"assign:exp:{experiment_id}:user:{user_id}"
            cached = await self.cache.get(cache_key)
            if cached:
                return json.loads(cached)
        
        # 2. Check database for existing assignment
        existing = await self.db.fetchrow("""
            SELECT a.*, v.key as variant_key, v.name as variant_name
            FROM assignments a
            JOIN variants v ON a.variant_id = v.id
            WHERE a.experiment_id = $1 AND a.user_id = $2
        """, experiment_id, user_id)
        
        if existing:
            result = dict(existing)
            await self._cache_assignment(experiment_id, user_id, result)
            return result
        
        # 3. Create new assignment using deterministic hashing
        assignment = await self._create_assignment(experiment_id, user_id)
        await self._cache_assignment(experiment_id, user_id, assignment)
        return assignment
    
    async def _create_assignment(self, experiment_id: int, user_id: str) -> dict:
        # Fetch experiment and variants
        experiment = await self.db.fetchrow(
            "SELECT * FROM experiments WHERE id = $1 AND status = 'active'",
            experiment_id
        )
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found or not active")
        
        variants = await self.db.fetch("""
            SELECT id, key, name, allocation_pct 
            FROM variants 
            WHERE experiment_id = $1
            ORDER BY id
        """, experiment_id)
        
        # Deterministic hash calculation
        hash_input = f"{user_id}:{experiment['seed']}"
        bucket = mmh3.hash(hash_input, signed=False) % self.bucket_size
        
        # Map bucket to variant based on allocation percentages
        cumulative = 0
        selected_variant = None
        for variant in variants:
            cumulative += variant['allocation_pct'] * (self.bucket_size / 100)
            if bucket < cumulative:
                selected_variant = variant
                break
        
        if not selected_variant:
            selected_variant = variants[-1]  # Fallback to last variant
        
        # Insert assignment (idempotent via UPSERT)
        result = await self.db.fetchrow("""
            INSERT INTO assignments (
                experiment_id, user_id, variant_id, version, source, assigned_at
            ) VALUES ($1, $2, $3, $4, 'hash', NOW())
            ON CONFLICT (experiment_id, user_id) 
            DO UPDATE SET updated_at = NOW()
            RETURNING *, $5 as variant_key, $6 as variant_name
        """, experiment_id, user_id, selected_variant['id'], 
            experiment['version'], selected_variant['key'], selected_variant['name'])
        
        return dict(result)
    
    async def _cache_assignment(self, experiment_id: int, user_id: str, assignment: dict):
        cache_key = f"assign:exp:{experiment_id}:user:{user_id}"
        await self.cache.setex(
            cache_key,
            86400 * 7,  # 7 days TTL
            json.dumps(assignment, default=str)
        )
```

## 4. CDC → ClickHouse Analytics Pipeline

### Change Data Capture Architecture
```yaml
# docker-compose.yml addition for CDC
services:
  debezium:
    image: debezium/connect:2.4
    environment:
      BOOTSTRAP_SERVERS: kafka:9092
      GROUP_ID: 1
      CONFIG_STORAGE_TOPIC: connect_configs
      OFFSET_STORAGE_TOPIC: connect_offsets
      STATUS_STORAGE_TOPIC: connect_statuses
    depends_on:
      - kafka
      - postgres

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    environment:
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092

  clickhouse:
    image: clickhouse/clickhouse-server:23.8
    volumes:
      - ./clickhouse/config.xml:/etc/clickhouse-server/config.xml
      - ./clickhouse/users.xml:/etc/clickhouse-server/users.xml
```

### ClickHouse Schema for Analytics
```sql
-- ClickHouse tables for analytics
CREATE DATABASE IF NOT EXISTS experiments;

-- Events table optimized for analytics
CREATE TABLE experiments.events (
    experiment_id UInt64,
    user_id String,
    variant_id UInt64,
    event_type String,
    timestamp DateTime64(3),
    assignment_timestamp DateTime64(3),
    properties String,  -- JSON string
    date Date MATERIALIZED toDate(timestamp)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (experiment_id, variant_id, user_id, timestamp)
TTL timestamp + INTERVAL 90 DAY;

-- Pre-aggregated metrics for fast queries
CREATE MATERIALIZED VIEW experiments.hourly_metrics
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(hour)
ORDER BY (experiment_id, variant_id, event_type, hour)
AS SELECT
    experiment_id,
    variant_id,
    event_type,
    toStartOfHour(timestamp) as hour,
    count() as event_count,
    uniqExact(user_id) as unique_users,
    sumIf(1, timestamp >= assignment_timestamp) as valid_events
FROM experiments.events
GROUP BY experiment_id, variant_id, event_type, hour;

-- Daily rollup for reporting
CREATE MATERIALIZED VIEW experiments.daily_metrics
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(day)
ORDER BY (experiment_id, variant_id, event_type, day)
AS SELECT
    experiment_id,
    variant_id,
    event_type,
    toDate(timestamp) as day,
    count() as event_count,
    uniqExact(user_id) as unique_users,
    avg(JSONExtractFloat(properties, 'value')) as avg_value,
    quantile(0.5)(JSONExtractFloat(properties, 'value')) as median_value,
    quantile(0.95)(JSONExtractFloat(properties, 'value')) as p95_value
FROM experiments.events
WHERE timestamp >= assignment_timestamp
GROUP BY experiment_id, variant_id, event_type, day;
```

### CDC Configuration for Debezium
```json
{
  "name": "postgres-events-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres",
    "database.port": "5432",
    "database.user": "experiments_user",
    "database.password": "password",
    "database.dbname": "experiments",
    "database.server.name": "experiments",
    "table.include.list": "public.events,public.assignments",
    "plugin.name": "pgoutput",
    "publication.autocreate.mode": "filtered",
    "transforms": "route",
    "transforms.route.type": "org.apache.kafka.connect.transforms.RegexRouter",
    "transforms.route.regex": "experiments.public.(.*)",
    "transforms.route.replacement": "cdc.$1"
  }
}
```

### ClickHouse Kafka Consumer
```python
# clickhouse_consumer.py
import asyncio
from aiokafka import AIOKafkaConsumer
from clickhouse_driver import Client
import json
from datetime import datetime

class ClickHouseEventConsumer:
    def __init__(self, kafka_servers: str, clickhouse_host: str):
        self.kafka_servers = kafka_servers
        self.ch_client = Client(host=clickhouse_host)
        
    async def consume_events(self):
        consumer = AIOKafkaConsumer(
            'cdc.events',
            bootstrap_servers=self.kafka_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        await consumer.start()
        
        batch = []
        batch_size = 1000
        
        try:
            async for msg in consumer:
                event = self._transform_event(msg.value)
                batch.append(event)
                
                if len(batch) >= batch_size:
                    await self._insert_batch(batch)
                    batch = []
        finally:
            if batch:
                await self._insert_batch(batch)
            await consumer.stop()
    
    def _transform_event(self, cdc_event: dict) -> dict:
        # Transform CDC event to ClickHouse format
        after = cdc_event.get('after', {})
        return {
            'experiment_id': after['experiment_id'],
            'user_id': after['user_id'],
            'variant_id': after['variant_id'],
            'event_type': after['type'],
            'timestamp': datetime.fromisoformat(after['ts']),
            'assignment_timestamp': datetime.fromisoformat(after['assignment_at']),
            'properties': json.dumps(after['properties'])
        }
    
    async def _insert_batch(self, batch: list):
        self.ch_client.execute(
            'INSERT INTO experiments.events VALUES',
            batch
        )
```

## 5. Results Endpoint with Dual-Source Strategy

### Flexible Analytics API
```python
from fastapi import FastAPI, Query, Depends
from typing import Optional, List
from datetime import datetime, timedelta
import asyncpg
from clickhouse_driver.client import Client

class ResultsService:
    def __init__(self, pg_pool: asyncpg.Pool, ch_client: Client):
        self.pg = pg_pool
        self.ch = ch_client
        
    async def get_results(
        self,
        experiment_id: int,
        event_types: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        granularity: str = 'day',  # realtime, hour, day
        metrics: List[str] = ['conversion_rate', 'unique_users'],
        include_ci: bool = True,
        min_sample: int = 100,
        filters: Optional[dict] = None
    ):
        # Determine data source based on time range
        use_clickhouse = self._should_use_clickhouse(start_date, granularity)
        
        if use_clickhouse:
            return await self._get_clickhouse_results(
                experiment_id, event_types, start_date, end_date,
                granularity, metrics, include_ci, min_sample, filters
            )
        else:
            return await self._get_postgres_results(
                experiment_id, event_types, start_date, end_date,
                granularity, metrics, include_ci, min_sample, filters
            )
    
    def _should_use_clickhouse(self, start_date: datetime, granularity: str) -> bool:
        # Use ClickHouse for historical data (> 1 hour old) or day granularity
        if not start_date:
            return False
        
        if granularity == 'day':
            return True
            
        cutoff = datetime.utcnow() - timedelta(hours=1)
        return start_date < cutoff
    
    async def _get_clickhouse_results(self, experiment_id: int, **kwargs):
        # Build ClickHouse query based on granularity
        granularity = kwargs['granularity']
        
        if granularity == 'day':
            table = 'daily_metrics'
            time_col = 'day'
        elif granularity == 'hour':
            table = 'hourly_metrics'
            time_col = 'hour'
        else:
            table = 'events'
            time_col = 'timestamp'
        
        query = f"""
        SELECT 
            variant_id,
            {time_col} as time_bucket,
            event_type,
            sum(event_count) as events,
            sum(unique_users) as users,
            avg(avg_value) as avg_value,
            quantile(0.95)(p95_value) as p95
        FROM experiments.{table}
        WHERE experiment_id = %(experiment_id)s
            AND {time_col} BETWEEN %(start_date)s AND %(end_date)s
            {self._build_filters(kwargs['filters'])}
        GROUP BY variant_id, time_bucket, event_type
        HAVING sum(unique_users) >= %(min_sample)s
        ORDER BY time_bucket, variant_id
        """
        
        results = self.ch.execute(query, {
            'experiment_id': experiment_id,
            'start_date': kwargs['start_date'],
            'end_date': kwargs['end_date'],
            'min_sample': kwargs['min_sample']
        })
        
        # Calculate statistical significance if requested
        if kwargs['include_ci']:
            results = self._add_confidence_intervals(results)
        
        return self._format_response(results, **kwargs)
    
    async def _get_postgres_results(self, experiment_id: int, **kwargs):
        # Real-time query from PostgreSQL for recent data
        query = """
        WITH variant_metrics AS (
            SELECT 
                e.variant_id,
                v.key as variant_key,
                v.is_control,
                DATE_TRUNC($1, e.ts) as time_bucket,
                e.type as event_type,
                COUNT(*) as event_count,
                COUNT(DISTINCT e.user_id) as unique_users,
                AVG((e.properties->>'value')::float) as avg_value,
                PERCENTILE_CONT(0.95) WITHIN GROUP (
                    ORDER BY (e.properties->>'value')::float
                ) as p95_value
            FROM events e
            JOIN variants v ON e.variant_id = v.id
            WHERE e.experiment_id = $2
                AND e.ts >= COALESCE($3, NOW() - INTERVAL '7 days')
                AND e.ts <= COALESCE($4, NOW())
                AND e.ts >= e.assignment_at  -- Only post-assignment events
                AND ($5::text[] IS NULL OR e.type = ANY($5))
            GROUP BY e.variant_id, v.key, v.is_control, time_bucket, e.type
            HAVING COUNT(DISTINCT e.user_id) >= $6
        )
        SELECT * FROM variant_metrics
        ORDER BY time_bucket, variant_id
        """
        
        results = await self.pg.fetch(
            query,
            kwargs['granularity'],
            experiment_id,
            kwargs['start_date'],
            kwargs['end_date'],
            kwargs['event_types'],
            kwargs['min_sample']
        )
        
        if kwargs['include_ci']:
            results = self._add_confidence_intervals(results)
        
        return self._format_response(results, **kwargs)
    
    def _add_confidence_intervals(self, results):
        """Add Wilson score confidence intervals for proportions"""
        import scipy.stats as stats
        
        enhanced_results = []
        for row in results:
            row = dict(row)
            if row['event_count'] > 0:
                # Wilson score interval
                p = row['event_count'] / row['unique_users'] if row['unique_users'] > 0 else 0
                n = row['unique_users']
                z = stats.norm.ppf(0.975)  # 95% CI
                
                denominator = 1 + z**2/n
                center = (p + z**2/(2*n)) / denominator
                margin = z * ((p*(1-p)/n + z**2/(4*n**2))**0.5) / denominator
                
                row['ci_lower'] = max(0, center - margin)
                row['ci_upper'] = min(1, center + margin)
                row['conversion_rate'] = p
            
            enhanced_results.append(row)
        
        return enhanced_results
    
    def _format_response(self, results, **kwargs):
        """Format results for API response"""
        # Group by variant
        variants = {}
        control_metrics = None
        
        for row in results:
            variant_id = row['variant_id']
            if variant_id not in variants:
                variants[variant_id] = {
                    'id': variant_id,
                    'key': row.get('variant_key', f'variant_{variant_id}'),
                    'is_control': row.get('is_control', False),
                    'metrics': {},
                    'time_series': []
                }
            
            # Aggregate metrics
            for metric in kwargs['metrics']:
                if metric not in variants[variant_id]['metrics']:
                    variants[variant_id]['metrics'][metric] = {
                        'value': 0,
                        'sample_size': 0
                    }
                
                # Update metric based on type
                if metric == 'conversion_rate':
                    variants[variant_id]['metrics'][metric]['value'] = row.get('conversion_rate', 0)
                elif metric == 'unique_users':
                    variants[variant_id]['metrics'][metric]['value'] += row['unique_users']
                
                variants[variant_id]['metrics'][metric]['sample_size'] += row['unique_users']
            
            # Add to time series
            variants[variant_id]['time_series'].append({
                'time': row['time_bucket'],
                'event_type': row['event_type'],
                'count': row['event_count'],
                'users': row['unique_users'],
                'ci_lower': row.get('ci_lower'),
                'ci_upper': row.get('ci_upper')
            })
            
            # Track control for lift calculation
            if row.get('is_control'):
                control_metrics = variants[variant_id]['metrics']
        
        # Calculate lift vs control
        if control_metrics:
            for variant_id, variant_data in variants.items():
                if not variant_data['is_control']:
                    for metric_name, metric_data in variant_data['metrics'].items():
                        control_value = control_metrics.get(metric_name, {}).get('value', 0)
                        if control_value > 0:
                            lift = ((metric_data['value'] - control_value) / control_value) * 100
                            metric_data['lift_vs_control'] = round(lift, 2)
        
        return {
            'experiment_id': kwargs['experiment_id'],
            'summary': self._calculate_summary(variants),
            'variants': list(variants.values()),
            'metadata': {
                'start_date': kwargs['start_date'],
                'end_date': kwargs['end_date'],
                'granularity': kwargs['granularity'],
                'total_users': sum(v['metrics'].get('unique_users', {}).get('value', 0) 
                                  for v in variants.values())
            }
        }
    
    def _calculate_summary(self, variants):
        """Calculate experiment-level summary statistics"""
        # Find winning variant
        best_variant = None
        best_rate = 0
        
        for variant in variants.values():
            rate = variant['metrics'].get('conversion_rate', {}).get('value', 0)
            if rate > best_rate:
                best_rate = rate
                best_variant = variant['key']
        
        return {
            'status': 'running',  # Would check experiment table in reality
            'winning_variant': best_variant,
            'confidence_level': 95,
            'minimum_detectable_effect': 0.01  # Would calculate based on power analysis
        }

# FastAPI endpoint
@app.get("/experiments/{experiment_id}/results")
async def get_experiment_results(
    experiment_id: int,
    event_type: Optional[List[str]] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    granularity: str = Query('day', regex='^(realtime|hour|day)$'),
    metrics: List[str] = Query(['conversion_rate', 'unique_users']),
    include_ci: bool = Query(True),
    min_sample: int = Query(100),
    results_service: ResultsService = Depends(get_results_service)
):
    return await results_service.get_results(
        experiment_id=experiment_id,
        event_types=event_type,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        metrics=metrics,
        include_ci=include_ci,
        min_sample=min_sample
    )
```

## 6. Redis Caching Strategy

### Multi-Level Cache Architecture
```python
class CacheManager:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.ttls = {
            'assignment': 86400 * 7,     # 7 days
            'experiment': 3600,          # 1 hour
            'results_summary': 60,        # 1 minute
            'results_detailed': 300,      # 5 minutes
            'token': 3600                 # 1 hour
        }
    
    async def get_or_set(self, key: str, fetch_func, ttl_type: str = 'default'):
        # Try to get from cache
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)
        
        # Fetch from source
        data = await fetch_func()
        
        # Cache with appropriate TTL
        ttl = self.ttls.get(ttl_type, 300)
        await self.redis.setex(key, ttl, json.dumps(data, default=str))
        
        return data
    
    async def invalidate_experiment(self, experiment_id: int):
        """Invalidate all caches related to an experiment"""
        pattern = f"*exp:{experiment_id}*"
        async for key in self.redis.scan_iter(match=pattern):
            await self.redis.delete(key)
    
    async def warm_cache(self, experiment_id: int):
        """Pre-warm cache for an experiment"""
        # Fetch and cache experiment config
        exp_key = f"exp:{experiment_id}:config"
        experiment = await self.db.fetchrow(
            "SELECT * FROM experiments WHERE id = $1", experiment_id
        )
        await self.redis.setex(exp_key, self.ttls['experiment'], 
                              json.dumps(dict(experiment), default=str))
        
        # Pre-compute and cache common metrics
        for granularity in ['hour', 'day']:
            results_key = f"exp:{experiment_id}:results:{granularity}"
            results = await self.compute_results(experiment_id, granularity)
            await self.redis.setex(results_key, self.ttls['results_summary'],
                                  json.dumps(results, default=str))
```

## 7. Production Deployment Configuration

### Docker Compose for Development
```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://user:pass@postgres:5432/experiments
      REDIS_URL: redis://redis:6379/0
      CLICKHOUSE_URL: clickhouse://clickhouse:9000/experiments
    depends_on:
      - postgres
      - redis
      - clickhouse
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: experiments
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"

  clickhouse:
    image: clickhouse/clickhouse-server:23.8
    ports:
      - "8123:8123"
      - "9000:9000"
    volumes:
      - clickhouse_data:/var/lib/clickhouse
      - ./clickhouse/init.sql:/docker-entrypoint-initdb.d/init.sql

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    ports:
      - "9092:9092"

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    ports:
      - "2181:2181"

  debezium:
    image: debezium/connect:2.4
    depends_on:
      - kafka
      - postgres
    ports:
      - "8083:8083"
    environment:
      BOOTSTRAP_SERVERS: kafka:9092
      GROUP_ID: 1
      CONFIG_STORAGE_TOPIC: connect_configs
      OFFSET_STORAGE_TOPIC: connect_offsets
      STATUS_STORAGE_TOPIC: connect_statuses

volumes:
  postgres_data:
  redis_data:
  clickhouse_data:
```

### Kubernetes Production Deployment
```yaml
# api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: experiments-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: experiments-api
  template:
    metadata:
      labels:
        app: experiments-api
    spec:
      containers:
      - name: api
        image: experiments-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        - name: REDIS_URL
          valueFrom:
            configMapKeyRef:
              name: redis-config
              key: url
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: experiments-api
spec:
  selector:
    app: experiments-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: experiments-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: experiments-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## 8. Implementation Checklist for Take-Home

### Must Have (Core Requirements)
- [ ] FastAPI application with all required endpoints
- [ ] PostgreSQL schema with proper indexes
- [ ] Deterministic assignment algorithm
- [ ] Redis caching for assignments
- [ ] Bearer token authentication
- [ ] Docker Compose setup
- [ ] Event filtering (only post-assignment)
- [ ] Flexible results endpoint with query params

### Should Have (Stand Out Features)
- [ ] Statistical significance calculations
- [ ] CDC setup with Debezium (at least configuration)
- [ ] ClickHouse schema design
- [ ] Materialized views for performance
- [ ] Comprehensive error handling
- [ ] Health check endpoints
- [ ] Prometheus metrics
- [ ] Unit tests for assignment logic

### Nice to Have (If Time Permits)
- [ ] Feature flags capability
- [ ] GraphQL endpoint
- [ ] Real-time WebSocket updates
- [ ] Admin UI
- [ ] A/B/n testing support
- [ ] Bayesian statistics option
- [ ] Export to CSV/JSON

## 9. Key Differentiators

1. **Production-Ready Architecture**: Shows CDC → ClickHouse for scale
2. **Deterministic Hashing**: Zero-latency assignments with consistency
3. **Dual-Source Analytics**: PostgreSQL for real-time, ClickHouse for historical
4. **Sophisticated Caching**: Multi-level with intelligent invalidation
5. **Statistical Rigor**: Wilson score intervals, power analysis
6. **Operational Excellence**: Health checks, metrics, gradual rollouts

This architecture demonstrates:
- Understanding of scale challenges
- Knowledge of modern data infrastructure
- Ability to balance complexity with practicality
- Focus on performance and reliability
- Clear upgrade path from MVP to production