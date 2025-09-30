-- Complete ClickHouse Analytics Setup
-- Kafka consumption → JSON processing → Materialized views → Aggregated analytics

-- =============================================================================
-- 1. CREATE DATABASE
-- =============================================================================
CREATE DATABASE IF NOT EXISTS experiments_analytics;

USE experiments_analytics;

-- =============================================================================
-- 2. KAFKA CONSUMER TABLES (Raw CDC Data)
-- =============================================================================

-- Raw events from Kafka (Debezium CDC format)
-- Using LineAsString because Debezium sends complex nested JSON
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
-- 3. PROCESSED TABLES (Clean, structured data)
-- =============================================================================

-- Events processed from CDC JSON
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
    event_minute UInt8 MATERIALIZED toMinute(timestamp),
    
    -- JSON property extraction for common analytics
    page Nullable(String) MATERIALIZED JSONExtractString(properties, 'page'),
    device Nullable(String) MATERIALIZED JSONExtractString(properties, 'device'),
    browser Nullable(String) MATERIALIZED JSONExtractString(properties, 'browser'),
    source Nullable(String) MATERIALIZED JSONExtractString(properties, 'source'),
    campaign Nullable(String) MATERIALIZED JSONExtractString(properties, 'campaign'),
    value Nullable(Float32) MATERIALIZED JSONExtractFloat(properties, 'value'),
    score Nullable(Int32) MATERIALIZED JSONExtractInt(properties, 'score'),
    duration Nullable(Int32) MATERIALIZED JSONExtractInt(properties, 'duration'),
    session_duration Nullable(Int32) MATERIALIZED JSONExtractInt(properties, 'session_duration'),
    
    -- Event type flags for fast filtering
    is_conversion Bool MATERIALIZED event_type = 'conversion',
    is_exposure Bool MATERIALIZED event_type = 'exposure',
    is_click Bool MATERIALIZED event_type = 'click',
    is_pageview Bool MATERIALIZED event_type = 'page_view',
    
    -- Validity check (event after assignment)
    is_valid Bool MATERIALIZED if(assignment_at IS NOT NULL, timestamp >= assignment_at, true)
    
) ENGINE = MergeTree()
ORDER BY (experiment_id, event_date, event_hour, user_id, timestamp)
PARTITION BY toYYYYMM(event_date)
TTL timestamp + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- Assignment events processed from CDC JSON
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
    
    -- Computed columns
    assignment_date Date MATERIALIZED toDate(assigned_at),
    assignment_hour UInt8 MATERIALIZED toHour(assigned_at),
    is_enrolled Bool MATERIALIZED enrolled_at IS NOT NULL
    
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (experiment_id, user_id, variant_id)
PARTITION BY toYYYYMM(assignment_date)
TTL assigned_at + INTERVAL 365 DAY
SETTINGS index_granularity = 8192;

-- =============================================================================
-- 4. MATERIALIZED VIEWS (Process CDC JSON → Structured Data)
-- =============================================================================

-- Process CDC events from Kafka
-- Handles both direct events and outbox events from Debezium CDC
CREATE MATERIALIZED VIEW IF NOT EXISTS events_processor_mv TO events_processed AS
SELECT 
    -- Extract from Debezium CDC format
    CASE 
        -- Direct event from events table
        WHEN JSONExtractString(message, 'after.id') != '' AND JSONExtractString(message, 'after.experiment_id') != ''
        THEN JSONExtractString(message, 'after.id')
        -- Event from outbox_events table (extract from payload)
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
    
    -- Parse timestamps with fallback logic
    CASE 
        WHEN JSONExtractString(message, 'after.timestamp') != ''
        THEN parseDateTime64BestEffortOrNull(JSONExtractString(message, 'after.timestamp'))
        WHEN JSONExtractString(message, 'after.aggregate_type') = 'event'
        THEN parseDateTime64BestEffortOrNull(JSONExtractString(JSONExtractString(message, 'after.payload'), 'timestamp'))
        ELSE NULL
    END as timestamp,
    
    CASE 
        WHEN JSONExtractString(message, 'after.assignment_at') != ''
        THEN parseDateTime64BestEffortOrNull(JSONExtractString(message, 'after.assignment_at'))
        WHEN JSONExtractString(message, 'after.aggregate_type') = 'event'
        THEN parseDateTime64BestEffortOrNull(JSONExtractString(JSONExtractString(message, 'after.payload'), 'assignment_at'))
        ELSE NULL
    END as assignment_at,
    
    -- Properties and metadata
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
WHERE JSONExtractString(message, 'op') IN ('r', 'c', 'u')  -- Read, Create, Update operations
  AND (
    -- Direct event table
    (JSONExtractString(message, 'after.id') != '' AND JSONExtractString(message, 'after.experiment_id') != '')
    OR 
    -- Outbox event with event type
    (JSONExtractString(message, 'after.aggregate_type') = 'event' AND JSONExtractString(message, 'after.event_type') = 'EVENT_CREATED')
  );

