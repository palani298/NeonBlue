-- =====================================================
-- Stored Procedures for Experimentation Platform
-- =====================================================

-- Enable PL/pgSQL if not already enabled
CREATE EXTENSION IF NOT EXISTS plpgsql;

-- =====================================================
-- EXPERIMENT PROCEDURES
-- =====================================================

-- Create experiment with variants
CREATE OR REPLACE FUNCTION create_experiment(
    p_key TEXT,
    p_name TEXT,
    p_description TEXT,
    p_status TEXT DEFAULT 'draft',
    p_starts_at TIMESTAMPTZ DEFAULT NULL,
    p_ends_at TIMESTAMPTZ DEFAULT NULL,
    p_config JSONB DEFAULT '{}',
    p_variants JSONB DEFAULT '[]'
) RETURNS TABLE (
    experiment_id BIGINT,
    experiment_key TEXT,
    experiment_name TEXT,
    experiment_status TEXT,
    experiment_version INT,
    created_at TIMESTAMPTZ
) AS $$
DECLARE
    v_experiment_id BIGINT;
    v_variant JSONB;
    v_total_allocation INT := 0;
BEGIN
    -- Validate total allocation equals 100
    FOR v_variant IN SELECT * FROM jsonb_array_elements(p_variants)
    LOOP
        v_total_allocation := v_total_allocation + (v_variant->>'allocation_pct')::INT;
    END LOOP;
    
    IF v_total_allocation != 100 THEN
        RAISE EXCEPTION 'Total allocation must equal 100%%, got %%', v_total_allocation;
    END IF;
    
    -- Insert experiment
    INSERT INTO experiments (key, name, description, status, starts_at, ends_at, config)
    VALUES (p_key, p_name, p_description, p_status, p_starts_at, p_ends_at, p_config)
    RETURNING id INTO v_experiment_id;
    
    -- Insert variants
    INSERT INTO variants (experiment_id, key, name, allocation_pct, is_control, config)
    SELECT 
        v_experiment_id,
        v->>'key',
        v->>'name',
        (v->>'allocation_pct')::INT,
        COALESCE((v->>'is_control')::BOOLEAN, false),
        COALESCE(v->'config', '{}')::JSONB
    FROM jsonb_array_elements(p_variants) v;
    
    -- Return experiment details
    RETURN QUERY
    SELECT 
        e.id,
        e.key,
        e.name,
        e.status,
        e.version,
        e.created_at
    FROM experiments e
    WHERE e.id = v_experiment_id;
END;
$$ LANGUAGE plpgsql;

-- Get experiment with variants
CREATE OR REPLACE FUNCTION get_experiment_with_variants(
    p_experiment_id BIGINT
) RETURNS TABLE (
    experiment_id BIGINT,
    experiment_key TEXT,
    experiment_name TEXT,
    experiment_status TEXT,
    experiment_version INT,
    starts_at TIMESTAMPTZ,
    ends_at TIMESTAMPTZ,
    variants JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.id,
        e.key,
        e.name,
        e.status,
        e.version,
        e.starts_at,
        e.ends_at,
        COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'id', v.id,
                    'key', v.key,
                    'name', v.name,
                    'allocation_pct', v.allocation_pct,
                    'is_control', v.is_control,
                    'config', v.config
                ) ORDER BY v.id
            ) FILTER (WHERE v.id IS NOT NULL),
            '[]'::jsonb
        ) as variants
    FROM experiments e
    LEFT JOIN variants v ON v.experiment_id = e.id
    WHERE e.id = p_experiment_id
    GROUP BY e.id, e.key, e.name, e.status, e.version, e.starts_at, e.ends_at;
END;
$$ LANGUAGE plpgsql;

