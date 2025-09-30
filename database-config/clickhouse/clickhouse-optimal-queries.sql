-- OPTIMAL CLICKHOUSE ANALYTICS QUERIES
-- Using Direct PostgreSQL Dictionaries for Maximum Performance

-- ==============================================
-- 1. DASHBOARD OVERVIEW QUERY
-- ==============================================
-- Real-time experiment performance dashboard
SELECT 
    experiment_id,
    variant_id,
    dictGet('experiment_dict_direct', 'name', experiment_id) as experiment_name,
    dictGet('experiment_dict_direct', 'status', experiment_id) as experiment_status,
    dictGet('variant_dict_direct', 'name', variant_id) as variant_name,
    dictGet('variant_dict_direct', 'is_control', variant_id) as is_control,
    dictGet('variant_dict_direct', 'allocation_pct', variant_id) as allocation_pct,
    event_date,
    countMerge(total_events) as total_events,
    uniqMerge(unique_users) as unique_users,
    avgMerge(conversion_rate) as conversion_rate
FROM experiments_analytics.experiment_daily_stats
WHERE event_date >= today() - 30
GROUP BY experiment_id, variant_id, event_date
ORDER BY event_date DESC, total_events DESC;

-- ==============================================
-- 2. EXPERIMENT DETAILS QUERY
-- ==============================================
-- Detailed view of a specific experiment
SELECT 
    variant_id,
    dictGet('variant_dict_direct', 'name', variant_id) as variant_name,
    dictGet('variant_dict_direct', 'is_control', variant_id) as is_control,
    dictGet('variant_dict_direct', 'allocation_pct', variant_id) as allocation_pct,
    countMerge(total_events) as total_events,
    uniqMerge(unique_users) as unique_users,
    avgMerge(conversion_rate) as conversion_rate,
    avgMerge(avg_score) as avg_score
FROM experiments_analytics.experiment_daily_stats
WHERE experiment_id = 1 AND event_date >= today() - 7
GROUP BY variant_id
ORDER BY total_events DESC;

-- ==============================================
-- 3. REAL-TIME METRICS QUERY
-- ==============================================
-- Current day performance metrics
SELECT 
    dictGet('experiment_dict_direct', 'name', experiment_id) as experiment_name,
    dictGet('variant_dict_direct', 'name', variant_id) as variant_name,
    dictGet('variant_dict_direct', 'is_control', variant_id) as is_control,
    countMerge(total_events) as total_events,
    uniqMerge(unique_users) as unique_users,
    avgMerge(conversion_rate) as conversion_rate
FROM experiments_analytics.experiment_daily_stats
WHERE event_date = today()
GROUP BY experiment_id, variant_id
ORDER BY total_events DESC;

-- ==============================================
-- 4. USER ANALYTICS QUERY
-- ==============================================
-- User behavior and engagement metrics
SELECT 
    user_id,
    dictGet('user_dict_direct', 'name', user_id) as user_name,
    dictGet('user_dict_direct', 'email', user_id) as user_email,
    dictGet('user_dict_direct', 'is_active', user_id) as is_active,
    count() as event_count,
    countIf(event_type = 'conversion') as conversions,
    countIf(event_type = 'click') as clicks,
    countIf(event_type = 'view') as views
FROM experiments_analytics.events_processed
WHERE timestamp >= today() - 1
GROUP BY user_id
ORDER BY event_count DESC
LIMIT 100;

-- ==============================================
-- 5. EXPERIMENT COMPARISON QUERY
-- ==============================================
-- Compare control vs treatment variants
SELECT 
    experiment_id,
    dictGet('experiment_dict_direct', 'name', experiment_id) as experiment_name,
    dictGet('variant_dict_direct', 'name', variant_id) as variant_name,
    dictGet('variant_dict_direct', 'is_control', variant_id) as is_control,
    countMerge(total_events) as total_events,
    uniqMerge(unique_users) as unique_users,
    avgMerge(conversion_rate) as conversion_rate,
    avgMerge(avg_score) as avg_score,
    -- Calculate lift over control
    CASE 
        WHEN dictGet('variant_dict_direct', 'is_control', variant_id) = 1 THEN 0
        ELSE (avgMerge(conversion_rate) - 
              (SELECT avgMerge(conversion_rate) 
               FROM experiments_analytics.experiment_daily_stats e2 
               WHERE e2.experiment_id = experiment_daily_stats.experiment_id 
               AND dictGet('variant_dict_direct', 'is_control', e2.variant_id) = 1)) * 100
    END as lift_percentage
FROM experiments_analytics.experiment_daily_stats
WHERE event_date >= today() - 7
GROUP BY experiment_id, variant_id
ORDER BY experiment_id, is_control DESC;

