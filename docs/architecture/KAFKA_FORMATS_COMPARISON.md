# ClickHouse Kafka Formats: LineAsString vs JSONEachRow for CDC

## 🔍 **Your Actual Debezium Message Format**

From your Kafka topic `experiments_events`:
```json
{
  "before": null,
  "after": {
    "id": 1,
    "aggregate_id": "1", 
    "aggregate_type": "experiment",
    "event_type": "EVENT_CREATED",
    "payload": "{\"id\": 1, \"name\": \"Test Experiment 1\", \"status\": \"ACTIVE\"}",
    "created_at": "2025-09-29T17:01:54.710715Z",
    "processed_at": null
  },
  "source": {
    "version": "2.4.2.Final",
    "connector": "postgresql", 
    "name": "experiments",
    "table": "outbox_events"
  },
  "op": "c",
  "ts_ms": 1759165315218
}
```

## 📊 **Format Comparison**

| **Aspect** | **LineAsString** | **JSONEachRow** |
|------------|------------------|-----------------|
| **Message Structure** | Any JSON structure | Flat JSON only |
| **CDC Compatibility** | ✅ **Perfect for Debezium** | ❌ **Won't work with Debezium** |
| **Nested JSON** | ✅ Handles `before`/`after` structure | ❌ Expects flat fields |
| **Schema Flexibility** | ✅ Adapts to any changes | ❌ Requires predefined columns |
| **Processing** | Manual JSON parsing | Direct column mapping |
| **Performance** | Slower (JSON parsing) | Faster (direct access) |
| **Error Handling** | Robust (skip malformed) | Fragile (schema mismatch = failure) |

## 🎯 **Why LineAsString is REQUIRED for Your CDC**

### **1. Debezium Message Structure**
Debezium sends **nested JSON** with metadata:
```json
{
  "before": {...},     // Previous state
  "after": {...},      // New state  
  "source": {...},     // Metadata
  "op": "c"            // Operation type
}
```

### **2. JSONEachRow Expects This (WON'T WORK)**
```json
// JSONEachRow expects flat structure:
{
  "id": 1,
  "user_id": "user123",
  "event_type": "conversion",
  "timestamp": "2025-01-01T12:00:00Z"
}
```

### **3. Your Outbox Pattern**
Your events are in the `payload` field as JSON strings:
```json
{
  "after": {
    "payload": "{\"id\": 1, \"experiment_id\": 1, \"user_id\": \"user123\"}"
  }
}
```

## ⚙️ **Correct Implementation**

### **✅ Using LineAsString (Recommended)**
```sql
-- Kafka consumer table
CREATE TABLE raw_events_kafka (
    message String
) ENGINE = Kafka()
SETTINGS 
    kafka_format = 'LineAsString',  -- ✅ Handles any JSON structure
    kafka_topic_list = 'experiments_events';

-- Materialized view with JSON parsing
CREATE MATERIALIZED VIEW events_processor_mv TO events_processed AS
SELECT 
    JSONExtractString(message, 'after.id') as id,
    toUInt32(JSONExtractString(message, 'after.experiment_id')) as experiment_id,
    JSONExtractString(message, 'after.user_id') as user_id,
    
    -- Handle outbox pattern (double JSON parsing)
    JSONExtractString(
        JSONExtractString(message, 'after.payload'), 
        'properties'
    ) as properties
    
FROM raw_events_kafka
WHERE JSONExtractString(message, 'op') IN ('c', 'u', 'r');
```

### **❌ Using JSONEachRow (Won't Work)**
```sql
-- This FAILS because Debezium doesn't send flat JSON
CREATE TABLE raw_events_kafka (
    id String,
    user_id String,
    event_type String
) ENGINE = Kafka()
SETTINGS 
    kafka_format = 'JSONEachRow';  -- ❌ Can't parse Debezium structure
```

## 🚀 **Performance Considerations**

### **LineAsString Performance**
- **Pros**: Handles complex structures, schema evolution, robust error handling
- **Cons**: Requires JSON parsing in materialized views (CPU overhead)
- **Best for**: CDC scenarios, complex JSON, evolving schemas

### **JSONEachRow Performance** 
- **Pros**: Direct column mapping, faster ingestion, no parsing overhead
- **Cons**: Rigid schema, breaks on structure changes, no nested support
- **Best for**: Application-generated flat JSON, stable schemas

## 🎯 **Your Analytics Pipeline Decision**

**For your CDC → ClickHouse analytics pipeline, LineAsString is the ONLY viable option because:**

1. ✅ **Debezium Compatibility**: Handles the nested CDC message format
2. ✅ **Outbox Pattern**: Can parse the double-nested JSON payload  
3. ✅ **Schema Evolution**: Won't break when you add new event types
4. ✅ **Error Resilience**: Skips malformed messages instead of failing
5. ✅ **Multi-source**: Can handle both direct events and outbox events

## 🔧 **Optimized Processing Strategy**

Your updated materialized view handles both scenarios:

```sql
-- Smart processing: Direct events OR outbox events
CASE 
    -- Direct event from events table
    WHEN JSONExtractString(message, 'after.experiment_id') != ''
    THEN JSONExtractString(message, 'after.experiment_id')
    
    -- Event from outbox_events table (extract from payload)
    WHEN JSONExtractString(message, 'after.aggregate_type') = 'event'
    THEN JSONExtractString(JSONExtractString(message, 'after.payload'), 'experiment_id')
END as experiment_id
```

## 📈 **Performance Optimization Tips**

1. **Use CASE statements**: Avoid double JSON parsing where possible
2. **Filter early**: Use WHERE clauses to reduce processing
3. **Batch processing**: Let ClickHouse batch the JSON parsing
4. **Monitor skip rate**: Track `kafka_skip_broken_messages`
5. **Index materialized columns**: Speed up common query patterns

## 🎉 **Conclusion**

**LineAsString is definitively the RIGHT choice** for your CDC analytics pipeline. It's the only format that can properly handle Debezium's nested message structure and your outbox pattern's double-encoded JSON payload.

The slight performance overhead of JSON parsing is more than offset by the reliability and flexibility it provides for real-world CDC scenarios.