-- Process assignment events from outbox pattern
CREATE MATERIALIZED VIEW IF NOT EXISTS assignments_processor_mv TO assignments_processed AS
SELECT 
    JSONExtractString(payload, 'id') as id,
    toUInt32(JSONExtractString(payload, 'experiment_id')) as experiment_id,
    JSONExtractString(payload, 'user_id') as user_id,
    toUInt32(JSONExtractString(payload, 'variant_id')) as variant_id,
    JSONExtractString(payload, 'variant_key') as variant_key,
    parseDateTime64BestEffortOrNull(JSONExtractString(payload, 'assigned_at')) as assigned_at,
    parseDateTime64BestEffortOrNull(JSONExtractString(payload, 'enrolled_at')) as enrolled_at,
    JSONExtractString(payload, 'source') as source,
    parseDateTime64BestEffortOrNull(JSONExtractString(message, 'after.created_at')) as created_at,
    parseDateTime64BestEffortOrNull(JSONExtractString(message, 'after.updated_at')) as updated_at

FROM raw_events_kafka
WHERE JSONExtractString(message, 'after.aggregate_type') = 'assignment'
  AND JSONExtractString(message, 'after.event_type') IN ('ASSIGNMENT_CREATED', 'ASSIGNMENT_ENROLLED')
  AND JSONExtractString(message, 'op') IN ('r', 'c', 'u');

-- =============================================================================
-- 5. EXPERIMENT ANALYTICS TABLES (Aggregated metrics)
-- =============================================================================

-- Hourly experiment metrics (real-time analytics)
CREATE TABLE IF NOT EXISTS experiment_hourly_stats (
    experiment_id UInt32,
    variant_id UInt32,
    event_date Date,
    event_hour UInt8,
    
    -- Event counts by type
    total_events AggregateFunction(count, UInt64),
    exposures AggregateFunction(count, UInt64),
    conversions AggregateFunction(count, UInt64),
    clicks AggregateFunction(count, UInt64),
    pageviews AggregateFunction(count, UInt64),
    
    -- User metrics
    unique_users AggregateFunction(uniq, String),
    unique_sessions AggregateFunction(uniq, String),
    
    -- Value metrics
    total_value AggregateFunction(sum, Float32),
    avg_value AggregateFunction(avg, Float32),
    total_score AggregateFunction(sum, Int32),
    avg_score AggregateFunction(avg, Float32),
    
    -- Engagement metrics
    avg_session_duration AggregateFunction(avg, Int32),
    bounce_rate AggregateFunction(avg, Float32)
    
) ENGINE = AggregatingMergeTree()
ORDER BY (experiment_id, variant_id, event_date, event_hour)
PARTITION BY toYYYYMM(event_date)
TTL event_date + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- Daily experiment rollups (for reporting)
CREATE TABLE IF NOT EXISTS experiment_daily_stats (
    experiment_id UInt32,
    variant_id UInt32,
    event_date Date,
    
    -- Event counts
    total_events UInt64,
    exposures UInt64,
    conversions UInt64,
    clicks UInt64,
    pageviews UInt64,
    
    -- User metrics
    unique_users UInt64,
    unique_sessions UInt64,
    new_users UInt64,
    
    -- Conversion metrics
    conversion_rate Float32,
    click_through_rate Float32,
    
    -- Value metrics
    total_value Float32,
    avg_value_per_user Float32,
    avg_value_per_conversion Float32,
    
    -- Engagement metrics
    avg_session_duration Float32,
    avg_events_per_user Float32,
    bounce_rate Float32
    
) ENGINE = SummingMergeTree()
ORDER BY (experiment_id, variant_id, event_date)
PARTITION BY toYYYYMM(event_date)
TTL event_date + INTERVAL 365 DAY
SETTINGS index_granularity = 8192;

