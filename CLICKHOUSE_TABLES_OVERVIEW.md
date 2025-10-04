# ClickHouse Tables & Materialized Views Overview

## 📊 **Database Structure**

Your ClickHouse instance contains multiple databases with different purposes:

### **Databases Available:**
- `experiments` - Basic experiment data
- `experiments_analytics` - Main analytics database (recommended for queries)
- `default` - Default ClickHouse database
- `system` - ClickHouse system tables
- `INFORMATION_SCHEMA` - Standard information schema

---

## 🗄️ **experiments_analytics Database (Main Analytics)**

This is your primary analytics database with the most comprehensive tables:

### **📋 Tables:**

#### **1. events_processed** (Main Events Table)
- **Type**: MergeTree table
- **Purpose**: Final processed events with enriched data
- **Row Count**: 14 rows
- **Schema**:
  ```sql
  id                     String
  experiment_id          UInt32
  user_id                String
  variant_id             Nullable(UInt32)
  variant_key            Nullable(String)
  event_type             String
  timestamp              DateTime64(3)
  assignment_at          Nullable(DateTime64(3))
  properties             String
  session_id             Nullable(String)
  request_id             Nullable(String)
  created_at             DateTime64(3)
  updated_at             DateTime64(3)
  
  -- Materialized Columns (computed automatically):
  event_date             Date (MATERIALIZED toDate(timestamp))
  event_hour             UInt8 (MATERIALIZED toHour(timestamp))
  page                   Nullable(String) (MATERIALIZED JSONExtractString(properties, 'page'))
  value                  Nullable(Float32) (MATERIALIZED JSONExtractFloat(properties, 'value'))
  score                  Nullable(Int32) (MATERIALIZED JSONExtractInt(properties, 'score'))
  is_conversion          Bool (MATERIALIZED event_type = 'conversion')
  is_exposure            Bool (MATERIALIZED event_type = 'exposure')
  is_click               Bool (MATERIALIZED event_type = 'click')
  is_valid               Bool (MATERIALIZED if(assignment_at IS NOT NULL, timestamp >= assignment_at, true))
  ```

#### **2. experiment_reports** (Aggregated Reports)
- **Type**: MergeTree table
- **Purpose**: Daily aggregated experiment performance reports
- **Row Count**: 10 rows
- **Schema**:
  ```sql
  experiment_id              UInt32
  variant_id                 UInt32
  variant_name               String
  is_control                 Bool
  experiment_name            String
  report_date                Date
  total_events               UInt64
  unique_users               UInt64
  total_score                UInt64
  avg_score                  Float32
  conversion_rate            Float32
  avg_session_duration       Float32
  statistical_significance   Float32
  confidence_interval_lower  Float32
  confidence_interval_upper  Float32
  ```

### **🔄 Materialized Views:**

#### **1. events_kafka_mv** (Kafka Materialized View)
- **Type**: Materialized View
- **Purpose**: Processes raw Kafka events into the events_processed table
- **Source**: Kafka topic data
- **Target**: events_processed table

#### **2. events_mv** (Events Materialized View)
- **Type**: Materialized View
- **Purpose**: Simplified view of events for basic queries
- **Schema**:
  ```sql
  id             String
  experiment_id  UInt32
  user_id        String
  variant_id     UInt32
  event_type     String
  timestamp      DateTime64(3)
  properties     String
  ```

### **📡 Kafka Integration Tables:**

#### **3. raw_events_kafka** (Kafka Engine Table)
- **Type**: Kafka Engine
- **Purpose**: Direct connection to Kafka topic for raw event ingestion
- **Read-only**: Yes (managed by Kafka)

---

## 🗄️ **experiments Database**

### **📋 Tables:**

#### **1. events** (Basic Events)
- **Type**: Basic table
- **Purpose**: Simple event storage
- **Schema**: Basic event structure

---

## 🔍 **Useful Queries for DataGrip**

### **Sample Data Exploration:**

#### **1. View All Processed Events:**
```sql
SELECT 
    experiment_id,
    user_id,
    variant_key,
    event_type,
    timestamp,
    is_conversion,
    page,
    value
FROM experiments_analytics.events_processed 
ORDER BY timestamp DESC 
LIMIT 10;
```

#### **2. View Experiment Reports:**
```sql
SELECT 
    experiment_name,
    variant_name,
    is_control,
    report_date,
    total_events,
    unique_users,
    conversion_rate,
    statistical_significance
FROM experiments_analytics.experiment_reports 
ORDER BY report_date DESC, experiment_id, variant_id;
```

#### **3. Event Type Distribution:**
```sql
SELECT 
    event_type,
    count() as event_count,
    uniq(user_id) as unique_users
FROM experiments_analytics.events_processed 
GROUP BY event_type 
ORDER BY event_count DESC;
```

#### **4. Daily Event Trends:**
```sql
SELECT 
    event_date,
    count() as total_events,
    uniq(user_id) as unique_users,
    countIf(is_conversion) as conversions
FROM experiments_analytics.events_processed 
GROUP BY event_date 
ORDER BY event_date DESC;
```

#### **5. Experiment Performance Summary:**
```sql
SELECT 
    experiment_name,
    variant_name,
    is_control,
    avg(conversion_rate) as avg_conversion_rate,
    avg(statistical_significance) as avg_significance,
    sum(total_events) as total_events,
    sum(unique_users) as total_users
FROM experiments_analytics.experiment_reports 
GROUP BY experiment_name, variant_name, is_control 
ORDER BY avg_conversion_rate DESC;
```

---

## 📊 **Data Flow Architecture**

```
PostgreSQL → Debezium CDC → Kafka → ClickHouse
    │                              │
    │                              ▼
    │                    raw_events_kafka (Kafka Engine)
    │                              │
    │                              ▼
    │                    events_kafka_mv (Materialized View)
    │                              │
    │                              ▼
    │                    events_processed (Main Table)
    │                              │
    │                              ▼
    │                    events_mv (Simplified View)
    │                              │
    │                              ▼
    │                    experiment_reports (Aggregated)
```

---

## 🎯 **Recommended Queries for Analysis**

### **For Experiment Analysis:**
- Use `experiment_reports` for high-level performance metrics
- Use `events_processed` for detailed event analysis
- Use `events_mv` for simple event queries

### **For Real-time Monitoring:**
- Query `events_processed` with recent timestamps
- Use materialized columns like `is_conversion`, `is_exposure`
- Filter by `event_date` for daily analysis

### **For Performance Optimization:**
- Use `experiment_reports` for statistical significance
- Use `events_processed` for conversion funnel analysis
- Use materialized columns for fast filtering

---

## 🔧 **DataGrip Connection Tips**

1. **Connect to**: `experiments_analytics` database (most comprehensive)
2. **Start with**: `experiment_reports` table (aggregated data)
3. **Explore**: `events_processed` table (detailed events)
4. **Use**: Materialized views for simplified queries

Your ClickHouse setup is working perfectly with 14 processed events and 10 experiment reports! 🎉

