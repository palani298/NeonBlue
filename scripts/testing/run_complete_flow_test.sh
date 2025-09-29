#!/bin/bash

echo "🚀 Complete Flow Test - NeonBlue Experimentation Platform"
echo "========================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if a service is running
check_service() {
    local service_name=$1
    local url=$2
    local expected_status=${3:-200}
    
    echo -n "🔍 Checking $service_name... "
    
    if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "$expected_status"; then
        echo -e "${GREEN}✅ Running${NC}"
        return 0
    else
        echo -e "${RED}❌ Not accessible${NC}"
        return 1
    fi
}

# Function to install Python dependencies
install_dependencies() {
    echo "📦 Installing required Python packages..."
    
    # Check if packages are installed
    if ! python -c "import httpx, psycopg2, clickhouse_connect" 2>/dev/null; then
        echo "Installing missing packages..."
        pip install httpx psycopg2-binary clickhouse-connect
    else
        echo "✅ All packages already installed"
    fi
}

# Function to setup CDC pipeline
setup_cdc_pipeline() {
    echo -e "\n🔧 Setting up CDC Pipeline..."
    
    # Check if Debezium connector exists
    connector_status=$(curl -s "http://localhost:8083/connectors/experiments-postgres-connector/status" 2>/dev/null)
    
    if echo "$connector_status" | grep -q "RUNNING"; then
        echo "✅ CDC connector already running"
    else
        echo "📡 Creating Debezium connector..."
        
        # Create the connector
        curl -X POST -H "Content-Type: application/json" \
             -d @debezium/debezium-connector-config.json \
             http://localhost:8083/connectors
        
        if [ $? -eq 0 ]; then
            echo "✅ Debezium connector created"
            echo "⏳ Waiting for connector to start..."
            sleep 10
        else
            echo -e "${RED}❌ Failed to create Debezium connector${NC}"
        fi
    fi
    
    # Check connector status
    echo "🔍 Checking connector status..."
    curl -s "http://localhost:8083/connectors/experiments-postgres-connector/status" | jq .
}

# Function to verify ClickHouse schema
verify_clickhouse_schema() {
    echo -e "\n🏠 Verifying ClickHouse schema..."
    
    # Check if database exists
    if curl -s "http://localhost:8123/?query=SHOW DATABASES" | grep -q "experiments"; then
        echo "✅ ClickHouse database exists"
    else
        echo "📊 Creating ClickHouse database..."
        curl -s "http://localhost:8123/" --data-binary "CREATE DATABASE IF NOT EXISTS experiments"
    fi
    
    # Check if tables exist
    tables=$(curl -s "http://localhost:8123/?query=SHOW TABLES FROM experiments")
    
    if echo "$tables" | grep -q "events"; then
        echo "✅ ClickHouse events table exists"
    else
        echo "📋 Creating ClickHouse tables from schema..."
        if [ -f "init/clickhouse/01_init.sql" ]; then
            curl -s "http://localhost:8123/" --data-binary @init/clickhouse/01_init.sql
            echo "✅ ClickHouse schema created"
        else
            echo -e "${YELLOW}⚠️ ClickHouse init script not found${NC}"
        fi
    fi
}

# Function to show useful monitoring commands
show_monitoring_commands() {
    echo -e "\n📊 Useful Monitoring Commands:"
    echo "================================"
    echo "1. Check Kafka Topics:"
    echo "   docker exec experiments-kafka kafka-topics --list --bootstrap-server localhost:9092"
    echo
    echo "2. Monitor Kafka Events:"
    echo "   docker exec experiments-kafka kafka-console-consumer \\"
    echo "     --bootstrap-server localhost:9092 \\"
    echo "     --topic experiments_events \\"
    echo "     --from-beginning"
    echo
    echo "3. Check PostgreSQL Outbox:"
    echo "   docker exec experiments-postgres psql -U experiments -d experiments \\"
    echo "     -c \"SELECT * FROM outbox_events ORDER BY created_at DESC LIMIT 10;\""
    echo
    echo "4. Query ClickHouse Events:"
    echo "   curl -s \"http://localhost:8123/?query=SELECT * FROM experiments.events ORDER BY timestamp DESC LIMIT 10 FORMAT Pretty\""
    echo
    echo "5. Monitor Debezium Status:"
    echo "   curl -s \"http://localhost:8083/connectors/experiments-postgres-connector/status\" | jq"
}

# Main execution
main() {
    echo "Starting complete flow test setup and execution..."
    echo
    
    # Step 1: Check services
    echo "🔍 Checking required services..."
    services_ok=true
    
    check_service "FastAPI" "http://localhost:8000/health" || services_ok=false
    check_service "PostgreSQL" "http://localhost:8000/health" || services_ok=false  # API health includes DB check
    check_service "Redis" "http://localhost:8000/health" || services_ok=false      # API health includes Redis check
    check_service "Kafka UI" "http://localhost:8080" || services_ok=false
    check_service "Debezium" "http://localhost:8083/connectors" || services_ok=false
    check_service "ClickHouse" "http://localhost:8123/?query=SELECT 1" || services_ok=false
    
    if [ "$services_ok" = false ]; then
        echo -e "\n${RED}❌ Some services are not running. Please start the docker-compose stack first:${NC}"
        echo "   cd config && docker-compose up -d"
        echo "   Wait for all services to be ready, then run this script again."
        exit 1
    fi
    
    echo -e "\n${GREEN}✅ All services are running!${NC}"
    
    # Step 2: Install Python dependencies
    install_dependencies
    
    # Step 3: Setup CDC pipeline
    setup_cdc_pipeline
    
    # Step 4: Verify ClickHouse schema
    verify_clickhouse_schema
    
    # Step 5: Run the complete flow test
    echo -e "\n🧪 Running Complete Flow Test..."
    echo "=================================="
    
    python test_complete_flow.py
    test_exit_code=$?
    
    # Step 6: Show monitoring commands
    show_monitoring_commands
    
    # Final result
    if [ $test_exit_code -eq 0 ]; then
        echo -e "\n${GREEN}🎉 Complete Flow Test PASSED!${NC}"
        echo "The entire pipeline from API -> PostgreSQL -> Kafka -> ClickHouse is working correctly."
    else
        echo -e "\n${RED}❌ Complete Flow Test FAILED!${NC}"
        echo "Check the error messages above and verify your service configurations."
    fi
    
    echo -e "\n🔗 Useful URLs:"
    echo "   • API Docs: http://localhost:8000/docs"
    echo "   • Swagger UI: http://localhost:8000/api/v1/docs"
    echo "   • Kafka UI: http://localhost:8080"
    echo "   • React Dashboard: http://localhost:3001"
    echo "   • Grafana: http://localhost:3000"
    
    exit $test_exit_code
}

# Check if running from correct directory
if [ ! -f "test_complete_flow.py" ]; then
    echo -e "${RED}❌ Please run this script from the project root directory${NC}"
    exit 1
fi

# Run main function
main
