# 🗂️ Project Structure Overview

## 📁 Organized Directory Structure

```
NeonBlue/
├── 📁 app/                          # FastAPI Application
│   ├── 📁 api/                      # API Routes
│   │   └── 📁 v1/                   # API Version 1
│   │       ├── 📁 endpoints/        # Individual endpoint files
│   │       └── api.py               # Main API router
│   ├── 📁 core/                     # Core functionality
│   │   ├── database.py              # Database configuration
│   │   ├── cache.py                 # Redis cache
│   │   └── auth.py                  # Authentication
│   ├── 📁 middleware/               # Custom middleware
│   ├── 📁 models/                   # SQLAlchemy models
│   ├── 📁 schemas/                  # Pydantic schemas
│   └── main.py                      # FastAPI app entry point
│
├── 📁 alembic/                      # Database migrations
│   ├── 📁 versions/                 # Migration files
│   └── env.py                       # Alembic environment
│
├── 📁 clickhouse/                   # ClickHouse schemas & queries
│   ├── clickhouse-optimal-schema.sql    # Main schema (latest)
│   ├── clickhouse-hot-cold-schema.sql   # Hot/cold data strategy
│   ├── clickhouse-optimal-queries.sql   # Analytics queries
│   ├── clickhouse-database.sql          # Database creation
│   ├── clickhouse-raw-events.sql        # Raw events table
│   ├── clickhouse-processed-events.sql  # Processed events table
│   ├── clickhouse-events-mv.sql         # Events materialized view
│   └── clickhouse-reports.sql           # Reports tables
│
├── 📁 debezium/                     # Debezium CDC configuration
│   ├── debezium-connector-config.json      # Full CDC config
│   └── debezium-events-only-config.json    # Events-only CDC
│
├── 📁 scripts/                      # Setup & utility scripts
│   ├── setup_with_sample_data.sh         # Complete setup
│   ├── setup_optimal_architecture.sh     # Optimal architecture setup
│   ├── setup_hot_cold_data.sh            # Hot/cold data strategy (with S3)
│   ├── setup_hot_cold_simple.sh          # Hot/cold data strategy (simple)
│   ├── setup_direct_postgresql_dicts.sh  # Direct dictionaries setup
│   ├── setup_cdc_pipeline.sh             # CDC pipeline setup
│   └── migrate_to_stored_procedures.sh   # Migration script
│
├── 📁 examples/                     # Example code & demos
│   ├── api_client_example.py            # API client example
│   ├── create_sample_data.py            # Sample data creation
│   ├── test_hot_cold_data.py            # Hot/cold data testing
│   ├── demo_stored_procedures.py        # Stored procedures demo
│   └── demo_usage.py                    # Usage examples
│
├── 📁 tests/                        # Test files
│   ├── test_all_crud.py                 # Comprehensive CRUD tests
│   ├── test_crud_operations.py          # Basic CRUD tests
│   ├── test_experiments.py              # Experiment tests
│   ├── test_events.py                   # Event tests
│   ├── test_assignments.py              # Assignment tests
│   └── test_cache.py                    # Cache tests
│
├── 📁 docs/                         # Documentation
│   ├── README.md                        # Main documentation
│   ├── QUICK_START.md                   # Quick start guide
│   ├── CRUD_API_DOCUMENTATION.md        # API documentation
│   ├── HOT_COLD_DATA_STRATEGY.md        # Hot/cold data strategy
│   ├── OPTIMAL_ARCHITECTURE_EXPLANATION.md # Architecture docs
│   ├── ARCHITECTURE_COMPARISON.md        # Architecture comparison
│   ├── CLICKHOUSE_OPTIMIZATION_STRATEGIES.md # ClickHouse optimization
│   ├── DICTGET_POSTGRESQL_OPTIMIZATION.md # Dictionary optimization
│   ├── DICTIONARY_OPTIMIZATION_APPROACH.md # Dictionary approach
│   ├── DIRECT_POSTGRESQL_DICTIONARIES.md # Direct dictionaries
│   ├── OPTIMAL_POSTGRESQL_DICTIONARY_ACCESS.md # PostgreSQL access
│   ├── STORED_PROCEDURES_README.md       # Stored procedures docs
│   └── requirement_details.md            # Requirements
│
├── 📁 config/                       # Configuration files
│   ├── docker-compose.yml              # Docker services
│   ├── Dockerfile                      # API container
│   └── requirements.txt                # Python dependencies
│
├── 📁 init/                         # Database initialization
│   └── 📁 postgres/                  # PostgreSQL init scripts
│       ├── 01_init.sql               # Database setup
│       └── 02_stored_procedures.sql  # Stored procedures
│
└── 📄 PROJECT_STRUCTURE.md          # This file
```

## 🎯 Key Files by Category

### 🚀 **Quick Start**
- `docs/QUICK_START.md` - Get started quickly
- `scripts/setup_with_sample_data.sh` - Complete setup
- `examples/api_client_example.py` - API usage examples

### 🏗️ **Architecture**
- `docs/OPTIMAL_ARCHITECTURE_EXPLANATION.md` - Main architecture
- `clickhouse/clickhouse-optimal-schema.sql` - Latest ClickHouse schema
- `debezium/debezium-connector-config.json` - CDC configuration

### 🔧 **Development**
- `app/` - FastAPI application code
- `alembic/` - Database migrations
- `tests/` - Test files

### 📊 **Analytics**
- `clickhouse/clickhouse-optimal-queries.sql` - Analytics queries
- `clickhouse/clickhouse-reports.sql` - Reporting tables

### 🐳 **Deployment**
- `config/docker-compose.yml` - All services
- `config/Dockerfile` - API container
- `scripts/` - Setup scripts

## 🔄 **Data Flow**

```
PostgreSQL → Debezium → Kafka → ClickHouse → Analytics
     ↓
  FastAPI ← Redis Cache
```

## 📋 **Next Steps**

1. **Start Services**: `docker compose up -d`
2. **Run Setup**: `./scripts/setup_with_sample_data.sh`
3. **Test API**: `python examples/api_client_example.py`
4. **View Analytics**: Query ClickHouse tables

## 🎉 **Benefits of This Structure**

- ✅ **Clear separation** of concerns
- ✅ **Easy navigation** to relevant files
- ✅ **Logical grouping** by functionality
- ✅ **Scalable** for future additions
- ✅ **Developer-friendly** organization
