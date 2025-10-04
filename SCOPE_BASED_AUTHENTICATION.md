# Scope-Based Authentication Implementation

## Overview

The API has been updated to implement proper scope-based authentication, ensuring that different tokens can only access specific API endpoints based on their assigned scopes.

## How It Works

### 1. Token Validation Process

When a request is made with a Bearer token, the system:

1. **Checks Static Tokens** (for development): If the token is in `settings.bearer_tokens`, it gets wildcard scope `["*"]`
2. **Checks Redis Cache**: Looks for cached token data (5-minute TTL)
3. **Checks Database**: Validates the token against the `api_tokens` table
4. **Validates Expiration**: Ensures the token hasn't expired
5. **Returns Token Data**: Including scopes, rate limits, and metadata

### 2. Scope Enforcement

Each API endpoint now uses `auth.require_scope("scope_name")` instead of `auth.verify_token()` to enforce specific scope requirements.

## API Endpoint Scope Requirements

### Experiments (`/experiments/*`)
- **Read Operations**: `experiments:read`
  - `GET /experiments/` - List experiments
  - `GET /experiments/{id}` - Get experiment details
- **Write Operations**: `experiments:write`
  - `POST /experiments/` - Create experiment
  - `PATCH /experiments/{id}` - Update experiment
  - `POST /experiments/{id}/activate` - Activate experiment
  - `POST /experiments/{id}/pause` - Pause experiment
  - `DELETE /experiments/{id}` - Delete experiment
  - `POST /experiments/bulk` - Bulk create experiments

### Assignments (`/assignments/*`)
- **Read Operations**: `assignments:read`
  - `GET /assignments/experiments/{id}/assignment/{user_id}` - Get assignment
  - `POST /assignments/bulk` - Get bulk assignments
  - `GET /assignments/list` - List assignments
  - `GET /assignments/{id}` - Get assignment by ID
- **Write Operations**: `assignments:write`
  - `PATCH /assignments/{id}` - Update assignment
  - `DELETE /assignments/{id}` - Delete assignment
  - `POST /assignments/bulk/create` - Bulk create assignments
  - `PATCH /assignments/bulk/update` - Bulk update assignments
  - `DELETE /assignments/bulk/delete` - Bulk delete assignments

### Events (`/events/*`)
- **Read Operations**: `events:read`
  - `GET /events/{id}` - Get event by ID
  - `GET /events/` - List events
- **Write Operations**: `events:write`
  - `POST /events/` - Record event
  - `POST /events/batch` - Record batch events
  - `PATCH /events/{id}` - Update event
  - `DELETE /events/{id}` - Delete event

### Results/Analytics (`/results/*`)
- **Read Operations**: `results:read`
  - `GET /results/experiments/{id}/results` - Get experiment results

### Users (`/users/*`)
- **Read Operations**: `users:read`
  - `GET /users/{id}` - Get user by ID
  - `GET /users/` - List users
- **Write Operations**: `users:write`
  - `POST /users/` - Create user
  - `PATCH /users/{id}` - Update user
  - `DELETE /users/{id}` - Delete user

### Variants (`/variants/*`)
- **Read Operations**: `variants:read`
  - `GET /variants/{id}` - Get variant by ID
  - `GET /variants/` - List variants
- **Write Operations**: `variants:write`
  - `POST /variants/` - Create variant
  - `PATCH /variants/{id}` - Update variant
  - `DELETE /variants/{id}` - Delete variant

### Analytics (`/analytics/*`)
- **Read Operations**: `analytics:read`
  - `GET /analytics/experiments` - Get experiments data
  - `GET /analytics/variants` - Get variants data
  - `GET /analytics/assignments` - Get assignments data
  - `GET /analytics/events` - Get events data
  - `GET /analytics/users` - Get users data
  - `GET /analytics/reports` - Get experiment reports
  - `GET /analytics/daily-stats` - Get daily statistics
  - `GET /analytics/summary` - Get data summary

