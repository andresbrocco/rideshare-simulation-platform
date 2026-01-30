# CONTEXT.md — Superset

## Purpose

Apache Superset 6.0.0 BI stack for business intelligence dashboards and SQL exploration across all medallion lakehouse layers (Bronze, Silver, Gold). Provides programmatic dashboard provisioning via Python scripts, automated dashboard import on container startup, centralized SQL query libraries, and API-based testing infrastructure.

## Responsibility Boundaries

- **Owns**: BI dashboard configuration (6 dashboards, 46 charts), virtual dataset definitions, SQL query libraries (bronze_queries.py, silver_queries.py, gold_queries.py), database connection auto-provisioning, cache layer configuration, dashboard export/import automation
- **Delegates to**: PostgreSQL for metadata persistence, Redis for multi-layer caching, Spark Thrift Server for lakehouse queries
- **Does not handle**: Dashboard creation logic (delegated to Python scripts in dashboards/ subdirectory), data transformation (handled by DBT), data storage (handled by Delta Lake on MinIO)

## Key Concepts

**Medallion Layer Dashboards**: Six dashboards organized by data layer:
- **Bronze Layer**: Bronze Pipeline Dashboard (8 charts) - ingestion metrics, DLQ errors, Kafka partition distribution
- **Silver Layer**: Silver Quality Dashboard (8 charts) - anomaly detection, staging table health, data freshness
- **Gold Layer**: Operations (9 charts), Driver Performance (6 charts), Demand Analysis (6 charts), Revenue Analytics (9 charts) - business metrics

**Centralized Query Libraries**: SQL queries are organized into three Python modules:
- `dashboards/bronze_queries.py` - Bronze layer queries (ingestion, DLQ, partitions)
- `dashboards/silver_queries.py` - Silver layer queries (anomalies, staging tables)
- `dashboards/gold_queries.py` - Gold layer queries (facts, dimensions, aggregates)

**Auto-provisioning**: docker-entrypoint.sh automatically creates "Rideshare Lakehouse" database connection on container startup by directly inserting into PostgreSQL metadata database, eliminating manual configuration.

**Automated Dashboard Import**: After server startup, docker-entrypoint.sh runs import_dashboards.py which authenticates via REST API, checks for existing dashboards by slug, and imports from ZIP files if not present. Import failures are non-blocking.

**Multi-layer Caching**: Redis uses 6 separate databases (0-5) for different cache concerns - Celery broker (0), Celery results (0), query results (1), general cache (2), data cache (3), filter state cache (4), and explore form cache (5).

**Virtual Datasets**: All dashboards use SQL-based virtual datasets rather than physical tables, enabling dashboard creation before actual tables exist and allowing flexible query definition.

## Non-Obvious Details

The entrypoint script waits for superset-init to complete by checking for ab_user table, not just PostgreSQL connectivity. This ensures admin user and schema are initialized before provisioning the Spark connection.

Database connection uses NOSASL authentication mode (hive://spark-thrift-server:10000/default?auth=NOSASL) because development environment has no Kerberos. Production should enable authentication.

Port mappings expose services on non-standard host ports (PostgreSQL on 5433, Redis on 6380) to avoid conflicts with Airflow and simulation services, but internal container connections use standard ports (5432 for PostgreSQL, 6379 for Redis).

Dashboard creation scripts share a common SupersetClient class pattern that handles authentication, CSRF tokens, dataset creation, chart creation, and dashboard assembly. Each dashboard script imports queries from its respective query module.

Test fixtures handle both current API format (charts as string array) and legacy format (slices as object array) for backward compatibility across Superset versions.

Configuration uses environment variable for SECRET_KEY with development fallback, but deployment must override via SUPERSET_SECRET_KEY environment variable.

## Related Modules

- **[services/dbt](../../services/dbt/CONTEXT.md)** — Data source; Superset dashboards query Gold dimensional models (fact_trips, dim_drivers, agg_zone_hourly_metrics) and Silver staging tables created by DBT transformations
- **[services/bronze-ingestion](../../services/bronze-ingestion/CONTEXT.md)** — Data source for Bronze dashboards; Bronze Pipeline Dashboard monitors ingestion metrics from Bronze layer tables
- **[infrastructure/monitoring](../../infrastructure/monitoring/CONTEXT.md)** — Shares observability domain; both provide visualization tools (Grafana for infrastructure metrics, Superset for business analytics)
