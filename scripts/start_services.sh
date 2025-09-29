#!/bin/bash

echo "🚀 Starting NeonBlue Services"
echo "============================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if Docker is running
echo -n "🐳 Checking Docker daemon... "
if docker info >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Running${NC}"
else
    echo -e "${RED}❌ Not running${NC}"
    echo -e "${YELLOW}Please start Docker Desktop and try again${NC}"
    echo "💡 On macOS: open -a Docker"
    exit 1
fi

# Navigate to config directory
cd config || {
    echo -e "${RED}❌ Could not find config directory${NC}"
    exit 1
}

# Start services
echo "🔄 Starting services with docker compose..."
docker compose up -d

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Services started successfully${NC}"
else
    echo -e "${RED}❌ Failed to start services${NC}"
    exit 1
fi

echo ""
echo "⏳ Waiting for services to initialize..."
echo "   This may take 2-3 minutes for first startup"
echo ""

# Wait and check services
sleep 10

echo "🔍 Checking service status..."
docker compose ps

echo ""
echo "📊 Service Health Check:"

# Check each service
services=(
    "FastAPI:http://localhost:8000/health"
    "Kafka UI:http://localhost:8080"
    "Debezium:http://localhost:8083/connectors"
    "ClickHouse:http://localhost:8123/?query=SELECT 1"
)

all_ready=true
for service in "${services[@]}"; do
    name=$(echo "$service" | cut -d: -f1)
    url=$(echo "$service" | cut -d: -f2-)
    
    echo -n "   $name... "
    
    # Try up to 30 times (5 minutes total)
    for i in {1..30}; do
        if curl -s "$url" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ Ready${NC}"
            break
        fi
        
        if [ $i -eq 30 ]; then
            echo -e "${RED}❌ Not ready after 5 minutes${NC}"
            all_ready=false
        elif [ $i -eq 1 ]; then
            echo -n "waiting"
        else
            echo -n "."
        fi
        
        sleep 10
    done
done

if [ "$all_ready" = true ]; then
    echo ""
    echo -e "${GREEN}🎉 All services are ready!${NC}"
    echo ""
    echo "🧪 You can now run the tests:"
    echo "   • Quick setup check: python3 verify_setup.py"
    echo "   • Complete test:      ./run_complete_flow_test.sh" 
    echo "   • Step by step:       python3 manual_flow_test.py"
    echo ""
    echo "🔗 Service URLs:"
    echo "   • API Docs:    http://localhost:8000/docs"
    echo "   • Kafka UI:    http://localhost:8080"
    echo "   • Debezium:    http://localhost:8083"
else
    echo ""
    echo -e "${YELLOW}⚠️ Some services are not ready yet${NC}"
    echo "   Wait a few more minutes and check manually:"
    echo "   docker compose logs -f"
fi
