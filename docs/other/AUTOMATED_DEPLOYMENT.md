# Fully Automated Data Platform Deployment

All data platform deployment steps are now **fully automated and idempotent**. You can deploy and redeploy without manual intervention.

## ✅ Single Command Deployment

```bash
docker compose -f infrastructure/docker/compose.yml \
  --profile core \
  --profile data-platform \
  --profile quality-orchestration \
  --profile bi \
  --profile monitoring \
  up -d
```

That's it! Everything else happens automatically.

## 🔄 What Runs Automatically (Idempotent)

### 1. Bronze Layer Initialization (`bronze-init` service)
- **When**: Runs once after `spark-thrift-server` is healthy
- **What**: Creates `bronze` database and registers all 8 Delta tables in Hive metastore
- **Idempotent**: Uses `CREATE TABLE IF NOT EXISTS` - safe to run multiple times
- **Exit**: Container exits after successful initialization (restart: "no")

**Logs:**
```bash
docker logs rideshare-bronze-init
```

### 2. Airflow DAGs Auto-Start (is_paused_upon_creation)
- **When**: Immediately when Airflow scheduler starts
- **What**: DAGs are created with `is_paused_upon_creation=False`:
  - `dbt_transformation` - Runs DBT Silver/Gold transforms
  - `dlq_monitoring` - Monitors error rates
- **Idempotent**: DAG configuration is declarative
- **Continuous**: DAGs schedule automatically based on their intervals

**Verify DAGs are Active:**
```bash
docker exec rideshare-airflow-scheduler airflow dags list | grep -v "True"
```
Should show unpaused (False) DAGs.

### 3. Streaming Jobs Auto-Start (dedicated services)
- **When**: Immediately with `docker compose up -d`
- **What**: 8 dedicated streaming services start as Docker containers:
  - `spark-streaming-trips`, `spark-streaming-gps-pings`
  - `spark-streaming-driver-status`, `spark-streaming-surge-updates`
  - `spark-streaming-ratings`, `spark-streaming-payments`
  - `spark-streaming-driver-profiles`, `spark-streaming-rider-profiles`
- **Lifecycle**: Docker Compose manages service health and restarts
- **Configuration**: Each service runs spark-submit with job-specific configs

**View Running Services:**
```bash
docker compose -f infrastructure/docker/compose.yml --profile data-platform ps | grep streaming
```

## 📊 Deployment Flow Diagram

```
docker compose up -d
        │
        ├─► Core Services (kafka, redis, osrm, simulation, stream-processor)
        │
        ├─► Data Platform
        │   ├─► minio + minio-init (creates buckets)
        │   ├─► spark-master, spark-worker
        │   ├─► spark-thrift-server
        │   ├─► bronze-init ──► Creates Bronze DB + Tables ✅
        │   └─► 8 streaming services ──► Start immediately ✅
        │           ├─► spark-streaming-trips
        │           ├─► spark-streaming-gps-pings
        │           ├─► spark-streaming-driver-status
        │           ├─► spark-streaming-surge-updates
        │           ├─► spark-streaming-ratings
        │           ├─► spark-streaming-payments
        │           ├─► spark-streaming-driver-profiles
        │           └─► spark-streaming-rider-profiles
        │
        ├─► Quality & Orchestration
        │   ├─► postgres-airflow
        │   ├─► airflow-webserver
        │   └─► airflow-scheduler ──► Runs DAGs (is_paused_upon_creation=False) ✅
        │
        ├─► BI (superset + auto-provisions database connection)
        │
        └─► Monitoring (prometheus, grafana)
```

## 🎯 Zero Manual Steps Required

**Before (Manual Workarounds):**
1. ❌ Trigger Bronze initialization DAG
2. ❌ Manually unpause DAGs
3. ❌ Manually submit streaming jobs with spark-submit
4. ❌ Create local test venv