-- ==============================================
-- 6. TREND ANALYSIS QUERY
-- ==============================================
-- Performance trends over time
SELECT 
    event_date,
    experiment_id,
    dictGet('experiment_dict_direct', 'name', experiment_id) as experiment_name,
    variant_id,
    dictGet('variant_dict_direct', 'name', variant_id) as variant_name,
    dictGet('variant_dict_direct', 'is_control', variant_id) as is_control,
    countMerge(total_events) as total_events,
    uniqMerge(unique_users) as unique_users,
    avgMerge(conversion_rate) as conversion_rate
FROM experiments_analytics.experiment_daily_stats
WHERE event_date >= today() - 14
GROUP BY event_date, experiment_id, variant_id
ORDER BY event_date DESC, experiment_id, variant_id;

-- ==============================================
-- 7. TOP PERFORMING EXPERIMENTS QUERY
-- ==============================================
-- Identify best performing experiments
SELECT 
    experiment_id,
    dictGet('experiment_dict_direct', 'name', experiment_id) as experiment_name,
    dictGet('experiment_dict_direct', 'status', experiment_id) as experiment_status,
    sum(countMerge(total_events)) as total_events,
    sum(uniqMerge(unique_users)) as total_users,
    avg(avgMerge(conversion_rate)) as avg_conversion_rate,
    avg(avgMerge(avg_score)) as avg_score
FROM experiments_analytics.experiment_daily_stats
WHERE event_date >= today() - 30
GROUP BY experiment_id
ORDER BY total_events DESC
LIMIT 10;

-- ==============================================
-- 8. USER SEGMENT ANALYSIS QUERY
-- ==============================================
-- Analyze user behavior by segments
SELECT 
    dictGet('user_dict_direct', 'name', user_id) as user_name,
    dictGet('user_dict_direct', 'is_active', user_id) as is_active,
    experiment_id,
    dictGet('experiment_dict_direct', 'name', experiment_id) as experiment_name,
    variant_id,
    dictGet('variant_dict_direct', 'name', variant_id) as variant_name,
    count() as event_count,
    countIf(event_type = 'conversion') as conversions,
    countIf(event_type = 'click') as clicks
FROM experiments_analytics.events_processed
WHERE timestamp >= today() - 7
GROUP BY user_id, experiment_id, variant_id
ORDER BY event_count DESC
LIMIT 50;

-- ==============================================
-- 9. EXPERIMENT HEALTH CHECK QUERY
-- ==============================================
-- Monitor experiment health and data quality
SELECT 
    experiment_id,
    dictGet('experiment_dict_direct', 'name', experiment_id) as experiment_name,
    dictGet('experiment_dict_direct', 'status', experiment_id) as experiment_status,
    count(DISTINCT variant_id) as variant_count,
    sum(countMerge(total_events)) as total_events,
    sum(uniqMerge(unique_users)) as total_users,
    min(event_date) as first_event_date,
    max(event_date) as last_event_date,
    count(DISTINCT event_date) as active_days
FROM experiments_analytics.experiment_daily_stats
WHERE event_date >= today() - 30
GROUP BY experiment_id
ORDER BY total_events DESC;

-- ==============================================
-- 10. STATISTICAL SIGNIFICANCE QUERY
-- ==============================================
-- Calculate statistical significance for experiments
WITH experiment_stats AS (
    SELECT 
        experiment_id,
        variant_id,
        dictGet('variant_dict_direct', 'is_control', variant_id) as is_control,
        countMerge(total_events) as events,
        uniqMerge(unique_users) as users,
        avgMerge(conversion_rate) as conversion_rate
    FROM experiments_analytics.experiment_daily_stats
    WHERE event_date >= today() - 7
    GROUP BY experiment_id, variant_id
),
control_stats AS (
    SELECT 
        experiment_id,
        conversion_rate as control_rate,
        users as control_users
    FROM experiment_stats
    WHERE is_control = 1
)
SELECT 
    e.experiment_id,
    dictGet('experiment_dict_direct', 'name', e.experiment_id) as experiment_name,
    e.variant_id,
    dictGet('variant_dict_direct', 'name', e.variant_id) as variant_name,
    e.conversion_rate,
    c.control_rate,
    e.users,
    c.control_users,
    -- Simple lift calculation
    CASE 
        WHEN c.control_rate > 0 THEN ((e.conversion_rate - c.control_rate) / c.control_rate) * 100
        ELSE 0
    END as lift_percentage
FROM experiment_stats e
JOIN control_stats c ON e.experiment_id = c.experiment_id
WHERE e.is_control = 0
ORDER BY lift_percentage DESC;