### API Tokens (`/api-tokens/*`)
- **Admin Operations**: `admin`
  - `POST /api-tokens/` - Create API token
  - `GET /api-tokens/{id}` - Get API token
  - `GET /api-tokens/` - List API tokens
  - `PATCH /api-tokens/{id}` - Update API token
  - `DELETE /api-tokens/{id}` - Delete API token
  - `POST /api-tokens/{id}/regenerate` - Regenerate API token

### Data Management (`/data-management/*`)
- **Admin Operations**: `admin`
  - `GET /data-management/stats` - Get data statistics
  - `POST /data-management/cleanup` - Clean up old data
  - `GET /data-management/retention-policies` - Get retention policies

## Token Scopes

Based on your `generated_api_tokens.json`, here are the available token types:

### 1. Admin Token
- **Scopes**: `["*"]` (full access)
- **Use Case**: Full administrative access to all resources
- **Rate Limit**: 1000 requests/minute

### 2. Read-Only Token
- **Scopes**: `["experiments:read", "assignments:read", "users:read", "analytics:read", "events:read"]`
- **Use Case**: Read-only access to experiments, assignments, and analytics
- **Rate Limit**: 500 requests/minute

### 3. Write Access Token
- **Scopes**: `["experiments:read", "experiments:write", "assignments:read", "assignments:write", "users:read", "users:write", "events:read", "events:write", "analytics:read"]`
- **Use Case**: Create and update experiments, assignments, and events
- **Rate Limit**: 300 requests/minute

### 4. Analytics Token
- **Scopes**: `["analytics:read", "analytics:write", "experiments:read", "events:read", "results:read"]`
- **Use Case**: Access to analytics data and reporting endpoints
- **Rate Limit**: 200 requests/minute

### 5. Service Token
- **Scopes**: `["experiments:read", "experiments:write", "assignments:read", "assignments:write", "events:read", "events:write", "users:read", "users:write"]`
- **Use Case**: Inter-service communication and automated processes
- **Rate Limit**: 2000 requests/minute

### 6. Demo Token
- **Scopes**: `["experiments:read", "assignments:read", "analytics:read", "events:read"]`
- **Use Case**: Limited access for demonstrations and testing
- **Rate Limit**: 100 requests/minute

### 7. External API Token
- **Scopes**: `["experiments:read", "assignments:read", "events:write", "results:read"]`
- **Use Case**: External partner/integration access
- **Rate Limit**: 150 requests/minute

### 8. Monitoring Token
- **Scopes**: `["health:read", "metrics:read", "status:read"]`
- **Use Case**: Health checks and monitoring endpoints
- **Rate Limit**: 1000 requests/minute

## Error Responses

When a token doesn't have the required scope, the API returns:

```json
{
  "detail": "Token does not have required scope: experiments:write"
}
```

With HTTP status code `403 Forbidden`.

## Benefits

1. **Granular Access Control**: Different tokens can access different parts of the API
2. **Security**: Prevents unauthorized access to sensitive operations
3. **Rate Limiting**: Each token can have custom rate limits
4. **Audit Trail**: Token usage is tracked with `last_used_at` timestamps
5. **Expiration**: Tokens can have expiration dates
6. **Caching**: Token validation is cached for performance

## Example Usage

```bash
# Using analytics token to get experiment results
curl -H "Authorization: Bearer analytics_zF6mbjnVkLX16wa3tpKZoQukIvNZDICp" \
     https://api.example.com/api/v1/results/experiments/123/results

# This will work because analytics token has "results:read" scope

# Using readonly token to create an experiment (will fail)
curl -X POST -H "Authorization: Bearer readonly_yI9Kf1N1CHDnMNOyvYc_Ll1VVRbldTMq" \
     -H "Content-Type: application/json" \
     -d '{"name": "New Experiment"}' \
     https://api.example.com/api/v1/experiments/

# This will fail with 403 Forbidden because readonly token doesn't have "experiments:write" scope
```

## Migration Notes

- All existing API endpoints now require proper scope validation
- Static tokens (for development) still work with wildcard `["*"]` scope
- The `require_scope()` decorator automatically calls `verify_token()` internally
- Rate limiting is still applied per token
- Token caching (Redis) is still active for performance
