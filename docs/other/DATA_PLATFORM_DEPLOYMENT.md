# Data Platform Deployment Guide

This guide explains how to deploy the data platform services (Bronze layer, DBT, Airflow, Superset, monitoring) and what is automated vs. manual.

## Quick Start

### 1. Start All Services

```bash
docker compose -f infrastructure/docker/compose.yml \
  --profile core \
  --profile data-pipeline \
   \
  --profile bi \
  --profile monitoring \
  up -d
```

### 2. Initialize Bronze Metastore (One-Time)

After first deployment, trigger the Bronze initialization DAG in Airflow:

1. Open Airflow UI: http://localhost:8082 (admin/admin)
2. Unpause the `bronze_initialization` DAG
3. Trigger it manually (run once)
4. Verify all Bronze tables are created

### 3. (Optional) Start Streaming Jobs via Airflow

To have Airflow manage streaming jobs:

1. Unpause the `streaming_jobs_lifecycle` DAG
2. It will submit all 8 streaming jobs to Spark and monitor their health
3. Runs every 5 minutes to check job health

**Note:** SparkSubmitOperator limitations mean this might not work perfectly in Docker. Alternative: use the manual spark-submit command (see Troubleshooting).

## What's Automated ✅

These persist across deployments automatically:

### Infrastructure Configuration
- ✅ Spark Master volume mount (`/opt/spark_streaming`) - **compose.yml**
- ✅ Spark Master PYTHONPATH (`/opt`) - **compose.yml**
- ✅ Airflow init scripts mount (`/opt/init-scripts`) - **compose.yml**
- ✅ MinIO bucket creation (minio-init container)
- ✅ Superset database connection auto-provisioning

### Code Fixes
- ✅ Kafka port corrected in all 8 streaming jobs (`kafka:29092`)
- ✅ S3A credentials in Airflow DAG `streaming_jobs_dag.py`
- ✅ DBT profiles configured for Spark Thrift Server

### DAGs and Scripts
- ✅ `bronze_initialization` DAG for one-time metastore setup
- ✅ `streaming_jobs_lifecycle` DAG for job management
- ✅ `dbt_transformation` DAG for Silver/Gold transforms
- ✅ `dlq_monitoring` DAG for error tracking

## What Needs Manual Steps ⚠️

### One-Time Setup (After First Deployment)

1. **Trigger Bronze initialization DAG** (explained above)
   - Creates `bronze` database in Hive metastore
   - Registers all 8 Delta tables
   - Only needed once per fresh environment

2. **Unpause DAGs** if you want them to run automatically
   - Airflow creates all DAGs in paused state by default
   - Go to Airflow UI → DAGs → Toggle each DAG to active

3. **Create Spark Streaming venv** (for running unit tests locally)
   ```bash
   cd services/spark-streaming
   python3 -m venv venv
   ./venv/bin/pip install -r requirements-test.txt
   ```

### Optional Manual Streaming Job Submission

If the `streaming_jobs_lifecycle` DAG doesn't work (SparkSubmitOperator issues), use this manual approach:

```bash
# Submit a streaming job to Spark cluster
docker exec -d rideshare-spark-master bash -c 'nohup /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode client \
  --conf spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension \
  --conf spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog \
  --conf spark.hadoop.fs.s3a.endpoint=http://minio:9000 \
  --conf spark.hadoop.fs.s3a.access.key=minioadmin \
  --conf spark.hadoop.fs.s3a.secret.key=minioadmin \
  --conf spark.hadoop.fs.s3a.path.style.access=true \
  /opt/spark_streaming/jobs/trips_streaming_job.py > /tmp/trips_job.log 2>&1 &'
```

Repeat for all 8 jobs:
- trips_streaming_job.py
- gps_pings_streaming_job.py
- driver_status_streaming_job.py
- surge_updates_streaming_job.py
- ratings_streaming_job.py
- payments_streaming_job.py
- driver_profiles_streaming_job.py
- rider_profiles_streaming_job.py

## Verification Checklist

After deployment, verify:

### Services Running
```bash
docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline  ps
```

All containers should be "Up" and healthy.

### Bronze Tables Exist
```python
docker exec rideshare-airflow-webserver python3 -c "
from pyhive import hive
conn = hive.connect(host='spark-thrift-server', port=10000, auth='NOSASL')
cursor = conn.cursor()
cursor.execute('SHOW TABLES IN bronze')
tables = [row[1] for row in cursor.fetchall()]
print(f'Bronze tables: {tables}')
assert len(tables) == 8, f'Expected 8 tables, found {len(tables)}'
conn.close()
"
```

