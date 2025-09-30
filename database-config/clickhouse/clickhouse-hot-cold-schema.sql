-- HOT/COLD DATA STRATEGY FOR CLICKHOUSE
-- Hot data (current month) in memory, cold data (historical) in S3

-- ==============================================
-- 1. EVENTS PROCESSED TABLE (Hot/Cold Strategy)
-- ==============================================
CREATE TABLE IF NOT EXISTS experiments_analytics.events_processed_hot_cold (
    id UInt64,
    experiment_id UInt32,
    user_id String,
    variant_id Nullable(UInt32),
    event_type String,
    timestamp DateTime64(3),
    assignment_at Nullable(DateTime64(3)),
    test_prop Nullable(String),
    score Nullable(Int32),
    session_id Nullable(String),
    request_id Nullable(String),
    created_at DateTime64(3),
    updated_at DateTime64(3),
    event_date Date MATERIALIZED toDate(timestamp),
    event_hour UInt8 MATERIALIZED toHour(timestamp),
    -- Extracted properties for analytics
    page Nullable(String) MATERIALIZED JSONExtractString(test_prop, 'page'),
    device Nullable(String) MATERIALIZED JSONExtractString(test_prop, 'device'),
    browser Nullable(String) MATERIALIZED JSONExtractString(test_prop, 'browser'),
    session_duration Nullable(Int32) MATERIALIZED JSONExtractInt(test_prop, 'session_duration'),
    conversion Bool MATERIALIZED event_type = 'conversion'
) ENGINE = MergeTree()
ORDER BY (experiment_id, event_date, event_hour, timestamp)
PARTITION BY toYYYYMM(event_date)
-- HOT/COLD TTL STRATEGY:
-- - Hot data (current month): Keep in memory for fast queries
-- - Cold data (older than 1 month): Move to S3 for cost-effective storage
TTL 
    timestamp + INTERVAL 1 MONTH TO VOLUME 'hot_storage',
    timestamp + INTERVAL 6 MONTHS TO VOLUME 'cold_storage',
    timestamp + INTERVAL 2 YEARS DELETE
SETTINGS 
    index_granularity = 8192,
    -- Enable compression for cold data
    compression_codec = 'LZ4';

-- ==============================================
-- 2. DAILY STATS TABLE (Hot/Cold Strategy)
-- ==============================================
CREATE TABLE IF NOT EXISTS experiments_analytics.experiment_daily_stats_hot_cold (
    experiment_id UInt32,
    variant_id UInt32,
    event_date Date,
    total_events AggregateFunction(count, UInt64),
    unique_users AggregateFunction(uniq, String),
    total_score AggregateFunction(sum, Int32),
    avg_score AggregateFunction(avg, Int32),
    conversion_rate AggregateFunction(avg, Float32),
    avg_session_duration AggregateFunction(avg, Int32)
) ENGINE = AggregatingMergeTree()
ORDER BY (experiment_id, variant_id, event_date)
PARTITION BY toYYYYMM(event_date)
-- HOT/COLD TTL STRATEGY:
-- - Hot data (current month): Keep in memory
-- - Cold data (older than 1 month): Move to S3
TTL 
    event_date + INTERVAL 1 MONTH TO VOLUME 'hot_storage',
    event_date + INTERVAL 6 MONTHS TO VOLUME 'cold_storage',
    event_date + INTERVAL 2 YEARS DELETE
SETTINGS 
    index_granularity = 8192,
    compression_codec = 'LZ4';

