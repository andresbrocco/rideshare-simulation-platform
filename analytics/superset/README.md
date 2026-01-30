# Apache Superset

> Apache Superset BI stack for medallion lakehouse dashboards and SQL exploration

## Quick Reference

### Dashboards Overview

| Dashboard | Slug | Charts | Layer | Purpose |
|-----------|------|--------|-------|---------|
| Operations Dashboard | `operations` | 9 | Gold | Real-time platform monitoring |
| Driver Performance Dashboard | `driver-performance` | 6 | Gold | Driver metrics and analytics |
| Demand Analysis Dashboard | `demand-analysis` | 6 | Gold | Zone demand and surge patterns |
| Revenue Analytics Dashboard | `revenue-analytics` | 9 | Gold | Revenue metrics and KPIs |
| Bronze Pipeline Dashboard | `bronze-pipeline` | 8 | Bronze | Ingestion metrics and DLQ monitoring |
| Silver Quality Dashboard | `silver-quality` | 8 | Silver | Anomaly detection and data freshness |

**Total: 6 dashboards, 46 charts**

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SUPERSET_SECRET_KEY` | Secret key for session encryption | `dev-secret-key-change-in-production` | Yes |
| `SUPERSET_ADMIN_USERNAME` | Admin user username | `admin` | No |
| `SUPERSET_ADMIN_PASSWORD` | Admin user password | `admin` | No |
| `SQLALCHEMY_DATABASE_URI` | PostgreSQL metadata database URI | `postgresql://superset:superset@postgres-superset:5432/superset` | Yes |
| `REDIS_URL` | Redis cache/broker base URL | `redis://redis-superset:6379` | Yes |

### Service Endpoints

| Service | URL | Description |
|---------|-----|-------------|
| Superset UI | http://localhost:8088 | Main dashboard interface |
| Health Check | http://localhost:8088/health | Service health endpoint |
| PostgreSQL | localhost:5433 | Metadata database (internal) |
| Redis | localhost:6380 | Cache layer (internal) |

**Default Credentials:**
- Username: `admin`
- Password: `admin`

### Commands

```bash
# Start Superset stack (analytics profile)
docker compose -f infrastructure/docker/compose.yml --profile analytics up -d

# Check service health
docker compose -f infrastructure/docker/compose.yml ps | grep superset

# View logs
docker compose -f infrastructure/docker/compose.yml logs -f superset

# Stop services
docker compose -f infrastructure/docker/compose.yml --profile analytics down

# Rebuild and restart (after config changes)
docker compose -f infrastructure/docker/compose.yml --profile analytics up -d --build superset
```

### Configuration Files

| File | Purpose |
|------|---------|
| `superset_config.py` | Main Superset configuration (database, Redis, caching, security) |
| `docker-entrypoint.sh` | Container startup script with auto-provisioning and dashboard import |
| `dashboards/bronze_queries.py` | Bronze layer SQL queries |
| `dashboards/silver_queries.py` | Silver layer SQL queries |
| `dashboards/gold_queries.py` | Gold layer SQL queries |
| `dashboards/import_dashboards.py` | Automated dashboard import script |

### Docker Services

| Service | Image | Memory | Ports | Purpose |
|---------|-------|--------|-------|---------|
| `superset` | apache/superset:6.0.0 | 768MB | 8088 | Main BI application |
| `postgres-superset` | postgres:16 | 256MB | 5433 | Metadata storage |
| `redis-superset` | redis:8.0-alpine | 128MB | 6380 | Multi-layer cache |

**Total Stack Memory:** 1152MB

### Prerequisites

- Docker Compose with `analytics` profile
- Spark Thrift Server running on port 10000 (for data access)
- Lakehouse tables created by DBT transformations
- Network: `rideshare-network`

## Common Tasks

### Access the UI

```bash
# Start Superset stack
docker compose -f infrastructure/docker/compose.yml --profile analytics up -d

# Wait for initialization (60-90 seconds)
docker compose -f infrastructure/docker/compose.yml logs -f superset

# Open browser
open http://localhost:8088

# Login with admin/admin
```

### Connect to Rideshare Data

The Spark Thrift Server connection is **auto-provisioned** on startup. To verify:

1. Log in to Superset at http://localhost:8088
2. Navigate to **Data > Databases**
3. Confirm "Rideshare Lakehouse" exists

**Connection Details:**
- **Database Name**: Rideshare Lakehouse
- **SQLAlchemy URI**: `hive://spark-thrift-server:10000/default?auth=NOSASL`
- **Exposed in SQL Lab**: Yes
- **Async Execution**: Enabled