-- User-level experiment analytics
CREATE TABLE IF NOT EXISTS user_experiment_stats (
    experiment_id UInt32,
    variant_id UInt32,
    user_id String,
    
    -- Assignment info
    assigned_at DateTime64(3),
    first_exposure DateTime64(3),
    
    -- Event counts
    total_events UInt32,
    total_conversions UInt32,
    total_clicks UInt32,
    total_pageviews UInt32,
    
    -- User journey
    session_count UInt32,
    total_session_duration UInt32,
    days_active UInt16,
    
    -- Value metrics
    total_value Float32,
    avg_event_value Float32,
    
    -- Flags
    has_converted Bool,
    is_active Bool
    
) ENGINE = SummingMergeTree()
ORDER BY (experiment_id, user_id, variant_id)
PARTITION BY experiment_id
TTL assigned_at + INTERVAL 365 DAY
SETTINGS index_granularity = 8192;

-- =============================================================================
-- 6. REAL-TIME ANALYTICS MATERIALIZED VIEWS
-- =============================================================================

-- Populate hourly stats from events
CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_stats_mv TO experiment_hourly_stats AS
SELECT 
    experiment_id,
    variant_id,
    event_date,
    event_hour,
    
    countState() as total_events,
    countIfState(is_exposure) as exposures,
    countIfState(is_conversion) as conversions,
    countIfState(is_click) as clicks,
    countIfState(is_pageview) as pageviews,
    
    uniqState(user_id) as unique_users,
    uniqState(session_id) as unique_sessions,
    
    sumState(value) as total_value,
    avgState(value) as avg_value,
    sumState(score) as total_score,
    avgState(score) as avg_score,
    
    avgState(session_duration) as avg_session_duration,
    avgState(if(duration <= 5000, 1.0, 0.0)) as bounce_rate  -- 5 second bounce
    
FROM events_processed
WHERE is_valid = true  -- Only count events after assignment
GROUP BY experiment_id, variant_id, event_date, event_hour;

-- Populate daily stats (rolled up from hourly)
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_stats_mv TO experiment_daily_stats AS
SELECT 
    experiment_id,
    variant_id,
    event_date,
    
    -- Event counts
    countMerge(total_events) as total_events,
    countMerge(exposures) as exposures,
    countMerge(conversions) as conversions,
    countMerge(clicks) as clicks,
    countMerge(pageviews) as pageviews,
    
    -- User metrics
    uniqMerge(unique_users) as unique_users,
    uniqMerge(unique_sessions) as unique_sessions,
    0 as new_users,  -- Calculate separately if needed
    
    -- Conversion rates
    if(countMerge(exposures) > 0, countMerge(conversions) / countMerge(exposures), 0) as conversion_rate,
    if(countMerge(pageviews) > 0, countMerge(clicks) / countMerge(pageviews), 0) as click_through_rate,
    
    -- Value metrics
    sumMerge(total_value) as total_value,
    if(uniqMerge(unique_users) > 0, sumMerge(total_value) / uniqMerge(unique_users), 0) as avg_value_per_user,
    if(countMerge(conversions) > 0, sumMerge(total_value) / countMerge(conversions), 0) as avg_value_per_conversion,
    
    -- Engagement
    avgMerge(avg_session_duration) as avg_session_duration,
    if(uniqMerge(unique_users) > 0, countMerge(total_events) / uniqMerge(unique_users), 0) as avg_events_per_user,
    avgMerge(bounce_rate) as bounce_rate
    
FROM experiment_hourly_stats
GROUP BY experiment_id, variant_id, event_date;

