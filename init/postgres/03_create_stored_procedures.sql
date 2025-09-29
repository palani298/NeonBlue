-- Create stored procedures for V2 services

-- Function to record a single event
CREATE OR REPLACE FUNCTION record_event(
    p_experiment_id BIGINT,
    p_user_id VARCHAR(255),
    p_event_type VARCHAR(50),
    p_properties JSONB,
    p_value FLOAT DEFAULT NULL
)
    RETURNS TABLE(
        event_id UUID,
        experiment_id BIGINT,
        user_id VARCHAR(255),
        variant_id BIGINT,
        event_type VARCHAR(50),
        event_timestamp TIMESTAMP WITH TIME ZONE,
        status VARCHAR(20)
    ) AS $$
DECLARE
    v_assignment_id BIGINT;
    v_variant_id BIGINT;
    v_event_id UUID;
    v_timestamp TIMESTAMP WITH TIME ZONE := NOW();
BEGIN
    -- Get user's assignment for this experiment
    SELECT a.id, a.variant_id
    INTO v_assignment_id, v_variant_id
    FROM assignments a
    WHERE a.experiment_id = p_experiment_id 
    AND a.user_id = p_user_id
    LIMIT 1;
    
        -- If no assignment found, return error
        IF v_assignment_id IS NULL THEN
            RETURN QUERY SELECT 
                NULL::UUID as event_id,
                p_experiment_id as experiment_id,
                p_user_id as user_id,
                NULL::BIGINT as variant_id,
                p_event_type as event_type,
                v_timestamp as event_timestamp,
                'NO_ASSIGNMENT'::VARCHAR(20) as status;
            RETURN;
        END IF;
    
        -- Insert event
        INSERT INTO events (
            id, experiment_id, user_id, variant_id, event_type, 
            properties, timestamp, session_id, request_id
        ) VALUES (
            gen_random_uuid(), p_experiment_id, p_user_id, v_variant_id, p_event_type,
            p_properties, v_timestamp, NULL, NULL
        ) RETURNING id INTO v_event_id;
    
        -- Create outbox event for CDC
        INSERT INTO outbox_events (
            event_type, aggregate_id, aggregate_type, payload, created_at
        ) VALUES (
            'EVENT_CREATED', v_event_id::TEXT, 'Event', 
            jsonb_build_object(
                'event_id', v_event_id,
                'experiment_id', p_experiment_id,
                'user_id', p_user_id,
                'variant_id', v_variant_id,
                'event_type', p_event_type,
                'properties', p_properties,
                'timestamp', v_timestamp
            ), NOW()
        );
    
    -- Return success
    RETURN QUERY SELECT 
        v_event_id as event_id,
        p_experiment_id as experiment_id,
        p_user_id as user_id,
        v_variant_id as variant_id,
        p_event_type as event_type,
        v_timestamp as event_timestamp,
        'SUCCESS'::VARCHAR(20) as status;
END;
$$ LANGUAGE plpgsql;