**After (Fully Automated):**
1. ✅ `bronze-init` service runs automatically
2. ✅ Airflow DAGs unpause via `is_paused_upon_creation=False`
3. ✅ 8 dedicated streaming services start immediately
4. ✅ Test venv automated via `requirements-test.txt`

## 🔍 Verification Commands

### Check Bronze Initialization
```bash
# Verify bronze-init ran successfully
docker logs rideshare-bronze-init | tail -20

# Verify all 8 Bronze tables exist
docker exec rideshare-airflow-webserver python3 -c "
from pyhive import hive
conn = hive.connect(host='spark-thrift-server', port=10000, auth='NOSASL')
cursor = conn.cursor()
cursor.execute('SHOW TABLES IN bronze')
tables = [row[1] for row in cursor.fetchall()]
print(f'Bronze tables ({len(tables)}): {tables}')
conn.close()
"
```

Expected output: 8 tables (bronze_trips, bronze_gps_pings, etc.)

### Check Auto-Unpaused DAGs
```bash
# List all DAGs and their pause status
docker exec rideshare-airflow-scheduler airflow dags list

# Check specific DAG is unpaused
docker exec rideshare-airflow-scheduler airflow dags state dbt_transformation
```

### Check Streaming Services Running
```bash
# Verify all 8 streaming services running
docker compose -f infrastructure/docker/compose.yml --profile data-platform ps | grep streaming

# Check logs for a specific streaming service
docker logs rideshare-spark-streaming-trips

# View Spark Master UI applications
curl -s http://localhost:4040/json/ | python3 -c "
import sys, json
data = json.load(sys.stdin)
apps = data.get('activeapps', [])
print(f'Active Spark applications: {len(apps)}')
for app in apps:
    print(f\"  - {app['name']}\")
"
```

Expected: 8 streaming services and 8 active Spark applications

## 🛠️ Idempotency Guarantees

All automation is idempotent - safe to run multiple times:

| Component | Idempotent Mechanism | Safe to Rerun |
|-----------|---------------------|---------------|
| Bronze init | `CREATE TABLE IF NOT EXISTS` | ✅ Yes |
| DAG creation | Declarative `is_paused_upon_creation=False` | ✅ Yes |
| Streaming services | Docker Compose ensures one per service | ✅ Yes |
| MinIO buckets | minio-init uses `mb --ignore-existing` | ✅ Yes |
| Superset connection | Init script checks for existing | ✅ Yes |

## 🔄 Redeployment

To redeploy (simulates fresh environment):

```bash
# Stop all services
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-platform --profile quality-orchestration \
  down

# Optional: Remove volumes for completely fresh start
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-platform --profile quality-orchestration \
  down -v

# Restart - everything auto-initializes
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-platform --profile quality-orchestration \
  up -d
```

All initialization happens automatically!

## 📝 Implementation Files

### New Automation Scripts
- `infrastructure/scripts/wait-for-thrift-and-init-bronze.sh` - Bronze init with health check
- `infrastructure/scripts/init-bronze-metastore.py` - Creates Bronze DB and tables (idempotent)

### Modified Services
- `infrastructure/docker/compose.yml`:
  - Added `bronze-init` service
  - Added 8 dedicated streaming services:
    - `spark-streaming-trips`
    - `spark-streaming-gps-pings`
    - `spark-streaming-driver-status`
    - `spark-streaming-surge-updates`
    - `spark-streaming-ratings`
    - `spark-streaming-payments`
    - `spark-streaming-driver-profiles`
    - `spark-streaming-rider-profiles`
  - Added init-scripts volume mounts
- `services/airflow/dags/dbt_transformation.py`:
  - Set `is_paused_upon_creation=False`
- `services/airflow/dags/dlq_monitoring.py`:
  - Set `is_paused_upon_creation=False`