### Test the Connection

```sql
-- In SQL Lab (SQL > SQL Editor):
-- Select "Rideshare Lakehouse" database

-- Bronze layer queries
SELECT COUNT(*) FROM bronze.bronze_trips;
SELECT COUNT(*) FROM bronze.bronze_gps_pings;

-- Silver layer queries
SELECT COUNT(*) FROM silver.stg_trips;
SELECT COUNT(*) FROM silver.anomalies_all;

-- Gold layer queries
SELECT COUNT(*) FROM gold.fact_trips;
SELECT COUNT(*) FROM gold.dim_drivers;
SELECT COUNT(*) FROM gold.dim_riders;
SELECT COUNT(*) FROM gold.dim_zones;
```

### Create a Dataset

To build dashboards, register lakehouse tables:

1. Navigate to **Data > Datasets**
2. Click **+ Dataset**
3. Configure:
   - **Database**: Rideshare Lakehouse
   - **Schema**: gold (or bronze/silver)
   - **Table**: fact_trips (or other table)
4. Click **Add**

### View Logs

```bash
# Superset application logs
docker compose -f infrastructure/docker/compose.yml logs -f superset

# PostgreSQL metadata database logs
docker compose -f infrastructure/docker/compose.yml logs -f postgres-superset

# Redis cache logs
docker compose -f infrastructure/docker/compose.yml logs -f redis-superset

# Initialization logs (one-time setup)
docker compose -f infrastructure/docker/compose.yml logs superset-init
```

### Reset Metadata Database

```bash
# WARNING: This deletes all dashboards, charts, and datasets

# Stop services
docker compose -f infrastructure/docker/compose.yml --profile analytics down

# Remove metadata volume
docker volume rm rideshare-simulation-platform_postgres-superset-data

# Restart (will reinitialize)
docker compose -f infrastructure/docker/compose.yml --profile analytics up -d
```

## Architecture

### Multi-Service Stack

```
┌─────────────────────────────────────────────────────┐
│ Superset (apache/superset:6.0.0)                    │
│ - FastAPI web server on port 8088                   │
│ - Celery workers for async queries                  │
│ - Auto-provisions Spark connection on startup       │
│ - Auto-imports dashboards from ZIP exports          │
└─────────────────┬───────────────────────────────────┘
                  │
       ┌──────────┴──────────┐
       │                     │
       ▼                     ▼
┌─────────────────┐   ┌─────────────────┐
│ PostgreSQL      │   │ Redis           │
│ (metadata)      │   │ (cache/broker)  │
│                 │   │                 │
│ - User accounts │   │ DB 0: Celery    │
│ - Dashboards    │   │ DB 1: Results   │
│ - Datasets      │   │ DB 2: Cache     │
│ - Permissions   │   │ DB 3: Data      │
│                 │   │ DB 4: Filters   │
│                 │   │ DB 5: Explore   │
└─────────────────┘   └─────────────────┘
```

### Query Library Architecture

```
dashboards/
├── bronze_queries.py    # Bronze layer SQL (8 queries)
│   ├── TOTAL_EVENTS_24H
│   ├── EVENTS_BY_TOPIC
│   ├── INGESTION_RATE_HOURLY
│   ├── DLQ_ERROR_COUNT
│   ├── DLQ_ERRORS_BY_TYPE
│   ├── PARTITION_DISTRIBUTION
│   ├── LATEST_INGESTION
│   └── INGESTION_LAG
│
├── silver_queries.py    # Silver layer SQL (8 queries)
│   ├── TOTAL_ANOMALIES
│   ├── ANOMALIES_BY_TYPE
│   ├── ANOMALIES_OVER_TIME
│   ├── GPS_OUTLIERS_COUNT
│   ├── IMPOSSIBLE_SPEEDS_COUNT
│   ├── ZOMBIE_DRIVERS_LIST
│   ├── STAGING_ROW_COUNTS
│   └── STAGING_FRESHNESS
│
└── gold_queries.py      # Gold layer SQL (30 queries)
    ├── OPERATIONS_QUERIES (9)
    ├── DRIVER_PERFORMANCE_QUERIES (6)
    ├── DEMAND_ANALYSIS_QUERIES (6)
    └── REVENUE_ANALYTICS_QUERIES (9)
```

### Configuration Layers