-- Function to get experiment with variants
CREATE OR REPLACE FUNCTION get_experiment_with_variants(
    p_experiment_id BIGINT
)
RETURNS TABLE(
    id BIGINT,
    key VARCHAR(255),
    name VARCHAR(255),
    description TEXT,
    status experimentstatus,
    seed VARCHAR(255),
    version INTEGER,
    config JSONB,
    starts_at TIMESTAMP WITH TIME ZONE,
    ends_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    variant_id BIGINT,
    variant_key VARCHAR(255),
    variant_name VARCHAR(255),
    variant_description TEXT,
    variant_allocation_pct INTEGER,
    variant_is_control BOOLEAN,
    variant_config JSONB,
    variant_created_at TIMESTAMP WITH TIME ZONE,
    variant_updated_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.id,
        e.key,
        e.name,
        e.description,
        e.status,
        e.seed,
        e.version,
        e.config,
        e.starts_at,
        e.ends_at,
        e.created_at,
        e.updated_at,
        v.id as variant_id,
        v.key as variant_key,
        v.name as variant_name,
        v.description as variant_description,
        v.allocation_pct as variant_allocation_pct,
        v.is_control as variant_is_control,
        v.config as variant_config,
        v.created_at as variant_created_at,
        v.updated_at as variant_updated_at
    FROM experiments e
    LEFT JOIN variants v ON e.id = v.experiment_id
    WHERE e.id = p_experiment_id
    ORDER BY v.id;
END;
$$ LANGUAGE plpgsql;

-- Function to get or create assignment
CREATE OR REPLACE FUNCTION get_or_create_assignment(
    p_experiment_id BIGINT,
    p_user_id VARCHAR(255),
    p_enroll BOOLEAN DEFAULT FALSE
)
RETURNS TABLE(
    assignment_id BIGINT,
    experiment_id BIGINT,
    user_id VARCHAR(255),
    variant_id BIGINT,
    variant_key VARCHAR(255),
    variant_name VARCHAR(255),
    enrolled_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
DECLARE
    v_assignment_id BIGINT;
    v_variant_id BIGINT;
    v_variant_key VARCHAR(255);
    v_variant_name VARCHAR(255);
    v_experiment_seed VARCHAR(255);
    v_bucket_size INTEGER := 10000;
    v_hash_seed VARCHAR(255) := 'assignment_seed';
    v_user_hash INTEGER;
    v_bucket INTEGER;
    v_allocation_sum INTEGER := 0;
    v_variant_record RECORD;
BEGIN
    -- Check if assignment already exists
    SELECT a.id, a.variant_id, v.key, v.name, a.enrolled_at, a.created_at
    INTO v_assignment_id, v_variant_id, v_variant_key, v_variant_name, enrolled_at, created_at
    FROM assignments a
    JOIN variants v ON a.variant_id = v.id
    WHERE a.experiment_id = p_experiment_id AND a.user_id = p_user_id;
    
    IF v_assignment_id IS NOT NULL THEN
        -- Return existing assignment
        assignment_id := v_assignment_id;
        experiment_id := p_experiment_id;
        user_id := p_user_id;
        variant_id := v_variant_id;
        variant_key := v_variant_key;
        variant_name := v_variant_name;
        RETURN NEXT;
        RETURN;
    END IF;
    
    -- Get experiment seed
    SELECT e.seed INTO v_experiment_seed
    FROM experiments e
    WHERE e.id = p_experiment_id AND e.status = 'ACTIVE';
    
    IF v_experiment_seed IS NULL THEN
        RAISE EXCEPTION 'Experiment not found or not active';
    END IF;
    
    -- Calculate user hash and bucket
    v_user_hash := ('x' || substr(md5(p_user_id || v_experiment_seed), 1, 8))::bit(32)::int;
    v_bucket := v_user_hash % v_bucket_size;
    
    -- Find variant based on allocation
    FOR v_variant_record IN
        SELECT v.id, v.key, v.name, v.allocation_pct
        FROM variants v
        WHERE v.experiment_id = p_experiment_id
        ORDER BY v.id
    LOOP
        v_allocation_sum := v_allocation_sum + v_variant_record.allocation_pct;
        IF v_bucket < v_allocation_sum THEN
            v_variant_id := v_variant_record.id;
            v_variant_key := v_variant_record.key;
            v_variant_name := v_variant_record.name;
            EXIT;
        END IF;
    END LOOP;
    
    -- Fallback to first variant if no variant was selected
    IF v_variant_id IS NULL THEN
        SELECT v.id, v.key, v.name
        INTO v_variant_id, v_variant_key, v_variant_name
        FROM variants v
        WHERE v.experiment_id = p_experiment_id
        ORDER BY v.id
        LIMIT 1;
    END IF;
    
    -- Create assignment
    INSERT INTO assignments (experiment_id, user_id, variant_id, version, source, context, assigned_at, enrolled_at)
    VALUES (
        p_experiment_id,
        p_user_id,
        v_variant_id,
        1,
        'api',
        jsonb_build_object('bucket', v_bucket, 'hash', v_user_hash),
        NOW(),
        CASE WHEN p_enroll THEN NOW() ELSE NULL END
    )
    RETURNING id INTO v_assignment_id;
    
    -- Create outbox event
    INSERT INTO outbox_events (event_type, aggregate_id, aggregate_type, payload, created_at)
    VALUES (
        'ASSIGNMENT_CREATED',
        v_assignment_id::text,
        'assignment',
        jsonb_build_object(
            'assignment_id', v_assignment_id,
            'experiment_id', p_experiment_id,
            'user_id', p_user_id,
            'variant_id', v_variant_id
        ),
        NOW()
    );
    
    -- Return assignment
    assignment_id := v_assignment_id;
    experiment_id := p_experiment_id;
    user_id := p_user_id;
    variant_id := v_variant_id;
    variant_key := v_variant_key;
    variant_name := v_variant_name;
    enrolled_at := CASE WHEN p_enroll THEN NOW() ELSE NULL END;
    created_at := NOW();
    
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- Function to record batch events
CREATE OR REPLACE FUNCTION record_batch_events(events jsonb)
RETURNS TABLE(success_count INTEGER, error_count INTEGER, errors jsonb) AS $$
DECLARE
    event_record jsonb;
    success_count INTEGER := 0;
    error_count INTEGER := 0;
    errors jsonb := '[]'::jsonb;
    v_assignment_id BIGINT;
    v_variant_id BIGINT;
    v_event_id BIGINT;
BEGIN
    FOR event_record IN SELECT * FROM jsonb_array_elements(events)
    LOOP
        BEGIN
            -- Check if assignment exists
            SELECT a.id, a.variant_id
            INTO v_assignment_id, v_variant_id
            FROM assignments a
            WHERE a.experiment_id = (event_record->>'experiment_id')::bigint
            AND a.user_id = event_record->>'user_id';
            
            IF v_assignment_id IS NULL THEN
                RAISE EXCEPTION 'No assignment found for user % in experiment %', 
                    event_record->>'user_id', event_record->>'experiment_id';
            END IF;
            
            -- Insert event
            INSERT INTO events (experiment_id, user_id, event_type, properties, timestamp, session_id, request_id)
            VALUES (
                (event_record->>'experiment_id')::bigint,
                event_record->>'user_id',
                event_record->>'event_type',
                event_record->'properties',
                COALESCE((event_record->>'timestamp')::timestamp with time zone, NOW()),
                event_record->>'session_id',
                event_record->>'request_id'
            )
            RETURNING id INTO v_event_id;
            
            -- Create outbox event
            INSERT INTO outbox_events (event_type, aggregate_id, aggregate_type, payload, created_at)
            VALUES (
                'EVENT_CREATED',
                v_event_id::text,
                'event',
                jsonb_build_object(
                    'event_id', v_event_id,
                    'experiment_id', (event_record->>'experiment_id')::bigint,
                    'user_id', event_record->>'user_id',
                    'variant_id', v_variant_id,
                    'event_type', event_record->>'event_type'
                ),
                NOW()
            );
            
            success_count := success_count + 1;
            
        EXCEPTION WHEN OTHERS THEN
            error_count := error_count + 1;
            errors := errors || jsonb_build_object(
                'event', event_record,
                'error', SQLERRM
            );
        END;
    END LOOP;
    
    RETURN QUERY SELECT success_count, error_count, errors;
END;
$$ LANGUAGE plpgsql;

-- Function to get bulk assignments
CREATE OR REPLACE FUNCTION get_bulk_assignments(
    p_user_id VARCHAR(255),
    p_experiment_ids BIGINT[]
)
RETURNS TABLE(
    experiment_id BIGINT,
    user_id VARCHAR(255),
    variant_id BIGINT,
    variant_key VARCHAR(255),
    variant_name VARCHAR(255),
    enrolled_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.experiment_id,
        a.user_id,
        a.variant_id,
        v.key as variant_key,
        v.name as variant_name,
        a.enrolled_at,
        a.created_at
    FROM assignments a
    JOIN variants v ON a.variant_id = v.id
    WHERE a.user_id = p_user_id
    AND a.experiment_id = ANY(p_experiment_ids);
END;
$$ LANGUAGE plpgsql;
