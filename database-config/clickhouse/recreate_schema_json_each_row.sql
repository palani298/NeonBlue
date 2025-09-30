-- Recreate entire ClickHouse schema with JSONEachRow format
-- This should fix the CDC pipeline timestamp issue

-- 1. Drop existing tables and views
DROP VIEW IF EXISTS experiments_analytics.events_mv;
DROP VIEW IF EXISTS experiments_analytics.assignments_mv;
DROP VIEW IF EXISTS experiments_analytics.daily_stats_mv;
DROP VIEW IF EXISTS experiments_analytics.reports_mv;
DROP VIEW IF EXISTS experiments_analytics.reports_denormalized_mv;

DROP TABLE IF EXISTS experiments_analytics.raw_events;
DROP TABLE IF EXISTS experiments_analytics.raw_assignments;
DROP TABLE IF EXISTS experiments_analytics.events_processed;
DROP TABLE IF EXISTS experiments_analytics.assignments_processed;
DROP TABLE IF EXISTS experiments_analytics.experiment_daily_stats;
DROP TABLE IF EXISTS experiments_analytics.experiment_reports;
DROP TABLE IF EXISTS experiments_analytics.experiment_reports_denormalized;

-- 2. DICTIONARY TABLES (Direct PostgreSQL connection)
-- These are static reference data that don't need CDC

CREATE TABLE IF NOT EXISTS experiments_analytics.users_dict (
    user_id String,
    email Nullable(String),
    name Nullable(String),
    age Nullable(Int32),
    location Nullable(String),
    plan Nullable(String),
    is_active Bool,
    created_at DateTime64(3),
    updated_at DateTime64(3)
) ENGINE = PostgreSQL('postgres:5432', 'experiments', 'users', 'experiments', 'password');

CREATE TABLE IF NOT EXISTS experiments_analytics.experiments_dict (
    id UInt32,
    key String,
    name String,
    description Nullable(String),
    status String,
    seed String,
    version UInt32,
    min_sample_size Nullable(Int32),
    traffic_allocation Nullable(Int32),
    starts_at Nullable(DateTime64(3)),
    ends_at Nullable(DateTime64(3)),
    created_at DateTime64(3),
    updated_at DateTime64(3)
) ENGINE = PostgreSQL('postgres:5432', 'experiments', 'experiments', 'experiments', 'password');

CREATE TABLE IF NOT EXISTS experiments_analytics.variants_dict (
    id UInt32,
    experiment_id UInt32,
    key String,
    name String,
    description Nullable(String),
    allocation_pct UInt8,
    is_control Bool,
    config_text Nullable(String),
    config_color Nullable(String),
    created_at DateTime64(3),
    updated_at DateTime64(3)
) ENGINE = PostgreSQL('postgres:5432', 'experiments', 'variants', 'experiments', 'password');

-- 3. EVENT DATA (CDC via Kafka) - Using JSONEachRow format
-- This should properly parse the Debezium JSON structure

CREATE TABLE experiments_analytics.raw_events (
    before Nullable(String),
    after String,
    source String,
    op String,
    ts_ms UInt64,
    transaction Nullable(String)
) ENGINE = Kafka()
SETTINGS 
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'experiments_events',
    kafka_group_name = 'clickhouse_events_consumer_v3',
    kafka_format = 'JSONEachRow',
    kafka_skip_broken_messages = 1000;

CREATE TABLE experiments_analytics.raw_assignments (
    before Nullable(String),
    after String,
    source String,
    op String,
    ts_ms UInt64,
    transaction Nullable(String)
) ENGINE = Kafka()
SETTINGS 
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'experiments_assignments',
    kafka_group_name = 'clickhouse_assignments_consumer_v3',
    kafka_format = 'JSONEachRow',
    kafka_skip_broken_messages = 1000;

-- 4. PROCESSED TABLES (Targets for materialized views)
CREATE TABLE experiments_analytics.events_processed (
    id String,
    experiment_id UInt32,
    user_id String,
    variant_id Nullable(UInt32),
    event_type String,
    timestamp DateTime64(3),
    assignment_at Nullable(DateTime64(3)),
    properties String,
    session_id Nullable(String),
    request_id Nullable(String),
    created_at DateTime64(3),
    updated_at DateTime64(3),
    event_date Date MATERIALIZED toDate(timestamp),
    event_hour UInt8 MATERIALIZED toHour(timestamp),
    -- Extracted properties for analytics
    page Nullable(String) MATERIALIZED JSONExtractString(properties, 'page'),
    device Nullable(String) MATERIALIZED JSONExtractString(properties, 'device'),
    browser Nullable(String) MATERIALIZED JSONExtractString(properties, 'browser'),
    session_duration Nullable(Int32) MATERIALIZED JSONExtractInt(properties, 'session_duration'),
    score Nullable(Int32) MATERIALIZED JSONExtractInt(properties, 'score'),
    conversion Bool MATERIALIZED event_type = 'conversion'
) ENGINE = MergeTree()
ORDER BY (experiment_id, event_date, event_hour, timestamp)
PARTITION BY toYYYYMM(event_date)
TTL toDateTime(timestamp) + INTERVAL 90 DAY;

CREATE TABLE experiments_analytics.assignments_processed (
    id String,
    experiment_id UInt32,
    user_id String,
    variant_id UInt32,
    is_enrolled Bool,
    enrolled_at Nullable(DateTime64(3)),
    created_at DateTime64(3),
    updated_at DateTime64(3),
    assignment_date Date MATERIALIZED toDate(created_at)
) ENGINE = MergeTree()
ORDER BY (experiment_id, assignment_date, user_id)
PARTITION BY toYYYYMM(assignment_date)
TTL created_at + INTERVAL 365 DAY;

