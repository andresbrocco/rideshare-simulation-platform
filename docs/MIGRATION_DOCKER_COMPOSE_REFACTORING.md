# Migration Guide: Docker Compose Refactoring (2026-01-18)

## Overview

This guide covers the migration from Docker Compose workarounds to production-ready best practices implemented on 2026-01-18.

**What Changed:**
1. Airflow DAGs now use `is_paused_upon_creation=False` (no entrypoint wrapper)
2. Streaming jobs are dedicated docker-compose services (no DAG-based submission)
3. Bronze init has retry logic and faster startup

**Impact:**
- Faster startup: ~3-4 minutes (down from ~8 minutes)
- Simpler architecture: No custom entrypoints or docker-exec
- Standard patterns: All production best practices

## What Changed in Detail

### 1. Airflow DAG Auto-Unpause

**Before:**
- Custom entrypoint wrapper (`airflow-entrypoint-wrapper.sh`)
- Wrapper polled API and called `airflow dags unpause`
- Non-standard entrypoint override in compose.yml

**After:**
- DAGs use `is_paused_upon_creation=False` parameter
- Standard Airflow pattern, no custom scripts
- Default entrypoint, cleaner compose.yml

**Files Changed:**
- `services/airflow/dags/streaming_jobs_dag.py` - Added parameter, deprecated DAG
- `services/airflow/dags/dbt_transformation_dag.py` - Added parameter to 2 DAGs
- `services/airflow/dags/dlq_monitoring_dag.py` - Added parameter
- `infrastructure/docker/compose.yml` - Removed entrypoint override
- `infrastructure/scripts/airflow-entrypoint-wrapper.sh` - DELETED

### 2. Streaming Jobs Lifecycle

**Before:**
- `streaming_jobs_dag.py` ran every 5 minutes
- Used docker-exec to submit jobs to Spark
- Custom idempotency checks

**After:**
- 8 dedicated docker-compose services
- Each service runs continuously with `restart: unless-stopped`
- Docker Compose ensures single instance per service

**Services Added:**
- spark-streaming-trips
- spark-streaming-gps-pings
- spark-streaming-driver-status
- spark-streaming-surge-updates
- spark-streaming-ratings
- spark-streaming-payments
- spark-streaming-driver-profiles
- spark-streaming-rider-profiles

**Files Changed:**
- `infrastructure/docker/compose.yml` - Added 8 services
- `services/airflow/dags/streaming_jobs_dag.py` - Deprecated (schedule=None)

### 3. Bronze Init Improvements

**Before:**
- 10-second hardcoded sleep
- No retry logic for transient errors

**After:**
- 5-second sleep (faster startup)
- 3-attempt retry with 5-second backoff

**Files Changed:**
- `infrastructure/scripts/init-bronze-metastore.py` - Added retry logic
- `infrastructure/scripts/wait-for-thrift-and-init-bronze.sh` - Reduced sleep

## Migration Steps

### For Fresh Deployments (Recommended)

If you haven't deployed before, simply use the latest code:

```bash
# Clone/pull latest code
git pull origin main

# Start all services
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-platform \
  up -d

# Wait for initialization (~4 minutes)
sleep 240

# Verify streaming services
docker compose -f infrastructure/docker/compose.yml --profile data-platform ps | grep streaming
# Expected: 8 services "Up"

# Verify DAGs unpaused
docker exec rideshare-airflow-scheduler airflow dags list
# Expected: All DAGs show "False" in is_paused column
```

### For Existing Deployments

If you already have services running:

**Step 1: Stop all services**
```bash
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-platform \
  down
```

**Step 2: Pull latest code**
```bash
git pull origin main
```

**Step 3: Clean up old volumes (optional but recommended)**
```bash
# This removes all data - only do this if you want a fresh start
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-platform \
  down -v
```

**Step 4: Start with new configuration**
```bash
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-platform \
  up -d
```

