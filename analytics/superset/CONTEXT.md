# CONTEXT.md — Superset

## Purpose

Apache Superset 6.0.0 BI stack for business intelligence dashboards and SQL exploration of the Rideshare Gold layer. Provides programmatic dashboard provisioning, automated database connection setup, and API-based testing infrastructure.

## Responsibility Boundaries

- **Owns**: BI dashboard configuration, virtual dataset definitions, database connection auto-provisioning, cache layer configuration, dashboard export/import automation
- **Delegates to**: PostgreSQL for metadata persistence, Redis for multi-layer caching, Spark Thrift Server for Gold layer queries
- **Does not handle**: Dashboard creation logic (delegated to Python scripts in dashboards/ subdirectory), data transformation (handled by DBT), data storage (handled by Delta Lake on MinIO)

## Key Concepts

**Auto-provisioning**: docker-entrypoint.sh automatically creates "Rideshare Lakehouse" database connection on container startup by directly inserting into PostgreSQL metadata database, eliminating manual configuration.

**Multi-layer caching**: Redis uses 6 separate databases (0-5) for different cache concerns - Celery broker (0), Celery results (0), query results (1), general cache (2), data cache (3), filter state cache (4), and explore form cache (5).

**Virtual datasets**: All dashboards use SQL-based virtual datasets rather than physical tables, enabling dashboard creation before actual tables exist and allowing flexible query definition.

**Dashboard export format**: JSON exports are ZIP files containing YAML dashboard definitions, chart configurations, and dataset definitions for version control and automated deployment.

**API-based testing**: Test suite uses Superset REST API with bearer token authentication to verify dashboard existence, chart counts, and accessibility without browser automation.

## Non-Obvious Details

The entrypoint script waits for superset-init to complete by checking for ab_user table, not just PostgreSQL connectivity. This ensures admin user and schema are initialized before provisioning the Spark connection.

Database connection uses NOSASL authentication mode (hive://spark-thrift-server:10000/default?auth=NOSASL) because development environment has no Kerberos. Production should enable authentication.

Port mappings expose services on non-standard host ports (PostgreSQL on 5433, Redis on 6380) to avoid conflicts with Airflow and simulation services, but internal container connections use standard ports (5432 for PostgreSQL, 6379 for Redis).

Test fixtures handle both current API format (charts as string array) and legacy format (slices as object array) for backward compatibility across Superset versions.

Configuration uses environment variable for SECRET_KEY with development fallback, but deployment must override via SUPERSET_SECRET_KEY environment variable.

## Related Modules

- **[services/dbt](../../services/dbt/CONTEXT.md)** — Data source; Superset dashboards query Gold dimensional models (fact_trips, dim_drivers, agg_zone_hourly_metrics) created by DBT transformations
- **[infrastructure/monitoring](../../infrastructure/monitoring/CONTEXT.md)** — Shares observability domain; both provide visualization tools (Grafana for infrastructure metrics, Superset for business analytics)
