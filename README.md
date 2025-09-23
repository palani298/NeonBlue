# Experimentation Platform

A production-ready A/B testing platform built with FastAPI, PostgreSQL, Redis, and prepared for ClickHouse analytics via CDC (Change Data Capture).

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   FastAPI   │────▶│    Redis    │────▶│ PostgreSQL  │
│   Gateway   │     │    Cache    │     │  Metadata   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                                        │
       │                                        ▼
       │                                 ┌─────────────┐
       │                                 │   Outbox    │
       │                                 │   Events    │
       │                                 └─────────────┘
       │                                        │
       ▼                                        ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Metrics   │     │  Debezium   │────▶│    Kafka    │
│ Prometheus  │     │     CDC     │     │   Events    │
└─────────────┘     └─────────────┘     └─────────────┘
                                                │
                                                ▼
                                         ┌─────────────┐
                                         │ ClickHouse  │
                                         │  Analytics  │
                                         └─────────────┘
```

## Key Features

### Core Functionality
- ✅ **Deterministic Assignment**: MurmurHash-based assignment ensures consistency
- ✅ **Idempotent Operations**: Once assigned, users always get the same variant
- ✅ **Transactional Outbox**: Ensures reliable event delivery via CDC
- ✅ **Statistical Analysis**: Wilson score confidence intervals, p-values
- ✅ **Flexible Reporting**: Multiple granularities, metrics, and filters

### Production Features
- ✅ **Bearer Token Authentication**: With Redis caching
- ✅ **Rate Limiting**: Token bucket algorithm per client
- ✅ **API Timing Middleware**: Track slow endpoints
- ✅ **Prometheus Metrics**: Full observability
- ✅ **Health Checks**: Readiness and liveness probes
- ✅ **Docker Compose**: Complete local environment

### Data Pipeline
- ✅ **PostgreSQL**: Transactional source of truth
- ✅ **Redis**: High-performance caching layer
- ✅ **Transactional Outbox**: Reliable event publishing
- ✅ **Debezium CDC**: Capture data changes
- ✅ **Kafka**: Event streaming backbone
- ✅ **ClickHouse**: Analytics at scale (configured)

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for local development)
- 8GB RAM minimum

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd experimentation-platform

# Create environment file
cp .env.example .env
# Edit .env with your settings
```

### 2. Start Services

```bash
# Start all services
docker-compose up -d

# Wait for services to be healthy
docker-compose ps

# Check logs
docker-compose logs -f api
```

### 3. Initialize Database

The database is automatically initialized on first run. To manually run migrations:

```bash
# Run Alembic migrations
docker-compose exec api alembic upgrade head
```

### 4. Access Services

- **API Documentation**: http://localhost:8000/api/v1/docs
- **Kafka UI**: http://localhost:8080
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **ClickHouse**: http://localhost:8123

## API Usage Examples

### 1. Create an Experiment

```bash
curl -X POST http://localhost:8000/api/v1/experiments \
  -H "Authorization: Bearer test-token-1" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "homepage_cta_test",
    "name": "Homepage CTA Test",
    "description": "Testing button colors",
    "variants": [
      {
        "key": "control",
        "name": "Blue Button",
        "allocation_pct": 50,
        "is_control": true
      },
      {
        "key": "treatment",
        "name": "Green Button",
        "allocation_pct": 50,
        "is_control": false
      }
    ]
  }'
```

### 2. Get User Assignment

```bash
# First call creates assignment
curl -X GET "http://localhost:8000/api/v1/experiments/1/assignment/user123" \
  -H "Authorization: Bearer test-token-1"

# Subsequent calls return same assignment (idempotent)
curl -X GET "http://localhost:8000/api/v1/experiments/1/assignment/user123?enroll=true" \
  -H "Authorization: Bearer test-token-1"
```

### 3. Record Event

```bash
curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer test-token-1" \
  -H "Content-Type: application/json" \
  -d '{
    "experiment_id": 1,
    "user_id": "user123",
    "event_type": "click",
    "properties": {
      "button": "cta",
      "page": "homepage"
    }
  }'
```

### 4. Get Results

```bash
curl -X GET "http://localhost:8000/api/v1/experiments/1/results?granularity=day&include_ci=true" \
  -H "Authorization: Bearer test-token-1"
```

### 5. Bulk Assignments (Optimized)

```bash
curl -X POST http://localhost:8000/api/v1/assignments/bulk \
  -H "Authorization: Bearer test-token-1" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "experiment_ids": [1, 2, 3, 4, 5]
  }'
```

## Configuration

### Environment Variables

