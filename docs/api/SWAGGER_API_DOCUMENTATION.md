# 🚀 Experiments Platform API Documentation

## Overview
This document provides comprehensive examples for testing the Experiments Platform API using Swagger UI at `http://localhost:8001/api/v1/docs`.

## 🔐 Authentication
All API endpoints require Bearer token authentication. Use one of these tokens:

- **Admin Token**: `admin_token_123` (Full access)
- **Experiment Token**: `experiment_token_789` (Experiment management)
- **Readonly Token**: `readonly_token_456` (Read-only access)

## 📊 Current System Status
- **PostgreSQL**: 5 experiments, 10 variants, 8 users
- **ClickHouse**: 21 events, 10 reports
- **CDC Pipeline**: ✅ Working (PostgreSQL → Kafka → ClickHouse)
- **React Dashboard**: `http://localhost:3001`

---

## 🧪 Experiments Management

### 1. Create New Experiment
**POST** `/api/v1/experiments/`

```json
{
  "key": "checkout-button-test",
  "name": "Checkout Button Color Test",
  "description": "Testing if green checkout button increases conversions",
  "variants": [
    {
      "key": "control",
      "name": "Blue Button (Control)",
      "allocation_pct": 50,
      "is_control": true,
      "config": {
        "button_color": "blue",
        "button_text": "Checkout Now"
      }
    },
    {
      "key": "treatment",
      "name": "Green Button (Treatment)",
      "allocation_pct": 50,
      "is_control": false,
      "config": {
        "button_color": "green",
        "button_text": "Checkout Now"
      }
    }
  ]
}
```

### 2. Get All Experiments
**GET** `/api/v1/experiments/`

### 3. Get Experiment by ID
**GET** `/api/v1/experiments/1`

### 4. Update Experiment
**PUT** `/api/v1/experiments/1`

```json
{
  "name": "Updated Checkout Button Test",
  "description": "Updated description for better clarity",
  "status": "ACTIVE"
}
```

### 5. Delete Experiment
**DELETE** `/api/v1/experiments/1`

---

## 👥 User Management

### 1. Create New User
**POST** `/api/v1/users/`

```json
{
  "user_id": "test-user-123",
  "email": "testuser@example.com",
  "name": "Test User",
  "properties": {
    "age": 28,
    "location": "San Francisco",
    "plan": "premium",
    "signup_date": "2024-09-29"
  }
}
```

### 2. Get All Users
**GET** `/api/v1/users/`

### 3. Get User by ID
**GET** `/api/v1/users/test-user-123`

### 4. Update User
**PUT** `/api/v1/users/test-user-123`

```json
{
  "name": "Updated Test User",
  "properties": {
    "age": 29,
    "location": "New York",
    "plan": "enterprise"
  }
}
```

---

## 🎯 Assignment Management

### 1. Get User Assignment
**GET** `/api/v1/assignments/experiments/1/assignment/test-user-123`

### 2. Create Assignment
**POST** `/api/v1/assignments/`

```json
{
  "experiment_id": 1,
  "user_id": "test-user-123",
  "context": {
    "ip": "192.168.1.100",
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "page": "/checkout"
  }
}
```

### 3. Get All Assignments
**GET** `/api/v1/assignments/`

---

## 📈 Event Recording

### 1. Record Event
**POST** `/api/v1/events/`

```json
{
  "experiment_id": 1,
  "user_id": "test-user-123",
  "event_type": "conversion",
  "properties": {
    "page": "/checkout",
    "device": "desktop",
    "value": 99.99,
    "currency": "USD",
    "product_id": "prod-123"
  }
}
```

### 2. Record Page View Event
**POST** `/api/v1/events/`

```json
{
  "experiment_id": 1,
  "user_id": "test-user-123",
  "event_type": "page_view",
  "properties": {
    "page": "/checkout",
    "device": "mobile",
    "session_id": "sess-456",
    "referrer": "https://google.com"
  }
}
```

### 3. Record Custom Event
**POST** `/api/v1/events/`

```json
{
  "experiment_id": 1,
  "user_id": "test-user-123",
  "event_type": "button_click",
  "properties": {
    "button_id": "checkout-btn",
    "button_text": "Checkout Now",
    "button_color": "green",
    "click_position": {
      "x": 150,
      "y": 300
    }
  }
}
```

---