-- List active experiments
CREATE OR REPLACE FUNCTION list_active_experiments(
    p_limit INT DEFAULT 100,
    p_offset INT DEFAULT 0
) RETURNS TABLE (
    experiment_id BIGINT,
    experiment_key TEXT,
    experiment_name TEXT,
    experiment_status TEXT,
    experiment_version INT,
    starts_at TIMESTAMPTZ,
    ends_at TIMESTAMPTZ,
    variant_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.id,
        e.key,
        e.name,
        e.status,
        e.version,
        e.starts_at,
        e.ends_at,
        COUNT(v.id) as variant_count
    FROM experiments e
    LEFT JOIN variants v ON v.experiment_id = e.id
    WHERE e.status = 'active'
        AND (e.starts_at IS NULL OR e.starts_at <= NOW())
        AND (e.ends_at IS NULL OR e.ends_at > NOW())
    GROUP BY e.id
    ORDER BY e.created_at DESC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$ LANGUAGE plpgsql;

-- Activate experiment
CREATE OR REPLACE FUNCTION activate_experiment(
    p_experiment_id BIGINT
) RETURNS TABLE (
    success BOOLEAN,
    message TEXT,
    new_version INT
) AS $$
DECLARE
    v_current_status TEXT;
    v_new_version INT;
BEGIN
    -- Get current status
    SELECT status INTO v_current_status
    FROM experiments
    WHERE id = p_experiment_id;
    
    IF v_current_status IS NULL THEN
        RETURN QUERY SELECT false, 'Experiment not found', NULL::INT;
        RETURN;
    END IF;
    
    IF v_current_status = 'active' THEN
        RETURN QUERY SELECT false, 'Experiment already active', NULL::INT;
        RETURN;
    END IF;
    
    -- Update experiment
    UPDATE experiments
    SET 
        status = 'active',
        version = version + 1,
        starts_at = COALESCE(starts_at, NOW()),
        updated_at = NOW()
    WHERE id = p_experiment_id
    RETURNING version INTO v_new_version;
    
    RETURN QUERY SELECT true, 'Experiment activated', v_new_version;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- ASSIGNMENT PROCEDURES
-- =====================================================

-- Get or create assignment
CREATE OR REPLACE FUNCTION get_or_create_assignment(
    p_experiment_id BIGINT,
    p_user_id TEXT,
    p_variant_key TEXT,
    p_enroll BOOLEAN DEFAULT FALSE
) RETURNS TABLE (
    assignment_id BIGINT,
    experiment_id BIGINT,
    user_id TEXT,
    variant_id BIGINT,
    variant_key TEXT,
    variant_name TEXT,
    enrolled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    is_new BOOLEAN
) AS $$
DECLARE
    v_assignment_id BIGINT;
    v_variant_id BIGINT;
    v_variant_name TEXT;
    v_enrolled_at TIMESTAMPTZ;
    v_is_new BOOLEAN := FALSE;
    v_experiment_version INT;
BEGIN
    -- Get experiment version
    SELECT version INTO v_experiment_version
    FROM experiments
    WHERE id = p_experiment_id AND status = 'active';
    
    IF v_experiment_version IS NULL THEN
        RAISE EXCEPTION 'Experiment % not found or not active', p_experiment_id;
    END IF;
    
    -- Check for existing assignment
    SELECT a.id, a.enrolled_at, v.id, v.key, v.name
    INTO v_assignment_id, v_enrolled_at, v_variant_id, p_variant_key, v_variant_name
    FROM assignments a
    JOIN variants v ON v.id = a.variant_id
    WHERE a.experiment_id = p_experiment_id AND a.user_id = p_user_id;
    
    IF v_assignment_id IS NULL THEN
        -- Create new assignment
        SELECT id, name INTO v_variant_id, v_variant_name
        FROM variants
        WHERE experiment_id = p_experiment_id AND key = p_variant_key;
        
        IF v_variant_id IS NULL THEN
            RAISE EXCEPTION 'Variant % not found for experiment %', p_variant_key, p_experiment_id;
        END IF;
        
        INSERT INTO assignments (experiment_id, user_id, variant_id, version, enrolled_at)
        VALUES (
            p_experiment_id, 
            p_user_id, 
            v_variant_id, 
            v_experiment_version,
            CASE WHEN p_enroll THEN NOW() ELSE NULL END
        )
        RETURNING id, enrolled_at INTO v_assignment_id, v_enrolled_at;
        
        v_is_new := TRUE;
        
        -- Create outbox event for new assignment
        INSERT INTO outbox_events (event_type, entity_id, entity_type, payload)
        VALUES (
            'assignment_created',
            v_assignment_id,
            'assignment',
            jsonb_build_object(
                'assignment_id', v_assignment_id,
                'experiment_id', p_experiment_id,
                'user_id', p_user_id,
                'variant_key', p_variant_key,
                'enrolled', p_enroll
            )
        );
    ELSIF p_enroll AND v_enrolled_at IS NULL THEN
        -- Update enrollment
        UPDATE assignments
        SET enrolled_at = NOW()
        WHERE id = v_assignment_id
        RETURNING enrolled_at INTO v_enrolled_at;
    END IF;
    
    -- Return assignment details
    RETURN QUERY
    SELECT 
        v_assignment_id,
        p_experiment_id,
        p_user_id,
        v_variant_id,
        p_variant_key,
        v_variant_name,
        v_enrolled_at,
        NOW(),
        v_is_new;
END;
$$ LANGUAGE plpgsql;

-- Bulk get assignments
CREATE OR REPLACE FUNCTION get_bulk_assignments(
    p_user_id TEXT,
    p_experiment_ids BIGINT[]
) RETURNS TABLE (
    experiment_id BIGINT,
    user_id TEXT,
    variant_id BIGINT,
    variant_key TEXT,
    variant_name TEXT,
    enrolled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.experiment_id,
        a.user_id,
        a.variant_id,
        v.key,
        v.name,
        a.enrolled_at,
        a.created_at
    FROM assignments a
    JOIN variants v ON v.id = a.variant_id
    WHERE a.user_id = p_user_id 
        AND a.experiment_id = ANY(p_experiment_ids);
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- EVENT PROCEDURES
-- =====================================================

-- Record event with assignment check
CREATE OR REPLACE FUNCTION record_event(
    p_experiment_id BIGINT,
    p_user_id TEXT,
    p_event_type TEXT,
    p_properties JSONB DEFAULT '{}',
    p_value NUMERIC DEFAULT NULL
) RETURNS TABLE (
    event_id BIGINT,
    assignment_id BIGINT,
    variant_key TEXT,
    created_at TIMESTAMPTZ
) AS $$
DECLARE
    v_event_id BIGINT;
    v_assignment_id BIGINT;
    v_variant_key TEXT;
BEGIN
    -- Get assignment (must exist)
    SELECT a.id, v.key
    INTO v_assignment_id, v_variant_key
    FROM assignments a
    JOIN variants v ON v.id = a.variant_id
    WHERE a.experiment_id = p_experiment_id AND a.user_id = p_user_id;
    
    IF v_assignment_id IS NULL THEN
        RAISE EXCEPTION 'No assignment found for user % in experiment %', p_user_id, p_experiment_id;
    END IF;
    
    -- Insert event
    INSERT INTO events (
        experiment_id, 
        user_id, 
        assignment_id, 
        event_type, 
        properties, 
        value
    )
    VALUES (
        p_experiment_id,
        p_user_id,
        v_assignment_id,
        p_event_type,
        p_properties,
        p_value
    )
    RETURNING id INTO v_event_id;
    
    -- Create outbox event
    INSERT INTO outbox_events (event_type, entity_id, entity_type, payload)
    VALUES (
        'event_recorded',
        v_event_id,
        'event',
        jsonb_build_object(
            'event_id', v_event_id,
            'experiment_id', p_experiment_id,
            'user_id', p_user_id,
            'event_type', p_event_type,
            'variant_key', v_variant_key,
            'properties', p_properties,
            'value', p_value
        )
    );
    
    RETURN QUERY
    SELECT v_event_id, v_assignment_id, v_variant_key, NOW();
END;
$$ LANGUAGE plpgsql;

-- Batch insert events
CREATE OR REPLACE FUNCTION record_batch_events(
    p_events JSONB
) RETURNS TABLE (
    success_count INT,
    error_count INT,
    errors JSONB
) AS $$
DECLARE
    v_event JSONB;
    v_success_count INT := 0;
    v_error_count INT := 0;
    v_errors JSONB := '[]'::JSONB;
    v_assignment_id BIGINT;
BEGIN
    FOR v_event IN SELECT * FROM jsonb_array_elements(p_events)
    LOOP
        BEGIN
            -- Get assignment
            SELECT a.id INTO v_assignment_id
            FROM assignments a
            WHERE a.experiment_id = (v_event->>'experiment_id')::BIGINT 
                AND a.user_id = v_event->>'user_id';
            
            IF v_assignment_id IS NOT NULL THEN
                -- Insert event
                INSERT INTO events (
                    experiment_id,
                    user_id,
                    assignment_id,
                    event_type,
                    properties,
                    value
                )
                VALUES (
                    (v_event->>'experiment_id')::BIGINT,
                    v_event->>'user_id',
                    v_assignment_id,
                    v_event->>'event_type',
                    COALESCE(v_event->'properties', '{}'),
                    (v_event->>'value')::NUMERIC
                );
                
                v_success_count := v_success_count + 1;
            ELSE
                v_error_count := v_error_count + 1;
                v_errors := v_errors || jsonb_build_object(
                    'user_id', v_event->>'user_id',
                    'experiment_id', v_event->>'experiment_id',
                    'error', 'No assignment found'
                );
            END IF;
        EXCEPTION WHEN OTHERS THEN
            v_error_count := v_error_count + 1;
            v_errors := v_errors || jsonb_build_object(
                'user_id', v_event->>'user_id',
                'error', SQLERRM
            );
        END;
    END LOOP;
    
    RETURN QUERY SELECT v_success_count, v_error_count, v_errors;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- ANALYTICS PROCEDURES
-- =====================================================

-- Get experiment metrics
CREATE OR REPLACE FUNCTION get_experiment_metrics(
    p_experiment_id BIGINT,
    p_start_date TIMESTAMPTZ DEFAULT NULL,
    p_end_date TIMESTAMPTZ DEFAULT NULL,
    p_event_types TEXT[] DEFAULT NULL
) RETURNS TABLE (
    variant_id BIGINT,
    variant_key TEXT,
    variant_name TEXT,
    is_control BOOLEAN,
    unique_users BIGINT,
    total_events BIGINT,
    conversion_count BIGINT,
    conversion_rate NUMERIC,
    avg_value NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    WITH variant_events AS (
        SELECT 
            v.id as variant_id,
            v.key as variant_key,
            v.name as variant_name,
            v.is_control,
            e.user_id,
            e.event_type,
            e.value,
            e.created_at
        FROM variants v
        LEFT JOIN assignments a ON a.variant_id = v.id
        LEFT JOIN events e ON e.assignment_id = a.id
            AND (p_start_date IS NULL OR e.created_at >= p_start_date)
            AND (p_end_date IS NULL OR e.created_at <= p_end_date)
            AND (p_event_types IS NULL OR e.event_type = ANY(p_event_types))
        WHERE v.experiment_id = p_experiment_id
    )
    SELECT 
        variant_id,
        variant_key,
        variant_name,
        is_control,
        COUNT(DISTINCT user_id) as unique_users,
        COUNT(*) as total_events,
        COUNT(*) FILTER (WHERE event_type = 'conversion') as conversion_count,
        ROUND(
            COUNT(*) FILTER (WHERE event_type = 'conversion')::NUMERIC / 
            NULLIF(COUNT(DISTINCT user_id), 0) * 100, 
            4
        ) as conversion_rate,
        ROUND(AVG(value), 2) as avg_value
    FROM variant_events
    GROUP BY variant_id, variant_key, variant_name, is_control
    ORDER BY is_control DESC, variant_id;
END;
$$ LANGUAGE plpgsql;

-- Get daily metrics
CREATE OR REPLACE FUNCTION get_daily_metrics(
    p_experiment_id BIGINT,
    p_days INT DEFAULT 7
) RETURNS TABLE (
    date DATE,
    variant_key TEXT,
    unique_users BIGINT,
    total_events BIGINT,
    conversions BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        DATE(e.created_at) as date,
        v.key as variant_key,
        COUNT(DISTINCT e.user_id) as unique_users,
        COUNT(*) as total_events,
        COUNT(*) FILTER (WHERE e.event_type = 'conversion') as conversions
    FROM events e
    JOIN assignments a ON a.id = e.assignment_id
    JOIN variants v ON v.id = a.variant_id
    WHERE e.experiment_id = p_experiment_id
        AND e.created_at >= CURRENT_DATE - INTERVAL '1 day' * p_days
    GROUP BY DATE(e.created_at), v.key
    ORDER BY date DESC, v.key;
END;
$$ LANGUAGE plpgsql;

-- Get funnel metrics
CREATE OR REPLACE FUNCTION get_funnel_metrics(
    p_experiment_id BIGINT,
    p_funnel_steps TEXT[]
) RETURNS TABLE (
    variant_key TEXT,
    step TEXT,
    step_order INT,
    users_reached BIGINT,
    conversion_rate NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    WITH funnel_data AS (
        SELECT 
            v.key as variant_key,
            e.user_id,
            e.event_type,
            ROW_NUMBER() OVER (PARTITION BY e.user_id, v.key ORDER BY e.created_at) as event_order
        FROM events e
        JOIN assignments a ON a.id = e.assignment_id
        JOIN variants v ON v.id = a.variant_id
        WHERE e.experiment_id = p_experiment_id
            AND e.event_type = ANY(p_funnel_steps)
    ),
    step_users AS (
        SELECT 
            variant_key,
            event_type,
            COUNT(DISTINCT user_id) as users
        FROM funnel_data
        GROUP BY variant_key, event_type
    )
    SELECT 
        su.variant_key,
        su.event_type as step,
        array_position(p_funnel_steps, su.event_type) as step_order,
        su.users as users_reached,
        ROUND(
            su.users::NUMERIC / 
            FIRST_VALUE(su.users) OVER (PARTITION BY su.variant_key ORDER BY array_position(p_funnel_steps, su.event_type)) * 100,
            2
        ) as conversion_rate
    FROM step_users su
    ORDER BY su.variant_key, array_position(p_funnel_steps, su.event_type);
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- UTILITY PROCEDURES
-- =====================================================

-- Clean up old events (for maintenance)
CREATE OR REPLACE FUNCTION cleanup_old_events(
    p_days_to_keep INT DEFAULT 90
) RETURNS TABLE (
    deleted_events BIGINT,
    deleted_outbox BIGINT
) AS $$
DECLARE
    v_deleted_events BIGINT;
    v_deleted_outbox BIGINT;
BEGIN
    -- Delete old events
    DELETE FROM events
    WHERE created_at < CURRENT_DATE - INTERVAL '1 day' * p_days_to_keep;
    GET DIAGNOSTICS v_deleted_events = ROW_COUNT;
    
    -- Delete processed outbox events
    DELETE FROM outbox_events
    WHERE processed_at IS NOT NULL 
        AND processed_at < CURRENT_DATE - INTERVAL '1 day' * 7;
    GET DIAGNOSTICS v_deleted_outbox = ROW_COUNT;
    
    RETURN QUERY SELECT v_deleted_events, v_deleted_outbox;
END;
$$ LANGUAGE plpgsql;

-- Get experiment statistics
CREATE OR REPLACE FUNCTION get_experiment_stats(
    p_experiment_id BIGINT
) RETURNS TABLE (
    total_users BIGINT,
    enrolled_users BIGINT,
    total_events BIGINT,
    avg_events_per_user NUMERIC,
    days_running INT,
    status TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(DISTINCT a.user_id) as total_users,
        COUNT(DISTINCT a.user_id) FILTER (WHERE a.enrolled_at IS NOT NULL) as enrolled_users,
        COUNT(DISTINCT e.id) as total_events,
        ROUND(COUNT(e.id)::NUMERIC / NULLIF(COUNT(DISTINCT a.user_id), 0), 2) as avg_events_per_user,
        EXTRACT(DAY FROM NOW() - MIN(e.created_at))::INT as days_running,
        exp.status
    FROM experiments exp
    LEFT JOIN assignments a ON a.experiment_id = exp.id
    LEFT JOIN events e ON e.assignment_id = a.id
    WHERE exp.id = p_experiment_id
    GROUP BY exp.status;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- INDEXES FOR STORED PROCEDURES
-- =====================================================

-- Create indexes if not exists
CREATE INDEX IF NOT EXISTS idx_assignments_lookup ON assignments(experiment_id, user_id);
CREATE INDEX IF NOT EXISTS idx_events_assignment ON events(assignment_id);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_outbox_pending ON outbox_events(processed_at) WHERE processed_at IS NULL;
