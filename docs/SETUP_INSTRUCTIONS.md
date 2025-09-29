# Complete Flow Test Setup Instructions

## 🚨 Current Status
Your Docker daemon is not running. You'll need to start Docker before we can run the complete flow tests.

## 📋 Step-by-Step Setup

### 1. Start Docker Desktop
```bash
# On macOS, start Docker Desktop application
# You can find it in Applications folder or use Spotlight search
open -a Docker
```

**OR** if you prefer command line (if Docker Desktop is already running):
```bash
# Check if Docker daemon is running
docker info
```

### 2. Wait for Docker to be Ready
Wait for Docker Desktop to fully start (you'll see the Docker whale icon in your menu bar turn steady).

### 3. Start All Services
Once Docker is ready, run:
```bash
cd config
docker compose up -d
```

This will start:
- ✅ PostgreSQL (port 5432)
- ✅ Redis (port 6379) 
- ✅ Kafka + Zookeeper (ports 9092, 2181)
- ✅ Kafka UI (port 8080)
- ✅ Debezium (port 8083)
- ✅ ClickHouse (ports 8123, 9000)
- ✅ FastAPI application (port 8000)

### 4. Verify Services Started
```bash
# Check all containers are running
docker compose ps

# Should show all services as "running"
```

### 5. Run the Complete Flow Tests

#### Option A: Quick Automated Test
```bash
./run_complete_flow_test.sh
```

#### Option B: Setup Verification First
```bash
python3 verify_setup.py
```

#### Option C: Step-by-Step Manual Test
```bash
python3 manual_flow_test.py
```

#### Option D: Full Comprehensive Test
```bash
python3 test_complete_flow.py
```

## 🔍 Expected Timeline

1. **Docker startup**: 1-2 minutes
2. **Services initialization**: 2-3 minutes
3. **Database migrations**: 30 seconds
4. **CDC connector setup**: 1 minute
5. **First test run**: 2-3 minutes

**Total setup time**: ~5-8 minutes

## 🎯 What the Tests Will Do

### Assignment Flow Test:
1. Create a test experiment
2. Generate user assignments
3. Record various events (exposure, conversion, etc.)
4. Verify data in PostgreSQL
5. Check CDC pipeline (Debezium → Kafka)
6. Validate data reaches ClickHouse
7. Generate comprehensive report

### Verification Points:
- ✅ API endpoints working
- ✅ Data persisted in PostgreSQL
- ✅ Outbox events generated for CDC
- ✅ Kafka topics receiving data
- ✅ ClickHouse ingesting analytics data
- ✅ End-to-end data integrity

## 🚨 Troubleshooting

### If services won't start:
```bash
# Clean up and restart
docker compose down
docker compose up -d --force-recreate
```

### If ports are in use:
```bash
# Find what's using the ports
lsof -i :8000  # FastAPI
lsof -i :5432  # PostgreSQL
lsof -i :8080  # Kafka UI
lsof -i :8083  # Debezium
lsof -i :8123  # ClickHouse
```

### Check logs if something fails:
```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs fastapi
docker compose logs postgres
docker compose logs debezium
docker compose logs clickhouse
```

## 🎉 Ready to Test!

Once Docker is running and services are up, you can run any of the test scripts. The `run_complete_flow_test.sh` script is recommended as it does everything automatically including setup verification.

---

**Next Steps:**
1. Start Docker Desktop
2. Run `cd config && docker compose up -d`
3. Wait 3-5 minutes for services to initialize
4. Run `./run_complete_flow_test.sh`