-- ==============================================
-- 3. REPORTS TABLE (Hot/Cold Strategy)
-- ==============================================
CREATE TABLE IF NOT EXISTS experiments_analytics.experiment_reports_hot_cold (
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
PARTITION BY toYYYYMM(report_date)
-- HOT/COLD TTL STRATEGY:
-- - Hot data (current month): Keep in memory
-- - Cold data (older than 1 month): Move to S3
TTL 
    report_date + INTERVAL 1 MONTH TO VOLUME 'hot_storage',
    report_date + INTERVAL 6 MONTHS TO VOLUME 'cold_storage',
    report_date + INTERVAL 2 YEARS DELETE
SETTINGS 
    index_granularity = 8192,
    compression_codec = 'LZ4';

-- ==============================================
-- 4. MATERIALIZED VIEWS (Updated for Hot/Cold)
-- ==============================================
CREATE MATERIALIZED VIEW IF NOT EXISTS experiments_analytics.daily_stats_hot_cold_mv 
TO experiments_analytics.experiment_daily_stats_hot_cold AS
SELECT 
    experiment_id,
    variant_id,
    event_date,
    countState() as total_events,
    uniqState(user_id) as unique_users,
    sumState(ifNull(score, 0)) as total_score,
    avgState(ifNull(score, 0)) as avg_score,
    avgState(toFloat32(if(event_type = 'conversion', 1, 0))) as conversion_rate,
    avgState(ifNull(session_duration, 0)) as avg_session_duration
FROM experiments_analytics.events_processed_hot_cold
WHERE score IS NOT NULL
GROUP BY experiment_id, variant_id, event_date;

CREATE MATERIALIZED VIEW IF NOT EXISTS experiments_analytics.reports_hot_cold_mv 
TO experiments_analytics.experiment_reports_hot_cold AS
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
    0.0 as statistical_significance,
    0.0 as confidence_interval_lower,
    0.0 as confidence_interval_upper
FROM experiments_analytics.experiment_daily_stats_hot_cold e
LEFT JOIN experiments_analytics.variants_dict v ON e.variant_id = v.id
LEFT JOIN experiments_analytics.experiments_dict exp ON e.experiment_id = exp.id
GROUP BY e.experiment_id, e.variant_id, v.name, v.is_control, exp.name, e.event_date;

-- ==============================================
-- 5. STORAGE POLICIES (Hot/Cold Configuration)
-- ==============================================
-- Create storage policy for hot/cold data
CREATE POLICY IF NOT EXISTS hot_cold_policy ON experiments_analytics.events_processed_hot_cold
AS PERIODIC 3600
TO VOLUME 'hot_storage'
WHERE toDate(timestamp) >= today() - INTERVAL 1 MONTH;

CREATE POLICY IF NOT EXISTS hot_cold_policy ON experiments_analytics.experiment_daily_stats_hot_cold
AS PERIODIC 3600
TO VOLUME 'hot_storage'
WHERE event_date >= today() - INTERVAL 1 MONTH;

CREATE POLICY IF NOT EXISTS hot_cold_policy ON experiments_analytics.experiment_reports_hot_cold
AS PERIODIC 3600
TO VOLUME 'hot_storage'
WHERE report_date >= today() - INTERVAL 1 MONTH;

-- ==============================================
-- 6. OPTIMIZATION SETTINGS
-- ==============================================
-- Optimize for hot data queries
ALTER TABLE experiments_analytics.events_processed_hot_cold 
SETTINGS 
    -- Enable parallel processing for hot data
    max_threads = 16,
    -- Optimize memory usage
    max_memory_usage = 10000000000,
    -- Enable query cache for hot data
    use_uncompressed_cache = 1;

-- ==============================================
-- 7. MONITORING QUERIES
-- ==============================================
-- Query to check data distribution between hot and cold storage
CREATE VIEW IF NOT EXISTS experiments_analytics.storage_distribution AS
SELECT 
    'events_processed' as table_name,
    count() as total_rows,
    countIf(toDate(timestamp) >= today() - INTERVAL 1 MONTH) as hot_rows,
    countIf(toDate(timestamp) < today() - INTERVAL 1 MONTH) as cold_rows,
    round(countIf(toDate(timestamp) >= today() - INTERVAL 1 MONTH) * 100.0 / count(), 2) as hot_percentage
FROM experiments_analytics.events_processed_hot_cold
UNION ALL
SELECT 
    'daily_stats' as table_name,
    count() as total_rows,
    countIf(event_date >= today() - INTERVAL 1 MONTH) as hot_rows,
    countIf(event_date < today() - INTERVAL 1 MONTH) as cold_rows,
    round(countIf(event_date >= today() - INTERVAL 1 MONTH) * 100.0 / count(), 2) as hot_percentage
FROM experiments_analytics.experiment_daily_stats_hot_cold
UNION ALL
SELECT 
    'reports' as table_name,
    count() as total_rows,
    countIf(report_date >= today() - INTERVAL 1 MONTH) as hot_rows,
    countIf(report_date < today() - INTERVAL 1 MONTH) as cold_rows,
    round(countIf(report_date >= today() - INTERVAL 1 MONTH) * 100.0 / count(), 2) as hot_percentage
FROM experiments_analytics.experiment_reports_hot_cold;
