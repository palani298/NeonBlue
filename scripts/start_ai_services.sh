#!/bin/bash
# Start AI-Enhanced Services - Separate from main demo flow

set -e

echo "🚀 Starting NeonBlue AI-Enhanced Services..."
echo "This runs separately from the main demo to avoid disruption"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found. Please install docker-compose."
    exit 1
fi

# Check if main services are running (optional)
if docker ps | grep -q "experiments-api"; then
    echo "✅ Main NeonBlue services detected - AI services will complement them"
else
    echo "⚠️  Main NeonBlue services not detected - you may want to start them first with:"
    echo "   docker-compose -f config/docker-compose.yml up -d"
    echo ""
    read -p "Continue with AI services only? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# Check environment variables
echo "🔧 Checking environment setup..."

if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  OPENAI_API_KEY not set. AI features will be limited."
    echo "   Set it with: export OPENAI_API_KEY='your-key-here'"
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  ANTHROPIC_API_KEY not set (optional for Claude support)"
fi

# Create network if needed
echo "📡 Ensuring network exists..."
docker network create experiments-network 2>/dev/null || echo "Network already exists"

# Start AI services
echo "🧠 Starting AI-enhanced services..."
docker-compose -f config/docker-compose-ai.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to initialize..."
sleep 10

# Health checks
echo "🔍 Checking service health..."

services=(
    "experiments-chromadb:8000"
    "experiments-mcp-router:8000"
    "experiments-mcp-exp-intel:8000"
    "experiments-ai-analytics:8000"
)

for service in "${services[@]}"; do
    container_name="${service%%:*}"
    port="${service##*:}"
    
    if docker ps | grep -q "$container_name"; then
        echo "✅ $container_name is running"
        
        # Wait a bit more for the service to be ready
        sleep 2
        
        # Test health endpoint if available
        if curl -s "http://localhost:$port/health" > /dev/null 2>&1; then
            echo "   🟢 Health check passed"
        else
            echo "   🟡 Service starting (health check not ready yet)"
        fi
    else
        echo "❌ $container_name failed to start"
    fi
done

echo ""
echo "🎉 AI-Enhanced Services Status:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 ChromaDB (Vector Store):      http://localhost:8001"
echo "🤖 MCP Router (Intelligence):    http://localhost:8002/status"
echo "🧠 Experiment Intelligence:      http://localhost:8003/health"
echo "📈 AI Analytics API:            http://localhost:8006/health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🚀 AI Services are now running alongside your main NeonBlue platform!"
echo ""
echo "Next Steps:"
echo "1. Your existing demo at http://localhost:8000 continues to work"
echo "2. Try the new AI features:"
echo "   curl -X POST http://localhost:8002/route -d '{\"experiment_id\":\"test_exp\",\"type\":\"experiment\"}'"
echo "   curl http://localhost:8003/health"
echo "3. Check the stream processor logs:"
echo "   docker logs experiments-ai-processor -f"
echo ""
echo "🛑 To stop AI services: docker-compose -f config/docker-compose-ai.yml down"

