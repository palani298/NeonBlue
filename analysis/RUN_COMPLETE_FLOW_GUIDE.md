# 🚀 Complete Flow Execution Guide

## 📍 **Docker Files Location & Setup**

### **Docker Configuration Files**
```
config/
├── 📄 docker-compose.yml          # Main orchestration file (8 services)
├── 📄 Dockerfile                  # FastAPI application container
├── 📄 prometheus.yml              # Monitoring configuration
├── 📄 requirements.txt            # Python dependencies
├── 📁 init/                       # Database initialization
│   ├── postgres/                  # PostgreSQL setup scripts
│   └── clickhouse/               # ClickHouse setup scripts
└── 📁 grafana/                    # Dashboard configurations
```

### **Complete Service Stack**
```
🐳 8 Docker Services:
├── api                  # FastAPI application (port 8000)
├── postgres            # PostgreSQL database (port 5432)
├── redis               # Caching layer (port 6379)
├── kafka               # Event streaming (port 9092)
├── debezium            # Change Data Capture (port 8083)
├── clickhouse          # Analytics database (port 8123)
├── grafana             # Monitoring dashboards (port 3000)
└── prometheus          # Metrics collection (port 9090)
```

---

## ⚡ **Quick Start: Run Complete Flow**

### **🎯 One-Command Startup**
```bash
# From project root
./scripts/start_services.sh
```

### **🔄 Manual Step-by-Step**
```bash
# 1. Start Docker services
cd config
docker compose up -d

# 2. Wait for services to be ready (2-3 minutes)
docker compose logs -f api

# 3. Set up CDC pipeline
cd ..
./scripts/setup_cdc_pipeline_v2.sh

# 4. Run complete end-to-end test
python tests/end-to-end/test_end_to_end_flow.py
```

---

## 🧪 **Testing the Complete Flow**

### **Available Test Scripts**
```
tests/
├── end-to-end/
│   ├── test_end_to_end_flow.py      # 🎯 Main complete flow test
│   └── test_complete_flow.py        # Alternative flow test
└── integration/
    ├── verify_setup.py              # ✅ Quick setup verification
    ├── setup_and_test_analytics.py  # 📊 Analytics pipeline test
    └── direct_db_test.py            # 💾 Direct database test
```

### **🎯 Run Complete End-to-End Test**
```bash
# Test: PostgreSQL → Debezium CDC → Kafka → ClickHouse
python tests/end-to-end/test_end_to_end_flow.py

# Expected output:
# ✅ User Created: e2e_test_user_xxxxx
# ✅ Assignment Created: ID 7
# ✅ Events Created: 4 events
# ✅ Kafka Pipeline: SUCCESS
# ✅ ClickHouse Analytics: SUCCESS
```

### **📊 Verify Setup**
```bash
# Quick health check
python tests/integration/verify_setup.py

# Expected output:
# ✅ PostgreSQL: Connected
# ✅ Redis: Connected  
# ✅ ClickHouse: Connected
# ✅ API: Running
# ✅ All services healthy
```

---

## 🔧 **Troubleshooting Common Issues**

### **Issue 1: Docker Not Running**
```bash
# Error: Cannot connect to Docker daemon
# Solution:
open -a Docker  # macOS
# Wait for Docker Desktop to start, then retry
```

### **Issue 2: Port Conflicts**
```bash
# Error: Port 8000 already in use
# Solution: Stop conflicting services
lsof -ti:8000 | xargs kill -9
docker compose down
docker compose up -d
```

### **Issue 3: Services Not Ready**
```bash
# Check service health
docker compose ps
docker compose logs api
docker compose logs postgres

# Wait for all services to show "healthy"
```

### **Issue 4: CDC Pipeline Issues**
```bash
# Check Debezium connector status
curl http://localhost:8083/connectors

# Reset if needed
./scripts/setup_cdc_pipeline_v2.sh
```

### **Issue 5: ClickHouse Not Processing**
```bash
# Check ClickHouse connection
curl http://localhost:8123/

# Restart Kafka consumer
curl -s "http://localhost:8123/" --data "DETACH TABLE experiments_analytics.raw_events_kafka"
curl -s "http://localhost:8123/" --data "ATTACH TABLE experiments_analytics.raw_events_kafka"
```

---

## 📊 **Accessing Services After Startup**

