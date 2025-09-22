# Experimentation Platform Architecture Discussion

## Overview
This document explores various architectural approaches for building a scalable A/B testing platform, considering different technology stacks and their trade-offs.

## Core Requirements Analysis

### Key Functional Requirements
1. **Experiment Management**: Create and manage experiments with multiple variants
2. **User Assignment**: Idempotent, persistent variant assignment with configurable traffic allocation
3. **Event Tracking**: High-volume event ingestion with flexible properties
4. **Results Analysis**: Real-time and batch analytics with multiple aggregation levels
5. **Authentication**: Bearer token-based API security

### Non-Functional Requirements (Implied)
- **Scalability**: Handle millions of users and billions of events
- **Performance**: Low-latency assignment decisions (<50ms)
- **Reliability**: 99.9%+ uptime for critical paths
- **Data Consistency**: Accurate experiment results
- **Extensibility**: Easy to add new features

## Architecture Approaches

### Approach 1: Modern Microservices Stack (Production-Ready)

#### Technology Stack
```
API Layer:        FastAPI (async Python)
Primary DB:       PostgreSQL (transactional metadata)
Cache:            Redis (assignment cache, real-time metrics)
Event Store:      ClickHouse/TimescaleDB (time-series events)
Message Queue:    Kafka/RabbitMQ (event streaming)
Container:        Docker + Kubernetes
Monitoring:       Prometheus + Grafana
```

#### Component Architecture
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   FastAPI   │────▶│    Redis    │────▶│ PostgreSQL  │
│   Gateway   │     │    Cache    │     │  Metadata   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                                        │
       ▼                                        ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Kafka     │────▶│  ClickHouse │────▶│  Analytics  │
│   Events    │     │ Time-Series │     │   Engine    │
└─────────────┘     └─────────────┘     └─────────────┘
```

#### Pros
- **High Performance**: Async FastAPI + Redis cache = <10ms assignment latency
- **Scalability**: Horizontal scaling at each layer
- **Reliability**: Redis for hot path, PostgreSQL for consistency
- **Analytics**: ClickHouse optimized for time-series analytics
- **Flexibility**: Kafka enables real-time and batch processing

#### Cons
- **Complexity**: Multiple systems to manage
- **Cost**: Higher infrastructure requirements
- **Development Time**: Longer initial setup

#### Scaling Strategies
- **API**: Kubernetes HPA based on CPU/memory
- **PostgreSQL**: Read replicas, connection pooling (PgBouncer)
- **Redis**: Redis Cluster for sharding
- **ClickHouse**: Built-in sharding and replication
- **Kafka**: Partition by user_id or experiment_id

### Approach 2: Simplified Monolithic Stack (MVP/Take-Home)

#### Technology Stack
```
API Layer:        FastAPI
Database:         PostgreSQL (all data)
Cache:            Redis (optional)
Container:        Docker Compose
```

#### Database Schema
```sql
-- Core Tables
experiments (
    id UUID PRIMARY KEY,
    name VARCHAR,
    status VARCHAR,
    created_at TIMESTAMP,
    config JSONB  -- variant weights, metadata
)

variants (
    id UUID PRIMARY KEY,
    experiment_id UUID REFERENCES experiments,
    name VARCHAR,
    weight DECIMAL,
    is_control BOOLEAN
)

assignments (
    user_id VARCHAR,
    experiment_id UUID,
    variant_id UUID,
    assigned_at TIMESTAMP,
    PRIMARY KEY (user_id, experiment_id),
    INDEX idx_assignment_lookup (experiment_id, user_id)
)

