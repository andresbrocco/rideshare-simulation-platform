# CONTEXT.md — PostgreSQL

## Purpose

PostgreSQL 16 relational database service providing catalog and metadata persistence for the data pipeline layer. Two independent instances run in Docker Compose: `postgres-airflow` stores Airflow workflow metadata, and `postgres-metastore` stores the Hive Metastore catalog used by Trino and Spark to discover Delta Lake tables.

## Responsibility Boundaries

- **Owns**: Relational data persistence for Airflow and Hive Metastore, data integrity via ACID transactions, connection management
- **Delegates to**: Airflow for workflow metadata management (DAG runs, task instances, XCom), Hive Metastore for catalog operations (table/partition definitions, schema evolution)
- **Does not handle**: Application data (stored in MinIO/Delta Lake), query execution over lakehouse data (Trino/Spark), scheduling (Airflow), schema discovery (Hive Metastore)

## Key Concepts

**Two Independent Instances**: The instances share no data and serve different purposes. They use the stock `postgres:16` image with env-var-only configuration (no custom config files in this directory).

**postgres-airflow**: Stores Airflow metadata including DAG run history, task instance state, XCom values, connection definitions, and variable storage. Accessed by both `airflow-webserver` and `airflow-scheduler` via SQLAlchemy (`postgresql+psycopg2://airflow:airflow@postgres-airflow/airflow`).

**postgres-metastore**: Stores the Hive Metastore catalog including table definitions, partition metadata, column schemas, and SerDe information. Accessed exclusively by the `hive-metastore` service via JDBC (`jdbc:postgresql://postgres-metastore:5432/metastore`).

**Named Volumes**: Each instance has a dedicated Docker volume (`postgres-airflow-data`, `postgres-metastore-data`) for data persistence across container restarts.

## Non-Obvious Details

The two instances are completely independent -- they do not share data, users, or network ports. `postgres-airflow` listens on host port 5432, while `postgres-metastore` listens on host port 5434 (mapped to container port 5432).

Both instances use 256MB memory limits. Health checks run `pg_isready` with the appropriate user (`-U airflow` or `-U hive`) every 5 seconds with a 30-second start period.

This directory contains no custom configuration files. All PostgreSQL configuration is handled through environment variables (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`) in `infrastructure/docker/compose.yml`.

## Related Modules

- **[services/airflow](../airflow/CONTEXT.md)** — Both airflow-webserver and airflow-scheduler connect to postgres-airflow for workflow metadata
- **[services/hive-metastore](../hive-metastore/CONTEXT.md)** — Connects to postgres-metastore for catalog persistence via JDBC
- **[infrastructure/docker](../../infrastructure/docker/CONTEXT.md)** — Deployment orchestration; defines both PostgreSQL instances, volumes, and health checks
