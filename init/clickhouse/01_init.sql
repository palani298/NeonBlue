-- Initialize ClickHouse for analytics

-- Create experiments database
CREATE DATABASE IF NOT EXISTS experiments;

USE experiments;

-- Events table for analytics (receives data from Kafka/CDC)
CREATE TABLE IF NOT EXISTS events
(
    id UUID,
    experiment_id UInt64,
    user_id String,
    variant_id UInt64,
    variant_key String,
    event_type String,
    timestamp DateTime64(3),
    assignment_at DateTime64(3),
    properties String,  -- JSON string
    is_valid UInt8,     -- 1 if event occurred after assignment
    date Date MATERIALIZED toDate(timestamp)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (experiment_id, variant_id, user_id, timestamp)
TTL timestamp + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- Assignments table (for enrichment)
CREATE TABLE IF NOT EXISTS assignments
(
    experiment_id UInt64,
    user_id String,
    variant_id UInt64,
    variant_key String,
    assigned_at DateTime64(3),
    enrolled_at Nullable(DateTime64(3)),
    version UInt32,
    source String
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(assigned_at)
ORDER BY (experiment_id, user_id)
SETTINGS index_granularity = 8192;

-- Materialized view for hourly metrics
CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_metrics
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(hour)
ORDER BY (experiment_id, variant_id, event_type, hour)
AS SELECT
    experiment_id,
    variant_id,
    event_type,
    toStartOfHour(timestamp) as hour,
    count() as event_count,
    uniqExact(user_id) as unique_users,
    sumIf(1, is_valid = 1) as valid_events,
    avg(JSONExtractFloat(properties, 'value')) as avg_value
FROM events
GROUP BY experiment_id, variant_id, event_type, hour;

-- Materialized view for daily metrics
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_metrics
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(day)
ORDER BY (experiment_id, variant_id, event_type, day)
AS SELECT
    experiment_id,
    variant_id,
    event_type,
    toDate(timestamp) as day,
    count() as event_count,
    uniqExact(user_id) as unique_users,
    sumIf(1, is_valid = 1) as valid_events,
    avg(JSONExtractFloat(properties, 'value')) as avg_value,
    quantile(0.5)(JSONExtractFloat(properties, 'value')) as median_value,
    quantile(0.95)(JSONExtractFloat(properties, 'value')) as p95_value,
    quantile(0.99)(JSONExtractFloat(properties, 'value')) as p99_value
FROM events
WHERE is_valid = 1
GROUP BY experiment_id, variant_id, event_type, day;

-- Kafka engine table for consuming CDC events
CREATE TABLE IF NOT EXISTS kafka_events
(
    payload String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'experiments.events',
    kafka_group_name = 'clickhouse-consumer',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1,
    kafka_skip_broken_messages = 100;

-- Materialized view to parse Kafka events into events table
CREATE MATERIALIZED VIEW IF NOT EXISTS kafka_events_mv TO events AS
SELECT
    JSONExtractString(payload, 'id') AS id,
    JSONExtractUInt(payload, 'experiment_id') AS experiment_id,
    JSONExtractString(payload, 'user_id') AS user_id,
    JSONExtractUInt(payload, 'variant_id') AS variant_id,
    JSONExtractString(payload, 'variant_key') AS variant_key,
    JSONExtractString(payload, 'event_type') AS event_type,
    parseDateTimeBestEffort(JSONExtractString(payload, 'timestamp')) AS timestamp,
    parseDateTimeBestEffort(JSONExtractString(payload, 'assignment_at')) AS assignment_at,
    JSONExtractString(payload, 'properties') AS properties,
    JSONExtractUInt(payload, 'is_valid') AS is_valid
FROM kafka_events
WHERE JSONExtractString(payload, 'id') != '';

-- Create table for experiment metadata
CREATE TABLE IF NOT EXISTS experiments
(
    id UInt64,
    key String,
    name String,
    status String,
    version UInt32,
    created_at DateTime64(3),
    updated_at DateTime64(3)
)
ENGINE = ReplacingMergeTree(version)
ORDER BY id
SETTINGS index_granularity = 8192;

-- Create table for variant metadata
CREATE TABLE IF NOT EXISTS variants
(
    id UInt64,
    experiment_id UInt64,
    key String,
    name String,
    allocation_pct UInt8,
    is_control UInt8
)
ENGINE = ReplacingMergeTree()
ORDER BY (experiment_id, id)
SETTINGS index_granularity = 8192;