### **🌐 Web Interfaces**
```bash
# FastAPI Application & Docs
open http://localhost:8000
open http://localhost:8000/docs

# Grafana Dashboards
open http://localhost:3000
# Login: admin/admin

# Kafka UI
open http://localhost:8080

# ClickHouse Interface
curl "http://localhost:8123/"
```

### **💾 Database Connections**
```bash
# PostgreSQL
docker exec -it experiments-postgres psql -U experiments -d experiments

# ClickHouse
docker exec -it experiments-clickhouse clickhouse-client

# Redis
docker exec -it experiments-redis redis-cli
```

---

## 🎯 **Complete Flow Validation**

### **Step 1: Verify All Services**
```bash
./scripts/start_services.sh
python tests/integration/verify_setup.py
```

### **Step 2: Test End-to-End Pipeline**
```bash
python tests/end-to-end/test_end_to_end_flow.py
```

### **Step 3: Check Data Flow**
```bash
# Check PostgreSQL
docker exec experiments-postgres psql -U experiments -d experiments -c "SELECT COUNT(*) FROM assignments"

# Check Kafka
docker exec experiments-kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic experiments_events --max-messages 1 --timeout-ms 3000

# Check ClickHouse
curl -s "http://localhost:8123/" --data "SELECT COUNT(*) FROM experiments_analytics.events_processed"
```

### **Step 4: View Analytics**
```bash
# Open Grafana dashboards
open http://localhost:3000

# Query ClickHouse analytics
curl -s "http://localhost:8123/" --data "
SELECT 
    variant_key,
    count() as events,
    uniq(user_id) as users 
FROM experiments_analytics.events_processed 
GROUP BY variant_key 
FORMAT Pretty"
```

---

## 🔄 **Restart/Reset Instructions**

### **🔄 Restart Everything**
```bash
cd config
docker compose down
docker compose up -d
./setup_cdc_pipeline_v2.sh
```

### **🗑️ Clean Reset (Remove All Data)**
```bash
cd config
docker compose down -v  # Remove volumes
docker system prune -f  # Clean up
docker compose up -d
./setup_cdc_pipeline_v2.sh
```

### **🔧 Partial Restart (Specific Services)**
```bash
# Restart just the API
docker compose restart api

# Restart analytics pipeline
docker compose restart clickhouse debezium kafka

# Rebuild API container
docker compose build api
docker compose up -d api
```

---

## 📈 **Performance Monitoring**

### **Real-time Monitoring**
```bash
# Watch Docker logs
docker compose logs -f api

# Monitor resource usage
docker stats

# Check service health
watch -n 5 'docker compose ps'
```

### **Analytics Performance**
```bash
# Query performance metrics
curl -s "http://localhost:8123/" --data "
SELECT 
    'Events processed' as metric,
    COUNT(*) as value 
FROM experiments_analytics.events_processed
UNION ALL
SELECT 
    'Assignments created' as metric,
    COUNT(*) as value 
FROM assignments
FORMAT Pretty"
```

---

## ✅ **Success Indicators**

### **🎯 Complete Flow Working When:**
- ✅ All 8 Docker containers running
- ✅ API responds at http://localhost:8000/health
- ✅ Grafana dashboards load at http://localhost:3000
- ✅ End-to-end test passes completely
- ✅ Data flows: PostgreSQL → Kafka → ClickHouse
- ✅ Analytics queries return data

### **📊 Test Results Should Show:**
```
🎯 END-TO-END TEST SUMMARY
==================================================
✅ User Created: e2e_test_user_xxxxx
✅ Assignment Created: ID 7
✅ Events Created: 4 events
✅ Kafka Pipeline: SUCCESS
✅ ClickHouse Analytics: SUCCESS

🎉 OVERALL RESULT: SUCCESS
```

---

## 🎉 **Ready to Run!**

The NeonBlue platform is **fully configured and ready to run** with:

✅ **Complete Docker setup** in `config/`  
✅ **One-command startup** with `./scripts/start_services.sh`  
✅ **Comprehensive testing** with end-to-end validation  
✅ **Production monitoring** with Grafana + Prometheus  
✅ **Real-time analytics** with ClickHouse pipeline  

**Just run `./scripts/start_services.sh` and you're ready to go!** 🚀

---

**🔗 Next Steps:**
1. Start services: `./scripts/start_services.sh`
2. Test flow: `python tests/end-to-end/test_end_to_end_flow.py`
3. View analytics: http://localhost:3000
4. Experiment with API: http://localhost:8000/docs
