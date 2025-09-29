-- Simplified ClickHouse Analytics Setup
-- Focus on core functionality first, add complexity later

-- =============================================================================
-- 1. CREATE DATABASE
-- =============================================================================
CREATE DATABASE IF NOT EXISTS experiments_analytics;

USE experiments_analytics;

-- =============================================================================
-- 2. KAFKA CONSUMER TABLE (Raw CDC Data)
-- =============================================================================

-- Raw events from Kafka (Debezium CDC format)
CREATE TABLE IF NOT EXISTS raw_events_kafka (
    message String
) ENGINE = Kafka()
SETTINGS 
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'experiments_events',
    kafka_group_name = 'clickhouse_events_consumer',
    kafka_format = 'LineAsString',
    kafka_skip_broken_messages = 1000;

-- =============================================================================
-- 3. PROCESSED EVENTS TABLE (Clean, structured data)
-- =============================================================================

CREATE TABLE IF NOT EXISTS events_processed (
    id String,
    experiment_id UInt32,
    user_id String,
    variant_id Nullable(UInt32),
    variant_key Nullable(String),
    event_type String,
    timestamp DateTime64(3),
    assignment_at Nullable(DateTime64(3)),
    properties String,
    session_id Nullable(String),
    request_id Nullable(String),
    created_at DateTime64(3),
    updated_at DateTime64(3),
    
    -- Computed columns for analytics
    event_date Date MATERIALIZED toDate(timestamp),
    event_hour UInt8 MATERIALIZED toHour(timestamp),
    
    -- JSON property extraction
    page Nullable(String) MATERIALIZED JSONExtractString(properties, 'page'),
    value Nullable(Float32) MATERIALIZED JSONExtractFloat(properties, 'value'),
    score Nullable(Int32) MATERIALIZED JSONExtractInt(properties, 'score'),
    
    -- Event type flags
    is_conversion Bool MATERIALIZED event_type = 'conversion',
    is_exposure Bool MATERIALIZED event_type = 'exposure',
    is_click Bool MATERIALIZED event_type = 'click',
    
    -- Validity check
    is_valid Bool MATERIALIZED if(assignment_at IS NOT NULL, timestamp >= assignment_at, true)
    
) ENGINE = MergeTree()
ORDER BY (experiment_id, event_date, user_id, timestamp)
PARTITION BY toYYYYMM(event_date);

-- =============================================================================
-- 4. ASSIGNMENTS TABLE (From CDC)
-- =============================================================================

