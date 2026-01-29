# Apache Superset

> Apache Superset BI stack for Gold layer dashboards and SQL exploration

## Quick Reference

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
| `docker-entrypoint.sh` | Container startup script with auto-provisioning |
| `database-connections.md` | Guide for connecting to Spark Thrift Server |

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
- Gold layer tables created by DBT transformations
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

-- Count trips in Gold layer
SELECT COUNT(*) FROM gold.fact_trips;

-- View recent trips
SELECT trip_id, pickup_time, dropoff_time, total_fare
FROM gold.fact_trips
ORDER BY pickup_time DESC
LIMIT 10;

-- Check dimension tables
SELECT COUNT(*) FROM gold.dim_drivers;
SELECT COUNT(*) FROM gold.dim_riders;
SELECT COUNT(*) FROM gold.dim_zones;
```

### Create a Dataset

To build dashboards, register Gold layer tables:

1. Navigate to **Data > Datasets**
2. Click **+ Dataset**
3. Configure:
   - **Database**: Rideshare Lakehouse
   - **Schema**: gold
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

### Configuration Layers

**superset_config.py:**
- Database URI (PostgreSQL metadata)
- Redis cache configuration (5 separate databases)
- Celery broker/result backend
- Security settings (CSRF, secret key)
- Feature flags (template processing)
- Row limits (default 5000)

**docker-entrypoint.sh:**
- Installs PyHive, Thrift, psycopg2-binary dependencies
- Waits for PostgreSQL metadata database readiness
- Auto-provisions "Rideshare Lakehouse" database connection
- Starts Superset web server

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

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| Connection refused on port 8088 | Superset not started or still initializing | Wait 60-90 seconds, check logs with `docker compose logs -f superset` |
| Health check failing | Initialization incomplete | Check `superset-init` logs: `docker compose logs superset-init` |
| Cannot connect to Spark | Thrift Server not running | Start data-pipeline profile: `docker compose --profile data-pipeline up -d` |
| Tables not visible in SQL Lab | Gold layer not created yet | Run DBT transformations: `cd services/dbt && ./venv/bin/dbt run` |
| Port 5433 already in use | Another PostgreSQL instance running | Stop conflicting service or change port in compose.yml |
| Port 6380 already in use | Another Redis instance running | Stop conflicting service or change port in compose.yml |
| "Rideshare Lakehouse" missing | Auto-provisioning failed | Check entrypoint logs, manually create connection via UI |
| Query timeout in SQL Lab | Large dataset or slow Spark | Increase cache timeout in database settings, enable async execution |
| Login fails with admin/admin | Admin user not created | Check `superset-init` logs, ensure `superset fab create-admin` ran successfully |

**Connection String Mismatch:**
- If using `database-connections.md` guide, note that auto-provisioned connection is named **"Rideshare Lakehouse"**, not "Rideshare Gold Layer"
- SQLAlchemy URI is identical: `hive://spark-thrift-server:10000/default?auth=NOSASL`

## Related

- [CONTEXT.md](CONTEXT.md) - Architecture context and design decisions
- [database-connections.md](database-connections.md) - Detailed Spark connection guide
- [../../services/dbt/README.md](../../services/dbt/README.md) - DBT transformations that create Gold tables
- [../../infrastructure/docker/compose.yml](../../infrastructure/docker/compose.yml) - Docker Compose configuration

---

## Additional Notes

> Preserved from original README.md

### Port Allocation

- PostgreSQL runs on port **5433** (not 5432) to avoid conflicts with Airflow PostgreSQL
- Redis runs on port **6380** (not 6379) to avoid conflicts with simulation Redis

### Default Behavior

- No example dashboards loaded by default
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