**Step 5: Verify migration**
```bash
# Check streaming services
docker compose -f infrastructure/docker/compose.yml --profile data-platform ps | grep streaming
# Expected: 8 services "Up"

# Check deprecated DAG
docker exec rideshare-airflow-scheduler airflow dags list | grep streaming_jobs_lifecycle
# Expected: schedule_interval=None, is_paused=True

# Check active DAGs are unpaused
docker exec rideshare-airflow-scheduler airflow dags list | grep -E "(dbt_transformation|dlq_monitoring)"
# Expected: is_paused=False
```

## Verification Commands

### Verify Streaming Services

```bash
# All 8 services should be running
docker compose -f infrastructure/docker/compose.yml --profile data-platform ps | grep streaming

# Check logs for one service
docker logs rideshare-spark-streaming-trips --tail 50

# Verify with Spark Master
curl -s http://localhost:4040/json/ | python3 -c "
import sys, json
data = json.load(sys.stdin)
apps = data.get('activeapps', [])
print(f'Active apps: {len(apps)}')
for app in apps:
    print(f\"  - {app['name']}\")
"
# Expected: 8 applications
```

### Verify DAGs

```bash
# List all DAGs
docker exec rideshare-airflow-scheduler airflow dags list

# Check specific DAG status
docker exec rideshare-airflow-scheduler airflow dags state streaming_jobs_lifecycle
```

### Verify Bronze Data

```bash
# Wait for data to flow
sleep 60

# Check Bronze tables
docker exec rideshare-airflow-webserver python3 -c "
from pyhive import hive
conn = hive.connect(host='spark-thrift-server', port=10000, auth='NOSASL')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM bronze.bronze_trips')
count = cursor.fetchone()[0]
print(f'Bronze trips: {count}')
conn.close()
"
```

### Test Automatic Restart

```bash
# Stop one streaming service
docker stop rideshare-spark-streaming-trips

# Wait 15 seconds
sleep 15

# Check if restarted
docker ps | grep spark-streaming-trips
# Expected: Container is running again
```

## Rollback Procedure

If you need to rollback to the previous version:

**Step 1: Stop current services**
```bash
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-platform \
  down
```

**Step 2: Checkout previous commit**
```bash
# Find the commit before the refactoring
git log --oneline | head -10

# Checkout (replace COMMIT_HASH with actual hash)
git checkout <COMMIT_HASH>
```

**Step 3: Restart services**
```bash
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-platform \
  up -d
```

**Note:** The previous version used:
- `airflow-entrypoint-wrapper.sh` for DAG unpausing
- `streaming_jobs_dag.py` (active, every 5 minutes) for job submission
- Manual spark-submit commands

## Troubleshooting

### Streaming Services Not Starting

**Symptom:** `docker ps` doesn't show 8 streaming services

**Check:**
```bash
# Verify profile is specified
docker compose -f infrastructure/docker/compose.yml --profile data-platform ps

# Check service logs
docker logs rideshare-spark-streaming-trips
```

**Common causes:**
- Forgot `--profile data-platform` flag
- Spark Master not healthy yet
- MinIO or Kafka not ready

**Solution:**
```bash
# Start dependencies first
docker compose -f infrastructure/docker/compose.yml --profile data-platform up -d spark-master minio kafka

# Wait for health checks
sleep 60

# Start streaming services
docker compose -f infrastructure/docker/compose.yml --profile data-platform up -d
```

### DAGs Are Paused on First Deployment

**Symptom:** DAGs show `is_paused=True` even with `is_paused_upon_creation=False`

**Cause:** This only affects **existing** Airflow metadata databases. The `is_paused_upon_creation` parameter only applies when a DAG is **first** added to the database.

**Solution 1 - Fresh start (recommended for dev):**
```bash
# Remove volumes to reset Airflow metadata
docker compose -f infrastructure/docker/compose.yml --profile data-platform down -v
docker compose -f infrastructure/docker/compose.yml --profile data-platform up -d
```