CREATE TABLE IF NOT EXISTS assignments_processed (
    id String,
    experiment_id UInt32,
    user_id String,
    variant_id UInt32,
    variant_key Nullable(String),
    assigned_at DateTime64(3),
    enrolled_at Nullable(DateTime64(3)),
    source Nullable(String),
    created_at DateTime64(3),
    updated_at DateTime64(3),
    
    assignment_date Date MATERIALIZED toDate(assigned_at)
    
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (experiment_id, user_id)
PARTITION BY toYYYYMM(assignment_date);

-- =============================================================================
-- 5. MATERIALIZED VIEW: Process CDC JSON → Events
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS events_processor_mv TO events_processed AS
SELECT 
    -- Handle both direct events and outbox events
    CASE 
        WHEN JSONExtractString(message, 'after.id') != '' AND JSONExtractString(message, 'after.experiment_id') != ''
        THEN JSONExtractString(message, 'after.id')
        WHEN JSONExtractString(message, 'after.aggregate_type') = 'event' 
        THEN JSONExtractString(JSONExtractString(message, 'after.payload'), 'id')
        ELSE ''
    END as id,
    
    CASE 
        WHEN JSONExtractString(message, 'after.experiment_id') != ''
        THEN toUInt32(JSONExtractString(message, 'after.experiment_id'))
        WHEN JSONExtractString(message, 'after.aggregate_type') = 'event'
        THEN toUInt32(JSONExtractString(JSONExtractString(message, 'after.payload'), 'experiment_id'))
        ELSE 0
    END as experiment_id,
    
    CASE 
        WHEN JSONExtractString(message, 'after.user_id') != ''
        THEN JSONExtractString(message, 'after.user_id')
        WHEN JSONExtractString(message, 'after.aggregate_type') = 'event'
        THEN JSONExtractString(JSONExtractString(message, 'after.payload'), 'user_id')
        ELSE ''
    END as user_id,
    
    CASE 
        WHEN JSONExtractString(message, 'after.variant_id') != ''
        THEN toUInt32OrNull(JSONExtractString(message, 'after.variant_id'))
        WHEN JSONExtractString(message, 'after.aggregate_type') = 'event'
        THEN toUInt32OrNull(JSONExtractString(JSONExtractString(message, 'after.payload'), 'variant_id'))
        ELSE NULL
    END as variant_id,
    
    CASE 
        WHEN JSONExtractString(message, 'after.variant_key') != ''
        THEN JSONExtractString(message, 'after.variant_key')
        WHEN JSONExtractString(message, 'after.aggregate_type') = 'event'
        THEN JSONExtractString(JSONExtractString(message, 'after.payload'), 'variant_key')
        ELSE ''
    END as variant_key,
    
    CASE 
        WHEN JSONExtractString(message, 'after.event_type') != ''
        THEN JSONExtractString(message, 'after.event_type')
        WHEN JSONExtractString(message, 'after.aggregate_type') = 'event'
        THEN JSONExtractString(JSONExtractString(message, 'after.payload'), 'event_type')
        ELSE ''
    END as event_type,
    
    CASE 
        WHEN JSONExtractString(message, 'after.timestamp') != ''
        THEN parseDateTime64BestEffortOrNull(JSONExtractString(message, 'after.timestamp'))
        WHEN JSONExtractString(message, 'after.aggregate_type') = 'event'
        THEN parseDateTime64BestEffortOrNull(JSONExtractString(JSONExtractString(message, 'after.payload'), 'timestamp'))
        ELSE now64()
    END as timestamp,
    
    CASE 
        WHEN JSONExtractString(message, 'after.assignment_at') != ''
        THEN parseDateTime64BestEffortOrNull(JSONExtractString(message, 'after.assignment_at'))
        WHEN JSONExtractString(message, 'after.aggregate_type') = 'event'
        THEN parseDateTime64BestEffortOrNull(JSONExtractString(JSONExtractString(message, 'after.payload'), 'assignment_at'))
        ELSE NULL
    END as assignment_at,
    
    CASE 
        WHEN JSONExtractString(message, 'after.properties') != ''
        THEN JSONExtractString(message, 'after.properties')
        WHEN JSONExtractString(message, 'after.aggregate_type') = 'event'
        THEN JSONExtractString(JSONExtractString(message, 'after.payload'), 'properties')
        ELSE '{}'
    END as properties,
    
    CASE 
        WHEN JSONExtractString(message, 'after.session_id') != ''
        THEN JSONExtractString(message, 'after.session_id')
        WHEN JSONExtractString(message, 'after.aggregate_type') = 'event'
        THEN JSONExtractString(JSONExtractString(message, 'after.payload'), 'session_id')
        ELSE ''
    END as session_id,
    
    CASE 
        WHEN JSONExtractString(message, 'after.request_id') != ''
        THEN JSONExtractString(message, 'after.request_id')
        WHEN JSONExtractString(message, 'after.aggregate_type') = 'event'
        THEN JSONExtractString(JSONExtractString(message, 'after.payload'), 'request_id')
        ELSE ''
    END as request_id,
    
    parseDateTime64BestEffortOrNull(JSONExtractString(message, 'after.created_at')) as created_at,
    parseDateTime64BestEffortOrNull(JSONExtractString(message, 'after.updated_at')) as updated_at

FROM raw_events_kafka
WHERE JSONExtractString(message, 'op') IN ('r', 'c', 'u')
  AND (
    (JSONExtractString(message, 'after.id') != '' AND JSONExtractString(message, 'after.experiment_id') != '')
    OR 
    (JSONExtractString(message, 'after.aggregate_type') = 'event' AND JSONExtractString(message, 'after.event_type') = 'EVENT_CREATED')
  );

-- =============================================================================
-- 6. ASSIGNMENTS PROCESSOR (From outbox events)
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS assignments_processor_mv TO assignments_processed AS
SELECT 
    JSONExtractString(JSONExtractString(message, 'after.payload'), 'id') as id,
    toUInt32(JSONExtractString(JSONExtractString(message, 'after.payload'), 'experiment_id')) as experiment_id,
    JSONExtractString(JSONExtractString(message, 'after.payload'), 'user_id') as user_id,
    toUInt32(JSONExtractString(JSONExtractString(message, 'after.payload'), 'variant_id')) as variant_id,
    JSONExtractString(JSONExtractString(message, 'after.payload'), 'variant_key') as variant_key,
    parseDateTime64BestEffortOrNull(JSONExtractString(JSONExtractString(message, 'after.payload'), 'assigned_at')) as assigned_at,
    parseDateTime64BestEffortOrNull(JSONExtractString(JSONExtractString(message, 'after.payload'), 'enrolled_at')) as enrolled_at,
    JSONExtractString(JSONExtractString(message, 'after.payload'), 'source') as source,
    parseDateTime64BestEffortOrNull(JSONExtractString(message, 'after.created_at')) as created_at,
    parseDateTime64BestEffortOrNull(JSONExtractString(message, 'after.updated_at')) as updated_at

FROM raw_events_kafka
WHERE JSONExtractString(message, 'after.aggregate_type') = 'assignment'
  AND JSONExtractString(message, 'after.event_type') IN ('ASSIGNMENT_CREATED', 'ASSIGNMENT_ENROLLED')
  AND JSONExtractString(message, 'op') IN ('r', 'c', 'u');

-- =============================================================================
-- 7. DAILY ANALYTICS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS experiment_daily_stats (
    experiment_id UInt32,
    variant_id UInt32,
    event_date Date,
    
    total_events UInt64,
    exposures UInt64,
    conversions UInt64,
    clicks UInt64,
    
    unique_users UInt64,
    
    conversion_rate Float32,
    total_value Float32,
    avg_value_per_user Float32
    
) ENGINE = SummingMergeTree()
ORDER BY (experiment_id, variant_id, event_date)
PARTITION BY toYYYYMM(event_date);

-- =============================================================================
-- 8. DAILY STATS MATERIALIZED VIEW
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS daily_stats_mv TO experiment_daily_stats AS
SELECT 
    experiment_id,
    variant_id,
    event_date,
    
    count() as total_events,
    countIf(is_exposure) as exposures,
    countIf(is_conversion) as conversions,
    countIf(is_click) as clicks,
    
    uniq(user_id) as unique_users,
    
    if(countIf(is_exposure) > 0, countIf(is_conversion) / countIf(is_exposure), 0) as conversion_rate,
    sum(value) as total_value,
    if(uniq(user_id) > 0, sum(value) / uniq(user_id), 0) as avg_value_per_user
    
FROM events_processed
WHERE is_valid = true
GROUP BY experiment_id, variant_id, event_date;

-- =============================================================================
-- 9. REFERENCE TABLES (Dictionary access to PostgreSQL)
-- =============================================================================

CREATE TABLE IF NOT EXISTS experiments_dict (
    id UInt32,
    key String,
    name String,
    status String,
    created_at DateTime64(3)
) ENGINE = PostgreSQL('postgres:5432', 'experiments', 'experiments', 'experiments', 'password');

CREATE TABLE IF NOT EXISTS variants_dict (
    id UInt32,
    experiment_id UInt32,
    key String,
    name String,
    is_control Bool
) ENGINE = PostgreSQL('postgres:5432', 'experiments', 'variants', 'experiments', 'password');
