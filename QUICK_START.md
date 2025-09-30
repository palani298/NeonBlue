# 🚀 Quick Start Guide

## Complete CRUD API Setup with Sample Data

This guide will get your experimentation platform running with full CRUD operations and sample data in just a few minutes.

## Prerequisites

- Docker and Docker Compose installed
- Git (to clone the repository)

## 🏃‍♂️ One-Command Setup

```bash
# Clone and setup everything
git clone <your-repo-url>
cd NeonBlue
./setup_with_sample_data.sh
```

That's it! The script will:
- Start all services (PostgreSQL, Redis, Kafka, ClickHouse, API)
- Run database migrations
- Create sample data for all entities
- Display test tokens and endpoints

## 📊 What You Get

### Sample Data Created:
- **5 Users** (4 active, 1 inactive) with different properties
- **4 Experiments** (2 active, 1 draft, 1 paused) with realistic data
- **8 Variants** across all experiments
- **Multiple Assignments** showing user-to-experiment mappings
- **Sample Events** with different types and properties
- **4 API Tokens** with different permission levels

### Complete CRUD Operations:
- ✅ **Experiments**: Create, Read, Update, Delete, Activate, Pause
- ✅ **Variants**: Full CRUD with experiment association
- ✅ **Users**: Full CRUD with soft/hard delete
- ✅ **Events**: Full CRUD with filtering and batch operations
- ✅ **Assignments**: Full CRUD with bulk operations
- ✅ **API Tokens**: Full CRUD with regeneration

## 🧪 Test the API

After setup, you'll get a test token. Use it to test the API:

```bash
# List all experiments
curl -X GET http://localhost:8000/api/v1/experiments \
  -H "Authorization: Bearer YOUR_TEST_TOKEN"

# List all users
curl -X GET http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer YOUR_TEST_TOKEN"

# Get experiment results
curl -X GET http://localhost:8000/api/v1/experiments/1/results \
  -H "Authorization: Bearer YOUR_TEST_TOKEN"
```

## 🌐 Access Points

- **API Documentation**: http://localhost:8000/api/v1/docs
- **Health Check**: http://localhost:8000/health
- **Kafka UI**: http://localhost:8080
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **ClickHouse**: http://localhost:8123

## 🎯 Perfect for React Development

This API provides everything you need for a React frontend:

### Admin Dashboard
- Manage experiments, variants, users, and API tokens
- View analytics and performance metrics
- Track user assignments and events

### User Management
- Complete user lifecycle management
- User properties and segmentation
- Soft/hard delete options

### Experiment Builder
- Create and configure experiments
- Add/remove variants with allocation percentages
- Set experiment timing and status

### Analytics Dashboard
- Real-time experiment results
- Statistical significance calculations
- Time-series data with different granularities

## 🔧 Manual Testing

If you want to test individual CRUD operations:

```bash
# Run the test suite
python test_crud_operations.py

# Or create more sample data
python create_sample_data.py
```

## 📝 API Examples

### Create a New Experiment
```bash
curl -X POST http://localhost:8000/api/v1/experiments \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "my_test",
    "name": "My Test Experiment",
    "description": "Testing something new",
    "variants": [
      {"key": "control", "name": "Control", "allocation_pct": 50, "is_control": true},
      {"key": "treatment", "name": "Treatment", "allocation_pct": 50, "is_control": false}
    ]
  }'
```

### Create a New User
```bash
curl -X POST http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "new_user_123",
    "email": "newuser@example.com",
    "name": "New User",
    "properties": {"plan": "premium", "location": "NYC"}
  }'
```

### Record an Event
```bash
curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "experiment_id": 1,
    "user_id": "user_001",
    "event_type": "click",
    "properties": {"button": "cta", "page": "homepage"}
  }'
```

## 🛠️ Development

### Adding New Endpoints
1. Create schema in `app/schemas/`
2. Add endpoint in `app/api/v1/endpoints/`
3. Register router in `app/api/v1/api.py`
4. Update documentation

### Database Changes
1. Modify models in `app/models/models.py`
2. Create migration: `alembic revision --autogenerate -m "Description"`
3. Apply migration: `alembic upgrade head`

## 🎉 You're Ready!

Your experimentation platform now has:
- ✅ Complete CRUD operations for all entities
- ✅ Sample data for immediate testing
- ✅ RESTful API with proper error handling
- ✅ Authentication and authorization
- ✅ Database relationships and constraints
- ✅ Comprehensive documentation

Start building your React frontend! 🚀