**Solution 2 - Manual unpause (for existing deployments):**
```bash
docker exec rideshare-airflow-scheduler airflow dags unpause dbt_transformation
docker exec rideshare-airflow-scheduler airflow dags unpause dbt_gold_transformation
docker exec rideshare-airflow-scheduler airflow dags unpause dlq_monitoring
```

### Streaming Service Exits Immediately

**Symptom:** Service starts but exits after a few seconds

**Check logs:**
```bash
docker logs rideshare-spark-streaming-trips
```

**Common causes:**
1. **Checkpoint path issues** - MinIO bucket doesn't exist
2. **Kafka connectivity** - Kafka not ready
3. **Spark Master not available** - Wrong spark:// URL

**Solutions:**
```bash
# Verify MinIO buckets exist
docker exec rideshare-minio mc ls myminio/

# Verify Kafka topics exist
docker exec rideshare-kafka kafka-topics --bootstrap-server localhost:9092 --list

# Verify Spark Master is reachable
docker exec rideshare-spark-streaming-trips curl -s spark-master:8080
```

### Bronze Init Fails After 3 Retries

**Symptom:** `docker logs rideshare-bronze-init` shows "All 3 attempts failed"

**Cause:** Thrift Server not ready or network issues

**Check:**
```bash
# Verify Thrift Server is running
docker ps | grep thrift

# Check Thrift Server logs
docker logs rideshare-spark-thrift-server

# Try manual connection
docker exec rideshare-bronze-init python3 -c "
from pyhive import hive
conn = hive.connect(host='spark-thrift-server', port=10000, auth='NOSASL')
print('Connected successfully')
conn.close()
"
```

**Solution:**
```bash
# Restart bronze-init service
docker compose -f infrastructure/docker/compose.yml --profile data-platform restart bronze-init
```

### Deprecated DAG Still Running

**Symptom:** `streaming_jobs_lifecycle` DAG is executing despite being deprecated

**Check:**
```bash
docker exec rideshare-airflow-scheduler airflow dags list | grep streaming_jobs
```

**Solution:**
```bash
# Pause the deprecated DAG manually
docker exec rideshare-airflow-scheduler airflow dags pause streaming_jobs_lifecycle
```

## FAQ

**Q: Will this break my existing deployment?**
A: No, if you follow the migration steps. The changes are backwards-compatible. Just restart services with the new configuration.

**Q: Do I need to delete volumes?**
A: Not required, but recommended for a clean slate. If you keep volumes:
- Airflow DAGs may still be paused (unpause manually)
- Streaming job checkpoints persist (safe to keep)

**Q: Can I run both old and new patterns?**
A: Not recommended. The deprecated `streaming_jobs_lifecycle` DAG will conflict with dedicated services. Pause the DAG if both are present.

**Q: How do I verify everything is working?**
A: Run the verification commands in the "Verification Commands" section above. All should pass.

**Q: What if I need to rollback?**
A: Follow the "Rollback Procedure" section. The old code is preserved in git history.

**Q: How does this affect Kubernetes migration (Phase 06)?**
A: It doesn't conflict. These are Docker Compose best practices. K8s will use Deployments, which is the proper K8s pattern.

## References

- Refactoring Plan: `.workflow/specs/2026-01-18-docker-compose-refactoring.md`
- Automated Deployment Docs: `docs/AUTOMATED_DEPLOYMENT.md`
- Integration Test Plan: `.workflow/integration-tests/2026-01-12T00-31-40-data-platform-phases-01-to-05/plan.md`
- Docker Compose File: `infrastructure/docker/compose.yml`

## Summary

This refactoring eliminates workarounds and adopts production-ready patterns:
- ✅ No custom entrypoint wrappers
- ✅ No docker-exec anti-patterns
- ✅ Standard Airflow DAG configuration
- ✅ Dedicated services for long-running jobs
- ✅ Faster startup (~4 minutes vs ~8 minutes)
- ✅ Better reliability with retry logic
- ✅ Simpler architecture, easier to maintain

For questions or issues, refer to the troubleshooting section or file an issue on GitHub.
