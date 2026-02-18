# CONTEXT.md — PostgreSQL (Metastore)

## Purpose

PostgreSQL 16 relational database instance storing the Hive Metastore catalog. This is one of two independent PostgreSQL instances in the platform; this one is dedicated to the Hive Metastore used by Trino and Spark to discover Delta Lake tables.

## Responsibility Boundaries

- **Owns**: Relational data persistence for Hive Metastore catalog, data integrity via ACID transactions, connection management
- **Delegates to**: Hive Metastore for catalog operations (table/partition definitions, schema evolution)
- **Does not handle**: Airflow metadata (separate `postgres-airflow` instance), application data (MinIO/Delta Lake), query execution (Trino/Spark), scheduling (Airflow)

## Key Concepts

**Hive Metastore Catalog**: Stores table definitions, partition metadata, column schemas, and SerDe information. Accessed exclusively by the `hive-metastore` service via JDBC (`jdbc:postgresql://postgres-metastore:5432/metastore`).

**Named Volume**: Uses `postgres-metastore-data` Docker volume for data persistence across container restarts.

**Stock Image**: Uses the `postgres:16` image with env-var-only configuration. No custom config files exist in this directory.

## Non-Obvious Details

This instance listens on host port 5434 (mapped to container port 5432). The other instance (`postgres-airflow`) listens on host port 5432.

Memory limit is 256MB. Health check runs `pg_isready -U <user>` every 5 seconds with a 30-second start period.

Credentials are injected from LocalStack Secrets Manager via the `data-pipeline.env` secrets file (`POSTGRES_METASTORE_USER`, `POSTGRES_METASTORE_PASSWORD`). Default development credentials are `admin`/`admin`.