### Streaming Jobs Running
```bash
# Check Spark Master UI for running applications
curl -s http://localhost:4040/api/v1/applications | python3 -m json.tool
```

Should show 8 running applications (one per topic).

### Airflow DAGs Loaded
```bash
docker exec rideshare-airflow-scheduler airflow dags list | grep -E "(bronze_initialization|streaming_jobs_lifecycle|dbt_transformation)"
```

Should show all DAGs.

## Troubleshooting

### "DAGs not showing in Airflow"
```bash
# Force reserialize DAGs
docker exec rideshare-airflow-scheduler airflow dags reserialize
```

### "Bronze tables not found"
Run the `bronze_initialization` DAG or manually execute:
```bash
docker exec rideshare-airflow-webserver python3 /opt/init-scripts/init-bronze-metastore.py
```

### "Streaming jobs not running"
Check Spark Master logs:
```bash
docker logs rideshare-spark-master --tail 50
```

Look for application registration. If jobs aren't persisting, use the manual spark-submit approach above.

### "Cannot connect to Spark from Airflow"
Verify Spark connection:
```bash
docker exec rideshare-airflow-webserver python3 -c "
from airflow.providers.apache.spark.hooks.spark_submit import SparkSubmitHook
hook = SparkSubmitHook(conn_id='spark_default')
print(f'Spark connection: {hook._resolve_connection()}')
"
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose Services                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Core (--profile core)                                       │
│  ├─ kafka, schema-registry, redis, osrm                     │
│  ├─ simulation, stream-processor, frontend                  │
│                                                              │
│  Data Pipeline (--profile data-pipeline)                     │
│  ├─ minio (+ minio-init)                                    │
│  ├─ spark-thrift-server                                     │
│  ├─ spark-streaming-* (8 streaming jobs)                    │
│  ├─ localstack                                              │
│  ├─ postgres-airflow                                        │
│  ├─ airflow-webserver, airflow-scheduler                   │
│  │                                                           │
│  │  Streaming Jobs (as dedicated containers)                │
│  │  ├─ Read from: kafka:29092                              │
│  │  ├─ Write to: s3a://rideshare-bronze/*                  │
│  │  └─ Checkpoints: s3a://rideshare-checkpoints/*          │
│  │                                                           │
│  │  DAGs:                                                    │
│  │  ├─ bronze_initialization (manual trigger, once)         │
│  │  ├─ streaming_jobs_lifecycle (optional, every 5min)     │
│  │  ├─ dbt_transformation (runs DBT models)                │
│  │  └─ dlq_monitoring (checks error rates)                 │
│                                                              │
│  BI (--profile bi)                                          │
│  ├─ postgres-superset, redis-superset                      │
│  ├─ superset (+ superset-init)                             │
│                                                              │
│  Monitoring (--profile monitoring)                           │
│  ├─ prometheus, cadvisor, grafana                          │
└─────────────────────────────────────────────────────────────┘
```

## Files Reference

### Modified for Automation
- `infrastructure/docker/compose.yml` - Added volumes and environment variables
- `services/spark-streaming/jobs/*.py` - Fixed Kafka port
- `services/airflow/dags/streaming_jobs_dag.py` - Fixed paths and added S3A config

### Created for Automation
- `infrastructure/scripts/init-bronze-metastore.py` - Bronze initialization script
- `services/airflow/dags/bronze_init_dag.py` - Airflow DAG for initialization
- `services/spark-streaming/requirements-test.txt` - Test dependencies
- `docs/DATA_PLATFORM_DEPLOYMENT.md` - This file

## Migration from Manual to Automated

If you previously deployed manually, here's how to migrate:

1. **Stop all containers**
   ```bash
   docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline  down
   ```

2. **Pull latest code changes** (with automation fixes)

3. **Restart with new configuration**
   ```bash
   docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline  up -d
   ```

4. **Bronze tables already exist?** Skip the initialization DAG

5. **Streaming jobs already running?** They'll continue, or restart via Airflow DAG

## Next Steps

After successful deployment:

1. **Run DBT transformations** - Trigger `dbt_transformation` DAG
2. **Validate with Great Expectations** - Automatically runs after DBT
3. **View dashboards** - Open Superset at http://localhost:8088
4. **Monitor metrics** - Open Grafana at http://localhost:3001
