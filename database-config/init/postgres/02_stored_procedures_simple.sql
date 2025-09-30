-- Simple stored procedures for experimentation platform
-- This file contains basic stored procedures without complex dependencies

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "plpgsql";

-- Basic function to get experiment statistics
CREATE OR REPLACE FUNCTION get_experiment_stats(p_experiment_id BIGINT)
RETURNS TABLE (
    total_assignments BIGINT,
    total_events BIGINT,
    conversion_rate NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(DISTINCT a.user_id)::BIGINT as total_assignments,
        COUNT(e.id)::BIGINT as total_events,
        CASE 
            WHEN COUNT(DISTINCT a.user_id) > 0 
            THEN ROUND((COUNT(e.id)::NUMERIC / COUNT(DISTINCT a.user_id)) * 100, 2)
            ELSE 0 
        END as conversion_rate
    FROM assignments a
    LEFT JOIN events e ON a.experiment_id = e.experiment_id AND a.user_id = e.user_id
    WHERE a.experiment_id = p_experiment_id;
END;
$$ LANGUAGE plpgsql;

-- Basic function to clean up old events
CREATE OR REPLACE FUNCTION cleanup_old_events(p_days_old INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM events 
    WHERE timestamp < NOW() - INTERVAL '1 day' * p_days_old;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