### Deprecated Files
- `services/airflow/dags/streaming_jobs_dag.py` - No longer needed (replaced by dedicated services)
- `bronze_initialization` DAG - Legacy, no longer needed (automated by bronze-init service)

## 🚨 Troubleshooting

### "Bronze tables not created"
```bash
# Check bronze-init logs
docker logs rideshare-bronze-init

# Manually trigger if needed
docker exec rideshare-bronze-init bash /opt/init-scripts/wait-for-thrift-and-init-bronze.sh
```

### "Streaming services not starting"
```bash
# Check status of all streaming services
docker compose -f infrastructure/docker/compose.yml --profile data-platform ps | grep streaming

# Check logs for specific service
docker logs rideshare-spark-streaming-trips

# Restart specific service
docker compose -f infrastructure/docker/compose.yml --profile data-platform restart spark-streaming-trips

# Verify Spark Master can accept jobs
curl -s http://localhost:8080/json/ | python3 -m json.tool
```

### "DAGs are paused on first deployment"
```bash
# Check DAG configuration
docker exec rideshare-airflow-webserver airflow dags list

# Verify is_paused_upon_creation setting in DAG files
docker exec rideshare-airflow-webserver cat /opt/airflow/dags/dbt_transformation.py | grep is_paused_upon_creation

# Manually unpause if needed (should not be necessary)
docker exec rideshare-airflow-webserver airflow dags unpause dbt_transformation
docker exec rideshare-airflow-webserver airflow dags unpause dlq_monitoring
```

## 📦 Artifacts Generated

After successful automated deployment:

```
MinIO (s3://):
  rideshare-bronze/
    ├── bronze_trips/_delta_log/
    ├── bronze_gps_pings/_delta_log/
    └── ... (8 tables total)
  rideshare-checkpoints/
    ├── trips/
    ├── gps_pings/
    └── ... (8 checkpoint directories)

Hive Metastore:
  bronze database
    ├── bronze_trips (DELTA table)
    ├── bronze_gps_pings (DELTA table)
    └── ... (8 tables total)

Airflow:
  2 DAGs (auto-unpaused):
    ├── dbt_transformation ✅ UNPAUSED (is_paused_upon_creation=False)
    └── dlq_monitoring ✅ UNPAUSED (is_paused_upon_creation=False)

Docker Compose Services:
  8 streaming services:
    ├── spark-streaming-trips ✅ RUNNING
    ├── spark-streaming-gps-pings ✅ RUNNING
    ├── spark-streaming-driver-status ✅ RUNNING
    ├── spark-streaming-surge-updates ✅ RUNNING
    ├── spark-streaming-ratings ✅ RUNNING
    ├── spark-streaming-payments ✅ RUNNING
    ├── spark-streaming-driver-profiles ✅ RUNNING
    └── spark-streaming-rider-profiles ✅ RUNNING

Spark Cluster:
  8 active applications (from streaming services):
    ├── streaming_trips
    ├── streaming_gps_pings
    └── ... (8 streaming jobs total)
```

## 🎓 Developer Setup (Local Testing)

For developers running tests locally:

```bash
cd services/spark-streaming
python3 -m venv venv
./venv/bin/pip install -r requirements-test.txt
./venv/bin/pytest tests/ -v
```

This is the only manual step remaining - **for local development only**. Deployment is fully automated.

## ✅ Summary

**Deployment Complexity:**
- **Before:** 4 manual steps per deployment
- **After:** 0 manual steps - `docker compose up -d` does everything

**Idempotency:**
- **Before:** Manual steps not idempotent, required careful sequencing
- **After:** All automated steps are idempotent, can rerun safely

**Deployment Time:**
- **Automated initialization:** ~2-3 minutes (bronze-init, streaming services start)
- **Streaming services ready:** Immediately (Docker Compose starts services in parallel)
- **Total:** ~3-4 minutes to fully operational data platform

**Human Interaction Required:** ✅ **ZERO** (except initial `docker compose up -d`)
