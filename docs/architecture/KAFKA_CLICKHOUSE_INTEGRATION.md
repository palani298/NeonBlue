# 🔗 Kafka ↔ ClickHouse Integration Architecture

## 🎯 **Critical Clarification: Data Flow Architecture**

**ClickHouse does NOT read directly from CDC (Debezium). The correct flow is:**

```
PostgreSQL → Debezium CDC → Kafka Topic → ClickHouse Kafka Engine → Analytics Tables
```

---

## 🏗️ **Detailed Technical Architecture**

### **Complete Data Flow Diagram**
```
┌─────────────────────┐
│   PostgreSQL        │
│   Primary Database  │
│                     │
│ ┌─────────────────┐ │
│ │ assignments     │ │
│ │ events          │ │  
│ │ outbox_events   │ │ ← Outbox Pattern
│ └─────────────────┘ │
└─────────────────────┘
           │
           ▼ WAL (Write-Ahead Log)
┌─────────────────────┐
│   Debezium CDC      │
│   Connector         │
│                     │
│ • Monitors WAL      │
│ • Captures Changes  │
│ • Creates JSON      │
│ • Publishes Events  │
└─────────────────────┘
           │
           ▼ JSON Messages
┌─────────────────────┐
│   Kafka Topic       │
│   "experiments_     │
│    events"          │
│                     │
│ • Message Queue     │
│ • Persistent        │
│ • Partitioned       │
│ • Replicated        │
└─────────────────────┘
           │
           ▼ Consumer Poll
┌─────────────────────┐
│   ClickHouse        │
│   Kafka Engine      │
│                     │
│ ┌─────────────────┐ │
│ │ raw_events_     │ │ ← Kafka Table
│ │ kafka (String)  │ │
│ └─────────────────┘ │
│           │         │
│           ▼ MV      │
│ ┌─────────────────┐ │
│ │ events_         │ │ ← Materialized View
│ │ processed       │ │
│ └─────────────────┘ │
└─────────────────────┘
```

---

## 🔧 **Technical Implementation Details**

### **1. ClickHouse Kafka Table Configuration**
```sql
-- Step 1: Create Kafka consumer table
CREATE TABLE experiments_analytics.raw_events_kafka (
    message String  -- Raw Kafka message as string
) ENGINE = Kafka()
SETTINGS 
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'experiments_events',
    kafka_group_name = 'clickhouse_analytics',
    kafka_format = 'LineAsString',          -- Each message as single string
    kafka_num_consumers = 1,                -- Number of consumer threads
    kafka_max_block_size = 1024,           -- Batch size
    kafka_poll_timeout_ms = 5000;          -- Poll timeout
```

