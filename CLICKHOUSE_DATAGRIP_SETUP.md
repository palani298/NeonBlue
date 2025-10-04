# ClickHouse DataGrip Connection Setup

## 🚀 **Quick Setup Steps**

### 1. **Start Docker Desktop**
- Open Docker Desktop application
- Wait for green "running" status

### 2. **Start ClickHouse Container**
```bash
# From project root
docker compose -f config/docker-compose.yml up -d clickhouse
```

### 3. **Verify ClickHouse is Running**
```bash
# Check container status
docker ps | grep clickhouse

# Test HTTP interface
curl http://localhost:8123/ping
# Should return: Ok.

# Test with query
curl 'http://localhost:8123/?query=SELECT%201'
# Should return: 1
```

### 4. **DataGrip Connection Settings**

#### **Basic Settings:**
- **Database Type**: ClickHouse
- **Host**: `localhost`
- **Port**: `8123` (HTTP interface)
- **Database**: `experiments`
- **Authentication**: **"No Authentication"** (recommended) OR "User & Password"
- **Username**: `default` (if using User & Password)
- **Password**: (leave completely empty)

#### **Connection URL:**
```
jdbc:clickhouse://localhost:8123/experiments
```

#### **Advanced Settings (if needed):**
- **Connection Timeout**: 30000
- **Socket Timeout**: 30000
- **SSL**: Disabled (for local development)

### 5. **Test Queries to Run**

Once connected, try these queries to verify everything works:

#### **Basic Connection Test:**
```sql
SELECT 1 as test
```

#### **Check Databases:**
```sql
SHOW DATABASES
```

#### **Check Tables (if any exist):**
```sql
SHOW TABLES
```

#### **Create Test Table:**
```sql
CREATE TABLE IF NOT EXISTS test_table (
    id UInt32,
    name String,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY id
```

#### **Insert Test Data:**
```sql
INSERT INTO test_table (id, name) VALUES (1, 'test')
```

#### **Query Test Data:**
```sql
SELECT * FROM test_table
```

## 🔧 **Troubleshooting**

### **Connection Refused Error:**
1. **Check Docker is running:**
   ```bash
   docker ps
   ```

2. **Check ClickHouse container:**
   ```bash
   docker ps | grep clickhouse
   ```

3. **Check container logs:**
   ```bash
   docker logs experiments-clickhouse
   ```

4. **Restart container:**
   ```bash
   docker compose -f config/docker-compose.yml restart clickhouse
   ```

### **Port Already in Use:**
If port 8123 is already in use:
```bash
# Check what's using the port
lsof -i :8123

# Kill the process or change port in docker-compose.yml
```

### **Authentication Issues:**
- ClickHouse default user is `default` with no password
- **DataGrip Fix**: Use "No Authentication" instead of "User & Password"
- If using "User & Password", leave password field completely empty
- Alternative: Try connection URL: `jdbc:clickhouse://localhost:8123/experiments?user=default&password=`

### **Database Not Found:**
- ClickHouse creates databases automatically when you first use them
- You can connect without specifying a database name
- Default database is `default`

## 📊 **Expected ClickHouse Schema**

Based on your project setup, you should see these tables once the CDC pipeline is running:

### **Tables to Look For:**
- `raw_events` - Raw events from Kafka
- `events_mv` - Materialized view of processed events
- `events_processed` - Final processed events
- `experiment_reports` - Daily aggregated reports
- `experiment_daily_stats` - Time-series statistics

### **Sample Queries for Your Data:**
```sql
-- Check if events are flowing
SELECT count() as event_count FROM raw_events

-- View processed events
SELECT * FROM events_mv ORDER BY timestamp DESC LIMIT 10

-- Check experiment reports
SELECT * FROM experiment_reports ORDER BY report_date DESC LIMIT 10
```

## 🎯 **Next Steps**

1. **Connect successfully** using the settings above
2. **Run test queries** to verify functionality
3. **Check if CDC pipeline** is creating tables automatically
4. **Explore existing data** if any tables exist
5. **Create test data** to verify write operations

## 📞 **If Still Having Issues**

1. **Check Docker Desktop** is fully started
2. **Verify container** is running: `docker ps | grep clickhouse`
3. **Check logs**: `docker logs experiments-clickhouse`
4. **Try HTTP interface** directly: `curl http://localhost:8123/ping`
5. **Use container IP** instead of localhost if needed

The ClickHouse container should be accessible on `localhost:8123` once Docker is running properly! 🚀