-- Populate user-level stats
CREATE MATERIALIZED VIEW IF NOT EXISTS user_stats_mv TO user_experiment_stats AS
SELECT 
    experiment_id,
    variant_id,
    user_id,
    
    -- Assignment timing
    min(timestamp) as assigned_at,
    minIf(timestamp, is_exposure) as first_exposure,
    
    -- Event counts
    count() as total_events,
    countIf(is_conversion) as total_conversions,
    countIf(is_click) as total_clicks,
    countIf(is_pageview) as total_pageviews,
    
    -- User journey
    uniq(session_id) as session_count,
    sum(session_duration) as total_session_duration,
    uniq(event_date) as days_active,
    
    -- Value
    sum(value) as total_value,
    avg(value) as avg_event_value,
    
    -- Flags
    countIf(is_conversion) > 0 as has_converted,
    max(event_date) >= today() - 7 as is_active  -- Active in last 7 days
    
FROM events_processed
WHERE is_valid = true
GROUP BY experiment_id, variant_id, user_id;

-- =============================================================================
-- 7. REFERENCE DATA TABLES (Dictionary access to PostgreSQL)
-- =============================================================================

CREATE TABLE IF NOT EXISTS experiments_dict (
    id UInt32,
    key String,
    name String,
    description Nullable(String),
    status String,
    created_at DateTime64(3),
    updated_at DateTime64(3)
) ENGINE = PostgreSQL('postgres:5432', 'experiments', 'experiments', 'experiments', 'password');

CREATE TABLE IF NOT EXISTS variants_dict (
    id UInt32,
    experiment_id UInt32,
    key String,
    name String,
    allocation_pct UInt8,
    is_control Bool,
    created_at DateTime64(3)
) ENGINE = PostgreSQL('postgres:5432', 'experiments', 'variants', 'experiments', 'password');

CREATE TABLE IF NOT EXISTS users_dict (
    user_id String,
    email Nullable(String),
    name Nullable(String),
    created_at DateTime64(3)
) ENGINE = PostgreSQL('postgres:5432', 'experiments', 'users', 'experiments', 'password');

-- =============================================================================
-- 8. REPORTING VIEWS (For dashboard queries)
-- =============================================================================

-- Real-time experiment performance
CREATE VIEW IF NOT EXISTS experiment_performance AS
SELECT 
    e.id as experiment_id,
    e.name as experiment_name,
    e.status,
    v.id as variant_id,
    v.name as variant_name,
    v.is_control,
    v.allocation_pct,
    
    -- Today's metrics
    s.total_events,
    s.exposures,
    s.conversions,
    s.unique_users,
    s.conversion_rate,
    s.avg_value_per_user,
    s.avg_session_duration,
    
    -- Comparison to control (statistical significance would be calculated here)
    0.0 as lift_percentage,
    0.0 as statistical_significance
    
FROM experiments_dict e
LEFT JOIN variants_dict v ON e.id = v.experiment_id
LEFT JOIN experiment_daily_stats s ON v.id = s.variant_id AND s.event_date = today()
WHERE e.status = 'ACTIVE'
ORDER BY e.id, v.is_control DESC, v.id;

-- User journey analysis
CREATE VIEW IF NOT EXISTS user_journey_analysis AS
SELECT 
    experiment_id,
    variant_id,
    
    -- Funnel metrics
    count() as total_assigned_users,
    countIf(first_exposure IS NOT NULL) as exposed_users,
    countIf(has_converted) as converted_users,
    
    -- Conversion rates
    countIf(first_exposure IS NOT NULL) / count() as exposure_rate,
    countIf(has_converted) / countIf(first_exposure IS NOT NULL) as conversion_rate,
    
    -- Engagement
    avg(total_events) as avg_events_per_user,
    avg(session_count) as avg_sessions_per_user,
    avg(total_session_duration) as avg_total_session_duration,
    avg(days_active) as avg_days_active,
    
    -- Value
    avg(total_value) as avg_total_value,
    avgIf(total_value, has_converted) as avg_value_per_converter
    
FROM user_experiment_stats
GROUP BY experiment_id, variant_id
ORDER BY experiment_id, variant_id;