### **2. Materialized View for Real-time Processing**
```sql
-- Step 2: Create target table for processed events
CREATE TABLE experiments_analytics.events_processed (
    id String,
    experiment_id UInt32,
    user_id String,
    variant_id UInt32,
    variant_key String,
    event_type String,
    timestamp DateTime64(3),
    assignment_at Nullable(DateTime64(3)),
    properties String,
    session_id String,
    
    -- Materialized columns for fast queries
    page String MATERIALIZED JSONExtractString(properties, 'page'),
    value Float32 MATERIALIZED toFloat32OrZero(JSONExtractString(properties, 'value')),
    score Int32 MATERIALIZED toInt32OrZero(JSONExtractString(properties, 'score')),
    
    -- Event classification flags
    is_conversion Bool MATERIALIZED event_type = 'conversion',
    is_click Bool MATERIALIZED event_type = 'click', 
    is_exposure Bool MATERIALIZED event_type = 'exposure',
    is_valid Bool MATERIALIZED timestamp >= assignment_at,
    
    -- Time partitioning columns
    event_date Date MATERIALIZED toDate(timestamp),
    event_hour UInt8 MATERIALIZED toHour(timestamp),
    
    created_at DateTime64(3),
    updated_at DateTime64(3)
) ENGINE = MergeTree()
PARTITION BY event_date
ORDER BY (experiment_id, user_id, timestamp)
SETTINGS index_granularity = 8192;

-- Step 3: Create materialized view to process Kafka messages
CREATE MATERIALIZED VIEW experiments_analytics.events_kafka_mv 
TO experiments_analytics.events_processed AS
SELECT 
    -- Extract from nested Debezium CDC JSON
    JSONExtractString(message, 'after.aggregate_id') as id,
    toUInt32(coalesce(
        toUInt32OrZero(JSONExtractString(JSONExtractString(message, 'after.payload'), 'experiment_id')), 
        1
    )) as experiment_id,
    coalesce(
        JSONExtractString(JSONExtractString(message, 'after.payload'), 'user_id'), 
        'unknown'
    ) as user_id,
    toUInt32OrZero(JSONExtractString(JSONExtractString(message, 'after.payload'), 'variant_id')) as variant_id,
    coalesce(
        JSONExtractString(JSONExtractString(message, 'after.payload'), 'variant_key'), 
        'unknown'
    ) as variant_key,
    coalesce(
        JSONExtractString(JSONExtractString(message, 'after.payload'), 'event_type'), 
        JSONExtractString(message, 'after.event_type')
    ) as event_type,
    coalesce(
        parseDateTime64BestEffortOrNull(JSONExtractString(JSONExtractString(message, 'after.payload'), 'timestamp')), 
        now64()
    ) as timestamp,
    parseDateTime64BestEffortOrNull(JSONExtractString(JSONExtractString(message, 'after.payload'), 'assignment_at')) as assignment_at,
    coalesce(
        JSONExtractString(JSONExtractString(message, 'after.payload'), 'properties'), 
        '{}'
    ) as properties,
    coalesce(
        JSONExtractString(JSONExtractString(message, 'after.payload'), 'session_id'), 
        'unknown'
    ) as session_id,
    parseDateTime64BestEffortOrNull(JSONExtractString(message, 'after.created_at')) as created_at,
    parseDateTime64BestEffortOrNull(JSONExtractString(message, 'after.updated_at')) as updated_at
FROM experiments_analytics.raw_events_kafka
WHERE JSONExtractString(message, 'op') = 'c'  -- Only process INSERT operations
  AND JSONExtractString(message, 'after.aggregate_id') != ''  -- Valid events only
  AND JSONExtractString(message, 'after.aggregate_type') = 'event';  -- Event type only
```

---

## 📨 **Message Format Handling**

### **Debezium CDC Message Structure**
```json
{
  "before": null,                    // Always null for INSERT
  "after": {                         // New record data
    "id": 16,
    "aggregate_id": "event_866af50b",
    "aggregate_type": "event", 
    "event_type": "EVENT_CREATED",
    "payload": "{                    // Nested JSON string!
      \"id\": \"event_866af50b\",
      \"experiment_id\": 1,
      \"user_id\": \"test_user_123\",
      \"variant_id\": 2,
      \"variant_key\": \"control\",
      \"event_type\": \"conversion\",
      \"timestamp\": \"2025-09-29T21:18:10.060313+00:00\",
      \"assignment_at\": \"2025-09-29T21:17:25.060313+00:00\",
      \"properties\": \"{\\\"value\\\": 39.99, \\\"currency\\\": \\\"USD\\\"}\",
      \"session_id\": \"session_123\"
    }",
    "created_at": "2025-09-29T21:18:10.060313Z",
    "processed_at": null
  },
  "source": {                       // CDC metadata
    "version": "2.4.2.Final",
    "connector": "postgresql",
    "name": "experiments",
    "ts_ms": 1759180645480,
    "snapshot": "false",
    "db": "experiments",
    "sequence": "[\"27337592\",\"27340424\"]",
    "schema": "public", 
    "table": "outbox_events",
    "txId": 762,
    "lsn": 27340424
  },
  "op": "c",                        // Operation: c=create, u=update, d=delete
  "ts_ms": 1759180645854,           // Kafka message timestamp
  "transaction": null
}
```

### **Key JSON Processing Challenges**

#### **1. Double-nested JSON**
```sql
-- Problem: payload is JSON string inside JSON object
JSONExtractString(message, 'after.payload')  
-- Returns: "{\"experiment_id\": 1, \"user_id\": \"test\"}"

-- Solution: Extract twice
JSONExtractString(JSONExtractString(message, 'after.payload'), 'experiment_id')
-- Returns: "1" (as string, needs casting)
```

#### **2. Type Conversion**
```sql
-- Problem: All JSON values are strings
JSONExtractString(..., 'experiment_id')  -- Returns "1" (string)

-- Solution: Safe type conversion
toUInt32OrZero(JSONExtractString(..., 'experiment_id'))  -- Returns 1 (UInt32)
```