**superset_config.py:**
- Database URI (PostgreSQL metadata)
- Redis cache configuration (6 separate databases)
- Celery broker/result backend
- Security settings (CSRF, secret key)
- Feature flags (template processing)
- Row limits (default 5000)

**docker-entrypoint.sh:**
- Installs PyHive, Thrift, psycopg2-binary dependencies
- Waits for PostgreSQL metadata database readiness
- Auto-provisions "Rideshare Lakehouse" database connection
- Starts Superset web server in background
- Imports dashboards via import_dashboards.py (non-blocking)

**superset-init (one-time):**
- Runs database migrations (`superset db upgrade`)
- Creates admin user (`superset fab create-admin`)
- Initializes roles and permissions (`superset init`)

### Redis Database Allocation

| Database | Purpose | Timeout | Key Prefix |
|----------|---------|---------|------------|
| DB 0 | Celery broker/results | - | - |
| DB 1 | Query results backend | - | - |
| DB 2 | General cache | 300s | `superset_` |
| DB 3 | Data cache | 86400s | `superset_data_` |
| DB 4 | Filter state cache | 86400s | `superset_filter_` |
| DB 5 | Explore form cache | 86400s | `superset_explore_` |

## Dashboard Details

### Bronze Pipeline Dashboard

**URL**: http://localhost:8088/superset/dashboard/bronze-pipeline/

Monitors the Bronze (raw ingestion) layer of the medallion lakehouse.

| Chart | Type | Description |
|-------|------|-------------|
| Total Events (24h) | Big Number | Total events ingested across all Kafka topics |
| DLQ Errors | Big Number | Dead letter queue error count |
| Max Ingestion Lag | Big Number | Maximum lag between event and ingestion time |
| Events by Topic | Bar Chart | Distribution of events across Kafka topics |
| Partition Distribution | Bar Chart | Event distribution across Kafka partitions |
| Ingestion Rate | Time Series | Hourly ingestion rate trend |
| DLQ Errors by Type | Pie Chart | Error type distribution |
| Latest Ingestion | Table | Data freshness per topic |

### Silver Quality Dashboard

**URL**: http://localhost:8088/superset/dashboard/silver-quality/

Monitors data quality in the Silver (cleaned/validated) layer.

| Chart | Type | Description |
|-------|------|-------------|
| Total Anomalies (24h) | Big Number | Total anomalies detected |
| GPS Outliers | Big Number | GPS coordinates outside São Paulo bounds |
| Impossible Speeds | Big Number | Speeds exceeding 200 km/h |
| Anomalies by Type | Pie Chart | Distribution of anomaly types |
| Anomalies Over Time | Time Series | Hourly anomaly trend |
| Staging Row Counts | Bar Chart | Row counts per staging table |
| Zombie Drivers | Table | Drivers with no GPS for 10+ minutes |
| Data Freshness | Table | Latest ingestion per staging table |

### Operations Dashboard

**URL**: http://localhost:8088/superset/dashboard/operations/

Real-time platform operations monitoring.

| Chart | Type | Description |
|-------|------|-------------|
| Active Trips | Big Number | Currently in-progress trips |
| Completed Today | Big Number | Trips completed today |
| Average Wait Time | Big Number | Average wait time in minutes |
| Total Revenue Today | Big Number | Daily revenue sum |
| DLQ Errors Last Hour | Time Series | Error volume trend |
| Total DLQ Errors | Pie Chart | Errors by type |
| Hourly Trip Volume | Time Series | 24-hour trip throughput |
| Pipeline Lag | Big Number | Event processing delay |
| Trips by Zone Today | Bar Chart | Geographic distribution |

### Driver Performance Dashboard

**URL**: http://localhost:8088/superset/dashboard/driver-performance/

Driver metrics and analytics.

| Chart | Type | Description |
|-------|------|-------------|
| Top 10 Drivers | Bar Chart | Top performers by trip count |
| Ratings Distribution | Histogram | Rating distribution |
| Payouts Over Time | Time Series | Driver payout trends |
| Utilization Heatmap | Heatmap | Driver utilization by date |
| Trips vs Revenue | Scatter | Trip count vs revenue correlation |
| Driver Status | Pie Chart | Status distribution |

### Demand Analysis Dashboard

**URL**: http://localhost:8088/superset/dashboard/demand-analysis/

Zone demand and surge pricing analysis.

