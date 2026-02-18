# CONTEXT.md — Spark Thrift Server

## Purpose

Apache Spark 4.0 Thrift Server providing a JDBC/ODBC endpoint for dual-engine DBT validation. Enables running DBT models against both Trino and Spark to verify SQL compatibility across query engines. Part of the optional `spark-testing` profile.

## Responsibility Boundaries

- **Owns**: JDBC/ODBC interface for Spark SQL queries, Spark UI for query monitoring
- **Delegates to**: Hive Metastore for table/partition catalog, MinIO for Delta Lake storage (S3A), OpenLDAP for LDAP authentication
- **Does not handle**: Table registration (Trino/delta-table-init), data ingestion (bronze-ingestion), workflow scheduling (Airflow), primary query serving (Trino)

## Key Concepts

**Dual-Engine Validation**: DBT models are developed against Trino (primary engine) but can be validated against Spark via this service to ensure SQL compatibility. This catches engine-specific SQL differences before production.

**Stock Image**: Uses the unmodified `apache/spark:4.0.0-python3` image. No custom Dockerfile exists -- all configuration is passed via `spark-submit` arguments in the compose entrypoint.

**LDAP Authentication**: Authenticates JDBC connections via the `openldap` service using `hive.server2.authentication=LDAP` with base DN `dc=rideshare,dc=local`.

**Delta Lake Integration**: Configured with `DeltaSparkSessionExtension` and `DeltaCatalog` to read/write Delta Lake tables stored on MinIO via the S3A filesystem connector.

**Hive Metastore Catalog**: Connects to the shared Hive Metastore (`thrift://hive-metastore:9083`) so Spark sees the same tables as Trino.

## Non-Obvious Details

This service is optional and only starts with the `spark-testing` profile. It is not required for normal platform operation -- Trino is the primary query engine.

Memory limit is 3072MB (3GB) with 1800MB driver memory and 512MB overhead. This is the most memory-intensive optional service.

The health check uses Beeline to execute `SELECT 1` against the Thrift Server, which requires the full Spark SQL pipeline to be operational. Start period is 90 seconds due to JVM/Spark initialization time.

MinIO credentials are injected at runtime from the `data-pipeline.env` secrets file, not hardcoded.
