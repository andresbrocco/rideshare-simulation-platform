# Data Migration Guide

> Migrate simulation data from local Docker (MinIO) to AWS S3 for cloud deployment

## Overview

The platform supports a **local-first workflow**: run the simulation locally using Docker Compose (free, using MinIO as S3-compatible storage), accumulate data over days or weeks, then sync everything to AWS S3 for cloud deployment. Both Delta Lake files and simulation checkpoints are byte-for-byte portable between MinIO and AWS S3.

### What Gets Migrated

| Bucket | Contents | Purpose |
|--------|----------|---------|
| `rideshare-bronze` | Raw Kafka events as Delta tables | Bronze layer (immutable event log) |
| `rideshare-silver` | Cleaned, validated, deduplicated data | Silver layer (DBT staging models) |
| `rideshare-gold` | Star schema with SCD Type 2 | Gold layer (DBT mart models) |
| `rideshare-checkpoints` | Gzip-compressed simulation state | Resume simulation from exact point |

### What Doesn't Need Migration

- **Kafka topics**: Cloud deployment creates fresh topics; Bronze layer has the complete event history
- **Redis state**: Ephemeral real-time state, rebuilt when simulation starts
- **Prometheus/Loki/Tempo**: Monitoring data stays local; cloud has its own observability stack
- **SQLite checkpoint**: Replaced by S3 checkpoint in Docker (no migration needed)

## Prerequisites

1. **Docker profiles running** with data accumulated:
   ```bash
   docker compose -f infrastructure/docker/compose.yml \
     --profile core --profile data-pipeline --profile monitoring up -d
   ```

2. **AWS CLI configured** with the `rideshare` profile:
   ```bash
   aws configure --profile rideshare
   # Set: AWS Access Key ID, Secret Access Key, Region (us-east-1)
   ```

3. **AWS account ID** (used for bucket naming):
   ```bash
   aws sts get-caller-identity --profile rideshare --query Account --output text
   ```

4. **Python dependencies** available:
   ```bash
   ./venv/bin/pip install boto3
   ```

## Step-by-Step Migration

### 1. Run Simulation Locally

```bash
# Start all services
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-pipeline --profile monitoring up -d

# Start simulation and spawn agents
curl -X POST -H "X-API-Key: admin" http://localhost:8000/simulation/start
curl -X POST -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"count": 50}' http://localhost:8000/agents/drivers
curl -X POST -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"count": 100}' http://localhost:8000/agents/riders

# Let it run... checkpoints save every 300 simulated seconds
# Speed up if desired:
curl -X PUT -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"speed_multiplier": 10}' http://localhost:8000/simulation/speed
```

### 2. Trigger Data Pipeline

Ensure Bronze → Silver → Gold transformations have run:

```bash
# Check Airflow DAGs are running
open http://localhost:8081  # admin/admin

# Or manually trigger DBT
docker compose -f infrastructure/docker/compose.yml exec airflow-webserver \
  airflow dags trigger dbt_silver_transformation
docker compose -f infrastructure/docker/compose.yml exec airflow-webserver \
  airflow dags trigger dbt_gold_transformation
```

### 3. Pause Simulation (Optional)

For a clean checkpoint with no in-flight trips:

```bash
curl -X POST -H "X-API-Key: admin" http://localhost:8000/simulation/pause

# Wait for PAUSED state
watch -n 1 'curl -s -H "X-API-Key: admin" http://localhost:8000/simulation/status | python3 -m json.tool'
```

### 4. Dry-Run Migration

```bash
./venv/bin/python3 scripts/sync-to-cloud.py \
  --account-id <YOUR_ACCOUNT_ID> \
  --dry-run
```

This lists all objects per bucket with sizes without transferring anything.

### 5. Sync to Cloud

```bash
./venv/bin/python3 scripts/sync-to-cloud.py \
  --account-id <YOUR_ACCOUNT_ID>
```

Syncs all 4 buckets. You can also sync specific buckets:

```bash
# Sync only the lakehouse data (skip checkpoints)
./venv/bin/python3 scripts/sync-to-cloud.py \
  --account-id <YOUR_ACCOUNT_ID> \
  --buckets bronze silver gold

# Sync only checkpoints
./venv/bin/python3 scripts/sync-to-cloud.py \
  --account-id <YOUR_ACCOUNT_ID> \
  --buckets checkpoints
```

### 6. Deploy to Cloud

Follow the [Cloud Deployment Guide](CLOUD-DEPLOYMENT.md) to create the EKS platform. The simulation will automatically restore from the S3 checkpoint on startup (RESUME_FROM_CHECKPOINT=true in production).

### 7. Register Tables in Cloud Trino

After deployment, register the migrated Delta tables in the cloud Trino catalog:

```bash
kubectl exec -it deployment/trino -- /bin/bash /opt/init-scripts/register-delta-tables.sh
```

## Checkpoint Resume Behavior

When the simulation container starts with `SIM_RESUME_FROM_CHECKPOINT=true` and `SIM_CHECKPOINT_STORAGE_TYPE=s3`:

1. Checks S3 for existing checkpoint (`<bucket>/<prefix>/latest.json.gz`)
2. If found, restores: SimPy environment time, all driver/rider agents with DNA and runtime state, surge multipliers, reserved drivers
3. If checkpoint type is "crash" (had in-flight trips), cancels those trips to ensure clean state
4. Starts simulation from the restored time point

This works identically whether the checkpoint came from local MinIO or was synced to AWS S3.

## Reverse Sync (Cloud to Local)

To bring cloud data back to local development:

```bash
# Use AWS CLI directly (reverse direction)
for suffix in bronze silver gold checkpoints; do
  aws s3 sync \
    s3://rideshare-<account-id>-$suffix \
    s3://rideshare-$suffix \
    --profile rideshare \
    --endpoint-url http://localhost:9000
done
```

Note: This requires MinIO to be running locally and AWS credentials configured.

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `Cannot connect to MinIO` | MinIO not running | Start data-pipeline profile: `docker compose --profile data-pipeline up -d` |
| `AWS credentials not found` | Missing rideshare profile | Run `aws configure --profile rideshare` |
| `NoSuchBucket` on source | Simulation hasn't created bucket | Start simulation and let checkpoint save at least once |
| `NoSuchBucket` on destination | First sync to this account | Script creates destination buckets automatically |
| Checkpoint restore fails | Version mismatch | Check simulation logs; checkpoint version is logged on mismatch |
| Empty Bronze/Silver/Gold | Pipeline hasn't run | Trigger Airflow DAGs or wait for scheduled runs |

## Related

- [CLOUD-DEPLOYMENT.md](CLOUD-DEPLOYMENT.md) - Full cloud deployment guide
- [../infrastructure/scripts/README.md](../infrastructure/scripts/README.md) - Script reference
- [../services/simulation/CONTEXT.md](../services/simulation/CONTEXT.md) - Simulation architecture
- [../services/simulation/src/db/CONTEXT.md](../services/simulation/src/db/CONTEXT.md) - Checkpoint backends