events (
    id UUID PRIMARY KEY,
    user_id VARCHAR,
    event_type VARCHAR,
    timestamp TIMESTAMP,
    properties JSONB,
    INDEX idx_events_user_time (user_id, timestamp),
    INDEX idx_events_type_time (event_type, timestamp)
) PARTITION BY RANGE (timestamp);  -- Monthly partitions
```

#### Pros
- **Simplicity**: Single database, easier to reason about
- **Quick Development**: Faster to implement
- **Cost-Effective**: Minimal infrastructure
- **Good Enough**: Handles moderate scale (millions of events)

#### Cons
- **Performance Limits**: Database becomes bottleneck
- **Analytics**: Complex queries slow without specialized DB
- **Scaling**: Vertical scaling limitations

### Approach 3: Hybrid Approach (Recommended for Take-Home)

#### Technology Stack
```
API:              FastAPI (async for performance)
Primary DB:       PostgreSQL (metadata + recent events)
Cache:            Redis (assignments + hot metrics)
Background Jobs:  Celery (async analytics)
Container:        Docker Compose
```

#### Implementation Strategy

##### 1. FastAPI Application Structure
```python
app/
├── api/
│   ├── experiments.py    # Experiment CRUD
│   ├── assignments.py    # User assignment logic
│   ├── events.py        # Event ingestion
│   └── results.py       # Analytics endpoints
├── core/
│   ├── auth.py          # Bearer token validation
│   ├── cache.py         # Redis operations
│   └── config.py        # Environment config
├── models/
│   ├── experiment.py    # SQLAlchemy models
│   └── event.py
├── services/
│   ├── assignment.py    # Assignment algorithm
│   ├── analytics.py     # Results calculation
│   └── statistics.py    # Statistical significance
└── main.py
```

##### 2. Assignment Algorithm with Caching
```python
async def get_assignment(experiment_id: str, user_id: str):
    # Check Redis cache first
    cache_key = f"assignment:{experiment_id}:{user_id}"
    cached = await redis.get(cache_key)
    if cached:
        return cached
    
    # Check PostgreSQL for existing assignment
    assignment = await db.get_assignment(experiment_id, user_id)
    if assignment:
        await redis.setex(cache_key, 3600, assignment)
        return assignment
    
    # Create new assignment
    variant = calculate_variant(experiment_id, user_id)
    await db.create_assignment(experiment_id, user_id, variant)
    await redis.setex(cache_key, 3600, variant)
    return variant
```

##### 3. Event Ingestion Pattern
```python
async def ingest_event(event_data: EventSchema):
    # Quick validation
    validate_event(event_data)
    
    # Write to database (async)
    await db.insert_event(event_data)
    
    # Update real-time metrics in Redis
    await update_redis_metrics(event_data)
    
    # Queue for batch processing if needed
    if requires_batch_processing(event_data):
        celery_task.delay(event_data)
    
    return {"status": "accepted"}
```

## Database Partitioning Strategies

### PostgreSQL Partitioning for Events Table

#### Time-based Partitioning (Recommended)
```sql
-- Create parent table
CREATE TABLE events (
    id UUID DEFAULT gen_random_uuid(),
    user_id VARCHAR(255),
    event_type VARCHAR(50),
    timestamp TIMESTAMP NOT NULL,
    properties JSONB,
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Create monthly partitions
CREATE TABLE events_2024_01 PARTITION OF events
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Automated partition creation
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
    
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF events 
                    FOR VALUES FROM (%L) TO (%L)',
                    partition_name, start_date, end_date);
END;
$$ LANGUAGE plpgsql;
```

#### Benefits
- **Query Performance**: Partition pruning for time-range queries
- **Maintenance**: Easy to drop old partitions
- **Parallel Processing**: Query multiple partitions concurrently

### Redis Sharding Strategy

#### Key Design Patterns
```python
# Hierarchical key structure
assignment_key = f"exp:{experiment_id}:user:{user_id}:assignment"
metric_key = f"exp:{experiment_id}:metric:{metric_name}:{date}"
user_events_key = f"user:{user_id}:events:{date}"

# Hash tags for Redis Cluster (keep related keys on same shard)
assignment_key = f"{{exp:{experiment_id}}}:user:{user_id}"
```

## Do You Need gRPC?

### When to Consider gRPC
1. **Internal Service Communication**: If splitting into microservices
2. **High-Performance Requirements**: Binary protocol faster than JSON
3. **Strong Typing**: Protocol buffers provide schema enforcement
4. **Streaming**: Real-time event streams between services

### For This Project
**Recommendation: No gRPC needed initially**
- REST API is sufficient for the requirements
- FastAPI provides OpenAPI documentation automatically
- JSON is more debuggable and easier to test
- Can add gRPC later if needed for internal services

## Scaling Considerations

### Horizontal Scaling Patterns

#### 1. API Layer Scaling
```yaml
# Kubernetes HPA example
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fastapi-deployment
  minReplicas: 3
  maxReplicas: 100
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

#### 2. Database Scaling
- **Read Replicas**: Separate read/write traffic
- **Connection Pooling**: PgBouncer for connection management
- **Sharding**: Partition by experiment_id or user_id if needed

#### 3. Cache Scaling
- **Redis Sentinel**: High availability
- **Redis Cluster**: Automatic sharding
- **Cache Levels**: L1 (application), L2 (Redis), L3 (database)