#### **3. Null Handling**
```sql
-- Problem: Missing or null values crash queries
JSONExtractString(..., 'optional_field')  -- May return empty string

-- Solution: Use coalesce with defaults
coalesce(JSONExtractString(..., 'optional_field'), 'default_value')
```

---

## ⚡ **Performance Optimizations**

### **1. Consumer Configuration**
```sql
-- Optimize Kafka consumption
SETTINGS 
    kafka_num_consumers = 4,           -- Parallel consumers for throughput
    kafka_max_block_size = 8192,       -- Larger batches
    kafka_poll_timeout_ms = 1000,      -- Faster polling
    kafka_flush_interval_ms = 7500;    -- Batch processing interval
```

### **2. Materialized Column Strategy**
```sql
-- Pre-compute expensive operations
page String MATERIALIZED JSONExtractString(properties, 'page'),
value Float32 MATERIALIZED toFloat32OrZero(JSONExtractString(properties, 'value')),

-- Event type flags for fast filtering
is_conversion Bool MATERIALIZED event_type = 'conversion',
is_click Bool MATERIALIZED event_type = 'click',

-- Time-based partitioning
event_date Date MATERIALIZED toDate(timestamp),
event_hour UInt8 MATERIALIZED toHour(timestamp)
```

### **3. Query Optimization**
```sql
-- Fast queries using materialized columns
SELECT 
    variant_key,
    count() as total_events,
    countIf(is_conversion) as conversions,  -- Uses materialized column
    sum(value) as revenue,                  -- Uses materialized column
    avgIf(score, is_conversion) as avg_score
FROM events_processed
WHERE event_date = today()                  -- Uses partition pruning
  AND experiment_id = 1                     -- Uses primary key
GROUP BY variant_key;
```

---

## 🔍 **Monitoring & Troubleshooting**

### **Check Kafka Consumer Status**
```sql
-- Check if Kafka table is consuming
SELECT name, is_readonly, total_rows 
FROM system.tables 
WHERE name = 'raw_events_kafka';

-- Monitor materialized view processing
SELECT 
    table, 
    last_exception,
    rows_read,
    bytes_read
FROM system.part_log 
WHERE table = 'events_processed' 
ORDER BY event_time DESC 
LIMIT 10;
```

### **Consumer Group Management**
```bash
# Check consumer group status in Kafka
docker exec experiments-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe \
  --group clickhouse_analytics

# Reset consumer group if needed (CAUTION: Will reprocess all messages)
docker exec experiments-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --reset-offsets \
  --group clickhouse_analytics \
  --topic experiments_events \
  --to-earliest \
  --execute
```

### **Common Issues & Solutions**

#### **1. No Messages Being Processed**
```sql
-- Restart Kafka consumer
DETACH TABLE raw_events_kafka;
ATTACH TABLE raw_events_kafka;

-- Check for errors
SELECT * FROM system.kafka_consumers;
```

#### **2. JSON Parsing Errors**  
```sql
-- Test JSON extraction on sample data
SELECT 
    message,
    JSONExtractString(message, 'after.aggregate_id') as id,
    JSONExtractString(message, 'op') as operation
FROM raw_events_kafka 
LIMIT 1;
```

#### **3. Materialized View Not Working**
```sql
-- Check materialized view status
SELECT name, engine, create_table_query 
FROM system.tables 
WHERE name = 'events_kafka_mv';

-- Recreate if necessary
DROP VIEW events_kafka_mv;
-- Recreate with correct query...
```

---

## 🎯 **Key Takeaways**

### **✅ Correct Architecture Understanding**
1. **ClickHouse reads from Kafka**, not directly from Debezium CDC
2. **Kafka acts as message broker** between Debezium and ClickHouse  
3. **Debezium publishes to Kafka**, ClickHouse consumes from Kafka
4. **Materialized Views** process incoming Kafka messages in real-time

### **✅ Benefits of This Design**
- **Decoupling**: Components can scale independently
- **Reliability**: Kafka provides message persistence and replay
- **Performance**: Asynchronous processing doesn't block PostgreSQL
- **Flexibility**: Multiple consumers can read the same stream
- **Scalability**: Kafka handles high-throughput message streaming

### **✅ Technical Implementation**
- **Kafka Table Engine** in ClickHouse handles message consumption
- **Materialized Views** provide real-time stream processing
- **JSON Processing** handles complex Debezium CDC format
- **Consumer Groups** manage offset tracking and load balancing

**This architecture ensures reliable, scalable, real-time data pipeline from PostgreSQL to ClickHouse analytics!** 🚀