## 📊 Analytics & Reporting

### 1. Get Experiments Analytics
**GET** `/api/v1/analytics/experiments`

### 2. Get Variants Analytics
**GET** `/api/v1/analytics/variants`

### 3. Get Assignments Analytics
**GET** `/api/v1/analytics/assignments`

### 4. Get Events Analytics
**GET** `/api/v1/analytics/events?limit=10&offset=0`

### 5. Get Users Analytics
**GET** `/api/v1/analytics/users`

### 6. Get Reports (ClickHouse Aggregated Data)
**GET** `/api/v1/analytics/reports`

### 7. Get System Summary
**GET** `/api/v1/analytics/summary`

---

## 🔑 API Token Management

### 1. Create API Token
**POST** `/api/v1/api-tokens/`

```json
{
  "name": "My Test Token",
  "description": "Token for testing API endpoints"
}
```

### 2. Get All API Tokens
**GET** `/api/v1/api-tokens/`

### 3. Get API Token by ID
**GET** `/api/v1/api-tokens/1`

### 4. Update API Token
**PUT** `/api/v1/api-tokens/1`

```json
{
  "name": "Updated Test Token",
  "is_active": true
}
```

### 5. Delete API Token
**DELETE** `/api/v1/api-tokens/1`

---

## 🧹 Data Management

### 1. Cleanup Old Data
**POST** `/api/v1/data-management/cleanup`

```json
{
  "retention_days": 30,
  "cleanup_events": true,
  "cleanup_assignments": false,
  "cleanup_outbox": true
}
```

### 2. Get Data Statistics
**GET** `/api/v1/data-management/stats`

---

## 🔍 Testing Scenarios

### Scenario 1: Complete A/B Test Flow
1. **Create Experiment**: Use the checkout button test example above
2. **Create User**: Use the test user example above
3. **Get Assignment**: Check which variant the user gets assigned
4. **Record Events**: Record page view, button click, and conversion events
5. **View Analytics**: Check the reports to see the results

### Scenario 2: Multi-Variant Test
1. **Create Experiment** with 3 variants (control + 2 treatments)
2. **Create Multiple Users** with different properties
3. **Record Various Events** for each user
4. **Analyze Results** using the reports endpoint

### Scenario 3: Event Tracking
1. **Record Different Event Types**: page_view, click, conversion, custom events
2. **Use Rich Properties**: Include detailed metadata in event properties
3. **Track User Journey**: Record events across multiple pages/sessions
4. **View Real-time Data**: Check events in ClickHouse via analytics endpoints

---

## 🚨 Common Issues & Solutions

### 1. Authentication Errors
- **Problem**: 403 Forbidden
- **Solution**: Ensure you're using a valid Bearer token in the Authorization header

### 2. Validation Errors
- **Problem**: 422 Unprocessable Entity
- **Solution**: Check that all required fields are provided and data types are correct

### 3. Not Found Errors
- **Problem**: 404 Not Found
- **Solution**: Verify the resource ID exists and you have access to it

### 4. Server Errors
- **Problem**: 500 Internal Server Error
- **Solution**: Check the API logs and ensure all services are running

---

## 📱 Frontend Integration

### React Dashboard
- **URL**: `http://localhost:3001`
- **Features**: Real-time data display, analytics charts, experiment management

### API Client Example
```python
import httpx

# Example Python client
async with httpx.AsyncClient() as client:
    headers = {"Authorization": "Bearer admin_token_123"}
    
    # Get experiments
    response = await client.get(
        "http://localhost:8001/api/v1/experiments/",
        headers=headers
    )
    experiments = response.json()
```

---

## 🔗 Useful URLs

- **API Documentation**: `http://localhost:8001/api/v1/docs`
- **React Dashboard**: `http://localhost:3001`
- **Grafana Monitoring**: `http://localhost:3000`
- **Prometheus Metrics**: `http://localhost:9090`
- **Kafka Connect**: `http://localhost:8083`

---

## 📈 Monitoring & Health

### Health Check
**GET** `/health`

### Metrics
**GET** `/metrics`

### System Status
Check the `/api/v1/analytics/summary` endpoint for comprehensive system status including:
- PostgreSQL data counts
- ClickHouse data counts
- Service health status
- Total record counts

---

*This documentation is automatically generated and reflects the current state of the Experiments Platform API.*

