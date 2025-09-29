# 🔐 API Authentication Guide

## Available API Tokens

You have **3 pre-configured API tokens** ready to use:

### 1. **Admin Token** (Full Access)
```
Token: admin_token_123
Access: All endpoints (create, read, update, delete)
```

### 2. **Experiment Token** (Experiment Management)
```
Token: experiment_token_789
Access: Experiment-related endpoints
```

### 3. **Read-Only Token** (View Only)
```
Token: readonly_token_456
Access: Read-only access to all endpoints
```

## 🚀 How to Use

### Using curl:
```bash
# List experiments
curl -H "Authorization: Bearer admin_token_123" \
     "http://localhost:8000/api/v1/experiments/"

# Create a new experiment
curl -X POST \
     -H "Authorization: Bearer admin_token_123" \
     -H "Content-Type: application/json" \
     -d '{"key":"my-test","name":"My Test","variants":[{"key":"control","name":"Control","allocation_pct":50,"is_control":true},{"key":"treatment","name":"Treatment","allocation_pct":50,"is_control":false}]}' \
     "http://localhost:8000/api/v1/experiments/"

# Get user assignment
curl -H "Authorization: Bearer admin_token_123" \
     "http://localhost:8000/api/v1/assignments/experiments/1/assignment/dashboard-user-1"

# Record an event
curl -X POST \
     -H "Authorization: Bearer admin_token_123" \
     -H "Content-Type: application/json" \
     -d '{"experiment_id":1,"user_id":"dashboard-user-1","event_type":"page_view","properties":{"page":"/test"}}' \
     "http://localhost:8000/api/v1/events/"
```

### Using Python:
```python
import httpx

headers = {"Authorization": "Bearer admin_token_123"}

# List experiments
response = httpx.get("http://localhost:8000/api/v1/experiments/", headers=headers)
print(response.json())

# Create experiment
experiment_data = {
    "key": "my-test",
    "name": "My Test",
    "variants": [
        {"key": "control", "name": "Control", "allocation_pct": 50, "is_control": True},
        {"key": "treatment", "name": "Treatment", "allocation_pct": 50, "is_control": False}
    ]
}
response = httpx.post("http://localhost:8000/api/v1/experiments/", 
                     headers=headers, json=experiment_data)
print(response.json())
```

### Using JavaScript/Fetch:
```javascript
const headers = {
    'Authorization': 'Bearer admin_token_123',
    'Content-Type': 'application/json'
};

// List experiments
fetch('http://localhost:8000/api/v1/experiments/', { headers })
    .then(response => response.json())
    .then(data => console.log(data));

// Create experiment
const experimentData = {
    key: 'my-test',
    name: 'My Test',
    variants: [
        { key: 'control', name: 'Control', allocation_pct: 50, is_control: true },
        { key: 'treatment', name: 'Treatment', allocation_pct: 50, is_control: false }
    ]
};

fetch('http://localhost:8000/api/v1/experiments/', {
    method: 'POST',
    headers,
    body: JSON.stringify(experimentData)
})
.then(response => response.json())
.then(data => console.log(data));
```

## 📊 Available Users for Testing

You have **5 test users** available:

- `dashboard-user-0` (dashboard-user-0@example.com)
- `dashboard-user-1` (dashboard-user-1@example.com)
- `dashboard-user-2` (dashboard-user-2@example.com)
- `dashboard-user-3` (dashboard-user-3@example.com)
- `dashboard-user-4` (dashboard-user-4@example.com)

## 🔗 Quick Links

- **API Documentation**: http://localhost:8000/api/v1/docs
- **React Dashboard**: http://localhost:3001
- **Grafana Monitoring**: http://localhost:3000
- **Test Script**: Run `python3 test_api_with_auth.py` to test all endpoints

## 🧪 Test the API

Run the included test script to see all endpoints in action:

```bash
python3 test_api_with_auth.py
```

This will test:
- ✅ Health check (no auth)
- ✅ Experiments list (with all tokens)
- ✅ Users list (with all tokens)
- ✅ Analytics endpoints (no auth)
- ✅ Create new experiment (admin token)
- ✅ Get user assignment (any token)
- ✅ Record event (any token)

## 📝 Notes

- **Analytics endpoints** (`/api/v1/analytics/*`) don't require authentication
- All other endpoints require a valid Bearer token
- Make sure to include trailing slashes in URLs (e.g., `/experiments/` not `/experiments`)
- The API returns JSON responses with proper HTTP status codes
- Check the Swagger docs at `/api/v1/docs` for complete API reference
