# DataGrip Connection Guide

## 📊 **PostgreSQL Connection (Operational Database)**

### Connection Details:
- **Host**: `localhost` (or `172.21.0.6` if using container IP)
- **Port**: `5432`
- **Database**: `experiments`
- **Username**: `experiments`
- **Password**: `password`
- **Driver**: PostgreSQL

### Connection String:
```
jdbc:postgresql://localhost:5432/experiments
```

### Key Tables to Explore:
- `experiments` - All experiment definitions
- `variants` - Experiment variants with traffic allocation
- `assignments` - User assignments to variants
- `events` - Raw events (before CDC processing)
- `users` - User accounts
- `api_tokens` - API authentication tokens
- `outbox_events` - CDC events for Kafka

### Sample Queries:
```sql
-- View all experiments
SELECT * FROM experiments ORDER BY created_at DESC;

-- View experiment variants
SELECT e.name as experiment, v.name as variant, v.allocation_pct, v.is_control
FROM experiments e
JOIN variants v ON e.id = v.experiment_id
ORDER BY e.name, v.id;

-- View user assignments
SELECT e.name as experiment, v.name as variant, a.user_id, a.assigned_at
FROM assignments a
JOIN experiments e ON a.experiment_id = e.id
JOIN variants v ON a.variant_id = v.id
ORDER BY a.assigned_at DESC;

-- View recent events
SELECT * FROM events ORDER BY timestamp DESC LIMIT 10;
```

---

## ⚡ **ClickHouse Connection (Analytics Database)**

### Connection Details:
- **Host**: `localhost` (or `172.21.0.11` if using container IP)
- **Port**: `8123` (HTTP) or `9000` (Native)
- **Database**: `experiments_analytics`
- **Username**: `default` (or leave empty)
- **Password**: (leave empty)
- **Driver**: ClickHouse

### Connection String:
```
jdbc:clickhouse://localhost:8123/experiments_analytics
```

### Key Tables to Explore:
- `raw_events` - Raw events from Kafka (Kafka engine)
- `events_mv` - Materialized view of processed events
- `events_processed` - Final processed events table
- `raw_assignments` - Raw assignments from Kafka
- `experiment_reports` - Aggregated daily reports
- `experiment_daily_stats` - AggregatingMergeTree stats
- `experiments_dict` - Dictionary table for experiments
- `variants_dict` - Dictionary table for variants
- `users_dict` - Dictionary table for users

### Sample Queries:
```sql
-- View processed events
SELECT * FROM events_mv ORDER BY timestamp DESC LIMIT 10;

-- View aggregated reports
SELECT 
    experiment_name,
    variant_name,
    report_date,
    total_events,
    unique_users,
    conversion_rate,
    statistical_significance
FROM experiment_reports 
ORDER BY report_date DESC, experiment_id, variant_id;

-- View daily statistics (aggregated)
SELECT 
    experiment_id,
    variant_id,
    date,
    uniq(user_id) as unique_users,
    count() as total_events
FROM experiment_daily_stats 
GROUP BY experiment_id, variant_id, date
ORDER BY date DESC;

-- View experiment performance
SELECT 
    experiment_name,
    variant_name,
    is_control,
    avg(conversion_rate) as avg_conversion_rate,
    avg(statistical_significance) as avg_significance
FROM experiment_reports 
GROUP BY experiment_name, variant_name, is_control
ORDER BY avg_conversion_rate DESC;
```

---

## 🔧 **Setup Instructions for DataGrip:**

### 1. **Add PostgreSQL Driver:**
- Go to File → Data Sources
- Click "+" → PostgreSQL
- Download driver if needed
- Use connection details above

### 2. **Add ClickHouse Driver:**
- Go to File → Data Sources  
- Click "+" → ClickHouse
- Download driver if needed
- Use connection details above

### 3. **Test Connections:**
- Click "Test Connection" for both
- Should show "Connection successful"

### 4. **Explore Data:**
- Expand databases in the Database Explorer
- Right-click tables → "Jump to Query Console"
- Run sample queries above

---

## 📈 **Key Insights to Look For:**

### PostgreSQL (Operational):
- **Experiments**: Current experiment definitions and status
- **Assignments**: User distribution across variants
- **Events**: Raw event data before processing
- **Outbox**: CDC events being sent to Kafka

### ClickHouse (Analytics):
- **Processed Events**: Clean, structured event data
- **Aggregated Reports**: Daily performance metrics
- **Statistical Significance**: A/B test results
- **Conversion Rates**: Variant performance comparison

### Data Flow Verification:
1. **PostgreSQL** → **Kafka** → **ClickHouse**
2. Check `outbox_events` in PostgreSQL
3. Check `raw_events` in ClickHouse
4. Check `events_mv` for processed data
5. Check `experiment_reports` for aggregated metrics

---

## 🚨 **Troubleshooting:**

### If Connection Fails:
1. **Check Docker containers are running:**
   ```bash
   docker ps | grep -E "(postgres|clickhouse)"
   ```

2. **Check port mappings:**
   ```bash
   docker port experiments-postgres
   docker port experiments-clickhouse
   ```

3. **Use container IPs if localhost doesn't work:**
   - PostgreSQL: `172.21.0.6:5432`
   - ClickHouse: `172.21.0.11:8123`

### If Queries Fail:
1. **PostgreSQL**: Check table names and column names
2. **ClickHouse**: Some tables might be Kafka engines (read-only)
3. **Use materialized views** for processed data

---

## 📊 **Dashboard Integration:**

The React dashboard at `http://localhost:3000` shows the same data you can query in DataGrip, but with:
- **Real-time updates** via API calls
- **Pagination** (limit/offset parameters)
- **Filtering** by experiment, user, event type
- **Aggregated views** from ClickHouse reports

Both DataGrip and the dashboard access the same underlying data! 🎯