### Performance Optimization Strategies

#### 1. Assignment Optimization
```python
# Batch assignment prefetch
async def prefetch_assignments(experiment_id: str, user_ids: List[str]):
    # Single query for multiple users
    existing = await db.get_assignments_batch(experiment_id, user_ids)
    
    # Parallel Redis writes
    await asyncio.gather(*[
        redis.setex(f"assignment:{experiment_id}:{user_id}", 3600, assignment)
        for user_id, assignment in existing.items()
    ])
```

#### 2. Analytics Optimization
```python
# Materialized views for common queries
CREATE MATERIALIZED VIEW experiment_metrics AS
SELECT 
    experiment_id,
    variant_id,
    DATE(timestamp) as date,
    event_type,
    COUNT(*) as event_count,
    COUNT(DISTINCT user_id) as unique_users
FROM events e
JOIN assignments a ON e.user_id = a.user_id
WHERE e.timestamp > a.assigned_at
GROUP BY 1, 2, 3, 4;

# Refresh strategy
REFRESH MATERIALIZED VIEW CONCURRENTLY experiment_metrics;
```

## Recommended Implementation Plan

### Phase 1: MVP (Take-Home)
1. **FastAPI** with async endpoints
2. **PostgreSQL** for all data storage
3. **Redis** for assignment caching
4. **Docker Compose** for local development
5. **Basic authentication** with bearer tokens
6. Focus on **clean code** and **good schema design**

### Phase 2: Production Enhancements
1. Add **Kafka** for event streaming
2. Implement **ClickHouse** for analytics
3. Add **Celery** for background jobs
4. Implement **circuit breakers** and retries
5. Add **monitoring** with Prometheus

### Phase 3: Scale Optimizations
1. Implement **database sharding**
2. Add **CDN** for static content
3. Implement **GraphQL** for flexible queries
4. Add **feature flags** for gradual rollouts
5. Implement **multi-region** deployment

## Key Design Decisions

### 1. Why FastAPI over Flask/Django?
- **Performance**: Async support, faster than Flask
- **Developer Experience**: Automatic OpenAPI docs
- **Type Safety**: Pydantic models for validation
- **Modern**: Built for Python 3.7+

### 2. Why PostgreSQL over MongoDB?
- **ACID Compliance**: Critical for assignment consistency
- **Relational Model**: Natural fit for experiments/variants
- **JSON Support**: JSONB for flexible event properties
- **Maturity**: Proven at scale

### 3. Why Redis for Caching?
- **Performance**: Sub-millisecond latency
- **Data Structures**: Sets, sorted sets for metrics
- **TTL Support**: Automatic cache expiration
- **Pub/Sub**: Real-time updates if needed

## Example API Design

### Experiment Creation
```python
POST /experiments
{
    "name": "Homepage CTA Test",
    "description": "Testing button colors",
    "variants": [
        {"name": "control", "weight": 0.5, "is_control": true},
        {"name": "blue_button", "weight": 0.25},
        {"name": "green_button", "weight": 0.25}
    ],
    "targeting": {
        "countries": ["US", "CA"],
        "min_version": "2.0.0"
    }
}
```

### Results Endpoint Design
```python
GET /experiments/{id}/results?
    start_date=2024-01-01&
    end_date=2024-01-31&
    metrics=conversion_rate,revenue&
    group_by=day,variant&
    confidence_level=0.95

Response:
{
    "experiment_id": "...",
    "summary": {
        "total_users": 100000,
        "duration_days": 30,
        "status": "significant"
    },
    "variants": [
        {
            "id": "control",
            "metrics": {
                "conversion_rate": {
                    "value": 0.05,
                    "confidence_interval": [0.048, 0.052],
                    "sample_size": 50000
                }
            },
            "time_series": [...]
        }
    ],
    "statistical_significance": {
        "p_value": 0.001,
        "confidence": 0.95,
        "minimum_detectable_effect": 0.01
    }
}
```

## Conclusion

For the take-home assessment, I recommend:
1. **FastAPI + PostgreSQL + Redis** for the core stack
2. **Docker Compose** for easy setup
3. **Focus on clean architecture** with clear separation of concerns
4. **Implement caching** for the assignment endpoint
5. **Design flexible schema** with partitioning consideration
6. **Add statistical significance** calculation as a differentiator

This approach balances simplicity with production-readiness, demonstrating both practical skills and architectural thinking.