-- Initialize PostgreSQL for experiments platform

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Create experiments database if not exists
-- (This is handled by POSTGRES_DB env var, but kept for reference)
-- CREATE DATABASE experiments;

-- Switch to experiments database
\c experiments;

-- Enable logical replication for CDC
-- Note: These settings require a restart to take effect
-- They are also set in postgresql.conf for immediate effect
ALTER SYSTEM SET wal_level = logical;
ALTER SYSTEM SET max_replication_slots = 4;
ALTER SYSTEM SET max_wal_senders = 4;

-- Note: Replication slot creation will be handled after restart
-- or in a separate initialization step

-- Create simple replication slot for Debezium (if wal_level is logical)
DO $$
BEGIN
    IF current_setting('wal_level') = 'logical' THEN
        PERFORM pg_create_logical_replication_slot('debezium', 'pgoutput');
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        -- Ignore if replication slot already exists or wal_level is not logical
        NULL;
END $$;

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE experiments TO experiments;
GRANT USAGE ON SCHEMA public TO experiments;
GRANT CREATE ON SCHEMA public TO experiments;

-- Performance settings
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET pg_stat_statements.track = 'all';
ALTER SYSTEM SET pg_stat_statements.max = 10000;
