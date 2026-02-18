# CONTEXT.md — PostgreSQL (Airflow)

## Purpose

PostgreSQL 16 relational database instance storing Airflow workflow metadata. This is one of two independent PostgreSQL instances in the platform; this one is dedicated to Airflow.

## Responsibility Boundaries

- **Owns**: Relational data persistence for Airflow, data integrity via ACID transactions, connection management
- **Delegates to**: Airflow for workflow metadata management (DAG runs, task instances, XCom)
- **Does not handle**: Hive Metastore catalog (separate `postgres-metastore` instance), application data (MinIO/Delta Lake), query execution (Trino/Spark)

## Key Concepts

**Airflow Metadata Store**: Stores DAG run history, task instance state, XCom values, connection definitions, and variable storage. Accessed by both `airflow-webserver` and `airflow-scheduler` via SQLAlchemy (`postgresql+psycopg2://<user>:<pass>@postgres-airflow:5432/airflow`).

**Named Volume**: Uses `postgres-airflow-data` Docker volume for data persistence across container restarts.

**Stock Image**: Uses the `postgres:16` image with env-var-only configuration. No custom config files exist in this directory.

## Non-Obvious Details

This instance listens on host port 5432 (mapped to container port 5432). The other instance (`postgres-metastore`) listens on host port 5434.

Memory limit is 256MB. Health check runs `pg_isready -U <user>` every 5 seconds with a 30-second start period.

Credentials are injected from LocalStack Secrets Manager via the `data-pipeline.env` secrets file (`POSTGRES_AIRFLOW_USER`, `POSTGRES_AIRFLOW_PASSWORD`). Default development credentials are `admin`/`admin`.
