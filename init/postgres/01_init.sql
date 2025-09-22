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
ALTER SYSTEM SET wal_level = logical;
ALTER SYSTEM SET max_replication_slots = 4;
ALTER SYSTEM SET max_wal_senders = 4;

-- Create replication slot for Debezium
SELECT pg_create_logical_replication_slot('debezium', 'pgoutput');

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE experiments TO experiments;
GRANT USAGE ON SCHEMA public TO experiments;
GRANT CREATE ON SCHEMA public TO experiments;

-- Performance settings
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET pg_stat_statements.track = 'all';
ALTER SYSTEM SET pg_stat_statements.max = 10000;