| Chart | Type | Description |
|-------|------|-------------|
| Zone Demand Heatmap | Heatmap | Demand by zone and time |
| Surge Multiplier Trends | Time Series | Surge pricing trends |
| Wait Time by Zone | Bar Chart | Average wait by zone |
| Demand by Hour | Area Chart | Hourly demand patterns |
| Top Demand Zones | Table | Highest demand zones |
| Surge Events Timeline | Bar Chart | Surge event history |

### Revenue Analytics Dashboard

**URL**: http://localhost:8088/superset/dashboard/revenue-analytics/

Revenue metrics and KPIs.

| Chart | Type | Description |
|-------|------|-------------|
| Daily Revenue | Big Number | Today's total revenue |
| Total Fees | Big Number | Platform fees collected |
| Trip Count | Big Number | Total trips today |
| Revenue by Zone | Bar Chart | Zone revenue breakdown |
| Revenue Over Time | Time Series | 7-day revenue trend |
| Fare by Distance | Scatter | Distance vs fare analysis |
| Payment Methods | Pie Chart | Payment type distribution |
| Revenue by Hour | Heatmap | Revenue by hour and date |
| Top Revenue Zones | Table | Highest revenue zones |

## Testing

Comprehensive test suite covers all dashboards:

```bash
cd analytics/superset/tests
./venv/bin/pytest test_all_dashboards.py -v
```

Tests verify:
- All 6 dashboards exist with correct slugs
- Each dashboard has expected chart count
- Exported JSON files are valid ZIP archives
- Dashboard filters work correctly
- All charts load successfully via API
- Dashboard titles match expected values

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| Connection refused on port 8088 | Superset not started or still initializing | Wait 60-90 seconds, check logs with `docker compose logs -f superset` |
| Health check failing | Initialization incomplete | Check `superset-init` logs: `docker compose logs superset-init` |
| Cannot connect to Spark | Thrift Server not running | Start data-pipeline profile: `docker compose --profile data-pipeline up -d` |
| Tables not visible in SQL Lab | Lakehouse layer not created yet | Run DBT transformations: `cd services/dbt && ./venv/bin/dbt run` |
| Port 5433 already in use | Another PostgreSQL instance running | Stop conflicting service or change port in compose.yml |
| Port 6380 already in use | Another Redis instance running | Stop conflicting service or change port in compose.yml |
| "Rideshare Lakehouse" missing | Auto-provisioning failed | Check entrypoint logs, manually create connection via UI |
| Query timeout in SQL Lab | Large dataset or slow Spark | Increase cache timeout in database settings, enable async execution |
| Login fails with admin/admin | Admin user not created | Check `superset-init` logs, ensure `superset fab create-admin` ran successfully |
| Dashboards not imported | import_dashboards.py failed | Check logs for import errors, run manually with `--force` flag |

**Connection String Mismatch:**
- If using `database-connections.md` guide, note that auto-provisioned connection is named **"Rideshare Lakehouse"**, not "Rideshare Gold Layer"
- SQLAlchemy URI is identical: `hive://spark-thrift-server:10000/default?auth=NOSASL`

## Related

- [CONTEXT.md](CONTEXT.md) - Architecture context and design decisions
- [database-connections.md](database-connections.md) - Detailed Spark connection guide
- [dashboards/README.md](dashboards/README.md) - Dashboard creation scripts documentation
- [../../services/dbt/README.md](../../services/dbt/README.md) - DBT transformations that create lakehouse tables
- [../../infrastructure/docker/compose.yml](../../infrastructure/docker/compose.yml) - Docker Compose configuration

---

## Additional Notes

### Port Allocation

- PostgreSQL runs on port **5433** (not 5432) to avoid conflicts with Airflow PostgreSQL
- Redis runs on port **6380** (not 6379) to avoid conflicts with simulation Redis

### Default Behavior

- Dashboards auto-imported on container startup from ZIP exports in dashboards/
- Admin user created during initialization with credentials: `admin` / `admin`
- Spark Thrift Server connection auto-provisioned on first startup
- Database name: "Rideshare Lakehouse" (not manually configured)

### Security Considerations

This is a **development configuration** with:
- Default admin credentials (`admin`/`admin`)
- No authentication on Spark Thrift Server (NOSASL mode)
- CSRF protection enabled but with dev secret key

**Production deployments should:**
- Change `SUPERSET_SECRET_KEY` to a strong random value
- Update admin password immediately
- Enable Kerberos authentication on Spark Thrift Server
- Use SSL/TLS for encrypted connections
- Implement row-level security in Superset
- Configure database-specific roles and permissions
- Audit query access logs
