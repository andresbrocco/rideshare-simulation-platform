# Apache Superset BI Stack

Apache Superset 6.0.0 deployment for business intelligence dashboards and SQL exploration.

## Architecture

- **Superset**: BI tool (768MB) at http://localhost:8088
- **PostgreSQL**: Metadata database (256MB) on port 5433
- **Redis**: Cache layer (128MB) on port 6380
- **Total Memory**: 1152MB

Note: Using 6.0.0 image which includes psycopg2-binary for PostgreSQL connectivity.

## Quick Start

```bash
# Start Superset stack (from project root)
docker compose -f infrastructure/docker/compose.yml --profile bi up -d

# Check service health
docker compose -f infrastructure/docker/compose.yml ps | grep superset

# View logs
docker compose -f infrastructure/docker/compose.yml logs -f superset

# Stop services
docker compose -f infrastructure/docker/compose.yml --profile bi down
```

## Access

- UI: http://localhost:8088
- Login: admin / admin
- Health: http://localhost:8088/health

## Configuration

Configuration is loaded from `analytics/superset/superset_config.py`:

- PostgreSQL metadata database connection
- Redis cache configuration (5 separate databases)
- Row limits and security settings
- Feature flags

## Database Connections

To connect Superset to data sources:

1. Log in to Superset UI
2. Settings > Database Connections > + Database
3. Add Spark SQL connection:
   - Host: spark-thrift-server
   - Port: 10000
   - Schema: default
   - SQLAlchemy URI: `hive://spark-thrift-server:10000/default?auth=NOSASL`

## Memory Allocation

- superset: 768MB
- postgres-superset: 256MB
- redis-superset: 128MB

## Notes

- PostgreSQL runs on port 5433 (not 5432) to avoid conflicts with Airflow PostgreSQL
- Redis runs on port 6380 (not 6379) to avoid conflicts with simulation Redis
- No example dashboards loaded by default
- Admin user created during initialization