-- 5. MATERIALIZED VIEWS (Process CDC data with JSONEachRow)
-- Now we can directly access the 'after' field as a JSON string

CREATE MATERIALIZED VIEW experiments_analytics.events_mv TO experiments_analytics.events_processed AS
SELECT 
    JSONExtractString(after, 'id') as id,
    JSONExtractUInt(after, 'experiment_id') as experiment_id,
    JSONExtractString(after, 'user_id') as user_id,
    JSONExtractUInt(after, 'variant_id') as variant_id,
    JSONExtractString(after, 'event_type') as event_type,
    parseDateTime64BestEffortOrZero(replaceRegexpAll(JSONExtractString(after, 'timestamp'), 'Z$', '')) as timestamp,
    parseDateTime64BestEffortOrZero(replaceRegexpAll(JSONExtractString(after, 'assignment_at'), 'Z$', '')) as assignment_at,
    JSONExtractString(after, 'properties') as properties,
    JSONExtractString(after, 'session_id') as session_id,
    JSONExtractString(after, 'request_id') as request_id,
    parseDateTime64BestEffortOrZero(replaceRegexpAll(JSONExtractString(after, 'created_at'), 'Z$', '')) as created_at,
    parseDateTime64BestEffortOrZero(replaceRegexpAll(JSONExtractString(after, 'updated_at'), 'Z$', '')) as updated_at
FROM experiments_analytics.raw_events
WHERE op IN ('r', 'c', 'u');

CREATE MATERIALIZED VIEW experiments_analytics.assignments_mv TO experiments_analytics.assignments_processed AS
SELECT 
    JSONExtractString(after, 'id') as id,
    JSONExtractUInt(after, 'experiment_id') as experiment_id,
    JSONExtractString(after, 'user_id') as user_id,
    JSONExtractUInt(after, 'variant_id') as variant_id,
    JSONExtractBool(after, 'is_enrolled') as is_enrolled,
    parseDateTime64BestEffortOrZero(replaceRegexpAll(JSONExtractString(after, 'enrolled_at'), 'Z$', '')) as enrolled_at,
    parseDateTime64BestEffortOrZero(replaceRegexpAll(JSONExtractString(after, 'created_at'), 'Z$', '')) as created_at,
    parseDateTime64BestEffortOrZero(replaceRegexpAll(JSONExtractString(after, 'updated_at'), 'Z$', '')) as updated_at
FROM experiments_analytics.raw_assignments
WHERE op IN ('r', 'c', 'u');

-- 6. ANALYTICS TABLES (Aggregated data)
CREATE TABLE experiments_analytics.experiment_daily_stats (
    experiment_id UInt32,
    variant_id UInt32,
    event_date Date,
    total_events AggregateFunction(count, UInt64),
    unique_users AggregateFunction(uniq, String),
    total_score AggregateFunction(sum, Int32),
    avg_score AggregateFunction(avg, Float32),
    conversion_rate AggregateFunction(avg, Float32),
    avg_session_duration AggregateFunction(avg, Int32)
) ENGINE = AggregatingMergeTree()
ORDER BY (experiment_id, variant_id, event_date)
PARTITION BY toYYYYMM(event_date);

-- 7. FINAL REPORTING TABLE
CREATE TABLE experiments_analytics.experiment_reports (
    experiment_id UInt32,
    variant_id UInt32,
    variant_name String,
    is_control Bool,
    experiment_name String,
    report_date Date,
    total_events UInt64,
    unique_users UInt64,
    total_score UInt64,
    avg_score Float32,
    conversion_rate Float32,
    avg_session_duration Float32,
    statistical_significance Float32,
    confidence_interval_lower Float32,
    confidence_interval_upper Float32
) ENGINE = SummingMergeTree()
ORDER BY (experiment_id, variant_id, report_date)
PARTITION BY toYYYYMM(report_date);

-- 8. MATERIALIZED VIEW FOR DAILY STATS
CREATE MATERIALIZED VIEW experiments_analytics.daily_stats_mv TO experiments_analytics.experiment_daily_stats AS
SELECT 
    experiment_id,
    variant_id,
    event_date,
    countState() as total_events,
    uniqState(user_id) as unique_users,
    sumState(ifNull(score, 0)) as total_score,
    avgState(ifNull(score, 0)) as avg_score,
    avgState(if(conversion, 1, 0)) as conversion_rate,
    avgState(ifNull(session_duration, 0)) as avg_session_duration
FROM experiments_analytics.events_processed
WHERE score IS NOT NULL
GROUP BY experiment_id, variant_id, event_date;

-- 9. MATERIALIZED VIEW FOR FINAL REPORTS
CREATE MATERIALIZED VIEW experiments_analytics.reports_mv TO experiments_analytics.experiment_reports AS
SELECT 
    e.experiment_id,
    e.variant_id,
    v.name as variant_name,
    v.is_control,
    exp.name as experiment_name,
    e.event_date as report_date,
    sum(e.total_events) as total_events,
    sum(e.unique_users) as unique_users,
    sum(e.total_score) as total_score,
    avg(e.avg_score) as avg_score,
    avg(e.conversion_rate) as conversion_rate,
    avg(e.avg_session_duration) as avg_session_duration,
    0.0 as statistical_significance, -- Placeholder for statistical calculations
    0.0 as confidence_interval_lower,
    0.0 as confidence_interval_upper
FROM experiments_analytics.experiment_daily_stats e
LEFT JOIN experiments_analytics.variants_dict v ON e.variant_id = v.id
LEFT JOIN experiments_analytics.experiments_dict exp ON e.experiment_id = exp.id
GROUP BY e.experiment_id, e.variant_id, v.name, v.is_control, exp.name, e.event_date;
