#!/bin/bash

# Setup ClickHouse schema for experiments platform
# This script runs the schema creation statements one by one

CLICKHOUSE_URL="http://localhost:8123"

echo "Setting up ClickHouse schema..."

# Create database
echo "Creating database..."
curl -s "$CLICKHOUSE_URL" -d "CREATE DATABASE IF NOT EXISTS experiments_analytics"

# Run schema file line by line
echo "Running schema statements..."
while IFS= read -r line; do
    # Skip empty lines and comments
    if [[ -n "$line" && ! "$line" =~ ^[[:space:]]*-- ]]; then
        echo "Executing: $line"
        curl -s "$CLICKHOUSE_URL" -d "$line"
        echo ""
    fi
done < clickhouse/recreate_schema_json_each_row.sql

echo "ClickHouse schema setup complete!"
