# 🔐 API Tokens Setup Guide

## 📋 Generated Tokens Summary

I've generated 8 secure API tokens for different access levels:

### 🔑 Available Tokens

| Token Type | Purpose | Scopes | Rate Limit | Expires |
|------------|---------|---------|------------|---------|
| **ADMIN** | Full administrative access | `*` (all permissions) | 1000 req/min | 365 days |
| **READONLY** | Read-only access | experiments:read, assignments:read, users:read, analytics:read, events:read | 500 req/min | 180 days |
| **WRITE** | Create/update access | experiments:read/write, assignments:read/write, users:read/write, events:read/write, analytics:read | 300 req/min | 180 days |
| **ANALYTICS** | Analytics focused | analytics:read/write, experiments:read, events:read, results:read | 200 req/min | 90 days |
| **SERVICE** | Inter-service communication | experiments:read/write, assignments:read/write, events:read/write, users:read/write | 2000 req/min | 365 days |
| **DEMO** | Demo/testing purposes | experiments:read, assignments:read, analytics:read, events:read | 100 req/min | 30 days |
| **EXTERNAL** | External API access | experiments:read, assignments:read, events:write, results:read | 150 req/min | 90 days |
| **MONITORING** | Health checks | health:read, metrics:read, status:read | 1000 req/min | 365 days |

### 🔑 Token Values

```bash
# Admin Token (Full Access)
ADMIN_TOKEN="admin_FYvh0whTsAXiWDzyq-lJ3alUPlH2j5vnN5V9mdL-"

# Read-Only Token
READONLY_TOKEN="readonly_yI9Kf1N1CHDnMNOyvYc_Ll1VVRbldTMq"

# Write Access Token
WRITE_TOKEN="write_EEpGsvCx9QnPgnMOfarQmOW1mcqwj7g6"

# Analytics Token
ANALYTICS_TOKEN="analytics_zF6mbjnVkLX16wa3tpKZoQukIvNZDICp"

# Service Token
SERVICE_TOKEN="service_2fIsuvS3OkelYHBCch3GaS_8cY2ijp10eEG7o36l"

# Demo Token
DEMO_TOKEN="demo_OErxSXNX_a5MKMXOtfm86xfc"

# External Token
EXTERNAL_TOKEN="ext_v5hu0oqO476IaHcmdrNTGZhkp2yCMk5ZALqP"

# Monitoring Token
MONITORING_TOKEN="monitor_0lQ8u2SyEaDKtQWGW5eZDBobeZg1"
```

## 🚀 Quick Setup (Option 1: Environment Variables)

Add to your `.env` file or environment:

```bash
# Update BEARER_TOKENS in your .env file
BEARER_TOKENS=["admin_FYvh0whTsAXiWDzyq-lJ3alUPlH2j5vnN5V9mdL-", "readonly_yI9Kf1N1CHDnMNOyvYc_Ll1VVRbldTMq", "write_EEpGsvCx9QnPgnMOfarQmOW1mcqwj7g6", "analytics_zF6mbjnVkLX16wa3tpKZoQukIvNZDICp", "service_2fIsuvS3OkelYHBCch3GaS_8cY2ijp10eEG7o36l", "demo_OErxSXNX_a5MKMXOtfm86xfc", "ext_v5hu0oqO476IaHcmdrNTGZhkp2yCMk5ZALqP", "monitor_0lQ8u2SyEaDKtQWGW5eZDBobeZg1"]
```

## 🗄️ Database Setup (Option 2: Database Storage)

If you want proper token management with expiration and scopes:

```bash
# Install tokens in database
psql -d experiments -f api_tokens.sql
```

## 🧪 Testing Your Tokens

### Test Admin Token (Full Access)
```bash
curl -X GET \
  'http://localhost:8000/api/v1/experiments/?limit=5' \
  -H 'Authorization: Bearer admin_FYvh0whTsAXiWDzyq-lJ3alUPlH2j5vnN5V9mdL-' \
  -H 'Accept: application/json'
```

### Test Read-Only Token
```bash
curl -X GET \
  'http://localhost:8000/api/v1/experiments/?limit=5' \
  -H 'Authorization: Bearer readonly_yI9Kf1N1CHDnMNOyvYc_Ll1VVRbldTMq' \
  -H 'Accept: application/json'
```

### Test Demo Token
```bash
curl -X GET \
  'http://localhost:8000/api/v1/experiments/?limit=5' \
  -H 'Authorization: Bearer demo_OErxSXNX_a5MKMXOtfm86xfc' \
  -H 'Accept: application/json'
```

### Test Analytics Token
```bash
curl -X GET \
  'http://localhost:8000/api/v1/analytics/' \
  -H 'Authorization: Bearer analytics_zF6mbjnVkLX16wa3tpKZoQukIvNZDICp' \
  -H 'Accept: application/json'
```

## ⚡ Quick Start (Immediate Use)

**For your demo right now**, use this command with the admin token:

```bash
curl -X 'GET' \
  'http://localhost:8000/api/v1/experiments/?limit=100&offset=0' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer admin_FYvh0whTsAXiWDzyq-lJ3alUPlH2j5vnN5V9mdL-'
```

## 🔧 Implementation Steps

1. **Quick Setup (for immediate demo):**
   ```bash
   # Update your docker-compose environment
   export BEARER_TOKENS='["admin_FYvh0whTsAXiWDzyq-lJ3alUPlH2j5vnN5V9mdL-", "readonly_yI9Kf1N1CHDnMNOyvYc_Ll1VVRbldTMq", "demo_OErxSXNX_a5MKMXOtfm86xfc"]'
   
   # Restart API service
   docker-compose -f config/docker-compose.yml restart api
   ```

2. **Full Database Setup (recommended for production):**
   ```bash
   # Load tokens into database
   psql -h localhost -p 5432 -U experiments -d experiments -f api_tokens.sql
   
   # Restart API to pick up changes
   docker-compose -f config/docker-compose.yml restart api
   ```

## 🎯 Usage Examples

### For Different Scenarios:

- **Demo/Testing**: Use `demo_OErxSXNX_a5MKMXOtfm86xfc`
- **Admin Operations**: Use `admin_FYvh0whTsAXiWDzyq-lJ3alUPlH2j5vnN5V9mdL-`
- **Read-Only Access**: Use `readonly_yI9Kf1N1CHDnMNOyvYc_Ll1VVRbldTMq`
- **Service Integration**: Use `service_2fIsuvS3OkelYHBCch3GaS_8cY2ijp10eEG7o36l`
- **Analytics Dashboard**: Use `analytics_zF6mbjnVkLX16wa3tpKZoQukIvNZDICp`

## 🔒 Security Notes

- ✅ All tokens are cryptographically secure (32-40 characters)
- ✅ Each token has specific scopes and rate limits
- ✅ Tokens have expiration dates
- ✅ Tokens can be revoked by setting `is_active = false`
- ✅ All tokens are prefixed by type for easy identification

## 📁 Generated Files

- `generated_api_tokens.json` - Complete token configuration
- `api_tokens.sql` - Database setup script  
- `api_tokens.env` - Environment configuration

Your tokens are ready to use! 🎉