```bash
# API Configuration
DEBUG=false
SECRET_KEY=your-secret-key-change-in-production
BEARER_TOKENS=["token1", "token2"]

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/experiments
DATABASE_POOL_SIZE=20

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_POOL_SIZE=10

# ClickHouse
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=9000
CLICKHOUSE_DATABASE=experiments

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60

# Assignment Configuration
ASSIGNMENT_BUCKET_SIZE=10000
ASSIGNMENT_CACHE_TTL=604800

# Monitoring
PROMETHEUS_ENABLED=true
ENABLE_TIMING_MIDDLEWARE=true
SLOW_API_THRESHOLD_MS=1000
```

## CDC Pipeline Setup

### 1. Configure Debezium Connector

```bash
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "experiments-connector",
    "config": {
      "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
      "database.hostname": "postgres",
      "database.port": "5432",
      "database.user": "experiments",
      "database.password": "password",
      "database.dbname": "experiments",
      "database.server.name": "experiments",
      "table.include.list": "public.outbox_events",
      "plugin.name": "pgoutput",
      "publication.autocreate.mode": "filtered",
      "slot.name": "debezium"
    }
  }'
```

### 2. Verify Kafka Topics

```bash
# List topics
docker-compose exec kafka kafka-topics --list --bootstrap-server localhost:9092

# Consume events
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic experiments.public.outbox_events \
  --from-beginning
```

### 3. ClickHouse Integration

ClickHouse is configured to automatically consume events from Kafka. Check the materialized views:

```sql
-- Connect to ClickHouse
docker-compose exec clickhouse clickhouse-client

-- Check events
SELECT * FROM experiments.events LIMIT 10;

-- Check daily metrics
SELECT * FROM experiments.daily_metrics;
```

## Performance Optimizations

### 1. Bulk Operations
- Use `/assignments/bulk` for multiple experiments per user
- Batch events with `/events/batch` endpoint
- Redis pipeline for cache operations

### 2. Caching Strategy
- 7-day TTL for assignments
- 1-minute TTL for results
- Version-aware cache keys

### 3. Database Optimizations
- Monthly partitioning for events table
- Proper indexes on all lookup columns
- Connection pooling with asyncpg

## Monitoring

### Prometheus Metrics
- Request duration and count
- Assignment and event counts
- Cache hit/miss rates
- Database pool metrics

### Grafana Dashboards
Access Grafana at http://localhost:3000 (admin/admin) for:
- API performance dashboard
- Business metrics dashboard
- System health dashboard

## Testing

### Run Tests

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

### Load Testing

```bash
# Using locust
locust -f tests/load_test.py --host=http://localhost:8000
```

## Production Deployment

### Kubernetes Deployment

```bash
# Apply configurations
kubectl apply -f k8s/

# Check status
kubectl get pods -n experiments
```

### Scaling Considerations

1. **API Layer**: Horizontal scaling with Kubernetes HPA
2. **PostgreSQL**: Read replicas for analytics queries
3. **Redis**: Redis Cluster for sharding
4. **Kafka**: Multi-broker cluster
5. **ClickHouse**: Sharded cluster for analytics

## Architecture Decisions

### Why This Stack?

1. **FastAPI**: Async Python, automatic OpenAPI docs, Pydantic validation
2. **PostgreSQL**: ACID compliance, JSONB support, partitioning
3. **Redis**: Sub-millisecond latency for assignments
4. **Transactional Outbox**: Guarantees event delivery without distributed transactions
5. **CDC with Debezium**: Real-time data pipeline without application changes
6. **Kafka**: Decouples producers and consumers, enables replay
7. **ClickHouse**: Optimized for analytics queries at scale

### Key Design Patterns

1. **Deterministic Hashing**: Consistent assignments without database lookups
2. **Idempotency**: Same user always gets same variant
3. **Transactional Outbox**: Reliable event publishing
4. **Dual-Source Analytics**: PostgreSQL for hot, ClickHouse for cold
5. **Cache-Aside Pattern**: Check cache, fallback to database

## Troubleshooting

### Common Issues

1. **Database Connection Issues**
```bash
# Check PostgreSQL logs
docker-compose logs postgres

# Verify connection
docker-compose exec postgres psql -U experiments -d experiments
```

2. **Redis Connection Issues**
```bash
# Check Redis logs
docker-compose logs redis

# Test connection
docker-compose exec redis redis-cli ping
```

3. **Kafka Issues**
```bash
# Check Kafka logs
docker-compose logs kafka

# List topics
docker-compose exec kafka kafka-topics --list --bootstrap-server localhost:9092
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - See LICENSE file for details

## Support

For issues and questions:
- Create an issue on GitHub
- Check the documentation at `/api/v1/docs`
- Review the architecture documents in `/docs`
