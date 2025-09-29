#!/bin/bash

echo "🚀 Setting up CDC Pipeline for Experimentation Platform (v2)"
echo "=================================================="

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if ClickHouse is ready
echo "🔍 Checking ClickHouse availability..."
for i in {1..30}; do
    if curl -s "http://localhost:8123/?query=SELECT 1" > /dev/null 2>&1; then
        echo "✅ ClickHouse is ready"
        break
    fi
    echo "⏳ Waiting for ClickHouse... (attempt $i/30)"
    sleep 2
done

# Create ClickHouse database
echo "📊 Creating ClickHouse database..."
curl -s "http://localhost:8123/" --data-binary @clickhouse-database.sql

# Create ClickHouse tables
echo "📊 Creating ClickHouse tables..."
curl -s "http://localhost:8123/" --data-binary @clickhouse-processed-events.sql
curl -s "http://localhost:8123/" --data-binary @clickhouse-raw-events.sql
curl -s "http://localhost:8123/" --data-binary @clickhouse-events-mv.sql
curl -s "http://localhost:8123/" --data-binary @clickhouse-reports.sql

echo "✅ ClickHouse schema created successfully"

# Check if Debezium is ready
echo "🔍 Checking Debezium availability..."
for i in {1..30}; do
    if curl -s "http://localhost:8083/connectors" > /dev/null 2>&1; then
        echo "✅ Debezium is ready"
        break
    fi
    echo "⏳ Waiting for Debezium... (attempt $i/30)"
    sleep 2
done

# Create Debezium connector
echo "🔌 Creating Debezium connector..."
curl -X POST -H "Content-Type: application/json" \
     -d @debezium-connector-config.json \
     http://localhost:8083/connectors

if [ $? -eq 0 ]; then
    echo "✅ Debezium connector created successfully"
else
    echo "❌ Failed to create Debezium connector"
fi

# Wait for connector to start
echo "⏳ Waiting for connector to start..."
sleep 15

# Check connector status
echo "🔍 Checking connector status..."
curl -s "http://localhost:8083/connectors/experiments-postgres-connector/status" | jq .

# Check Kafka topics
echo "📋 Checking Kafka topics..."
docker exec experiments-kafka kafka-topics --bootstrap-server localhost:9092 --list

# Test data flow
echo "🧪 Testing data flow..."
echo "Creating test event..."

# Create a test event via API with correct timestamp format
curl -X POST "http://localhost:8001/api/v1/events/" \
     -H "Authorization: Bearer admin_token_123" \
     -H "Content-Type: application/json" \
     -d '{
       "experiment_id": 1,
       "user_id": "test_user_cdc",
       "event_type": "test_event",
       "properties": {"test": "cdc_pipeline", "score": 100}
     }'

echo ""
echo "⏳ Waiting for data to flow through pipeline..."
sleep 20

# Check if data reached ClickHouse
echo "🔍 Checking if data reached ClickHouse..."
curl -s "http://localhost:8123/?query=SELECT count() FROM experiments_analytics.events_processed WHERE user_id = 'test_user_cdc'"

echo ""
echo "🎉 CDC Pipeline setup complete!"
echo ""
echo "📊 Available ClickHouse tables:"
curl -s "http://localhost:8123/?query=SHOW TABLES FROM experiments_analytics"

echo ""
echo "🔗 Access points:"
echo "  - ClickHouse: http://localhost:8123"
echo "  - Debezium: http://localhost:8083"
echo "  - Kafka UI: http://localhost:8080"
echo "  - API: http://localhost:8001"
echo ""
echo "📈 Sample queries:"
echo "  - Events: SELECT * FROM experiments_analytics.events_processed LIMIT 10"
echo "  - Reports: SELECT * FROM experiments_analytics.experiment_reports LIMIT 10"
