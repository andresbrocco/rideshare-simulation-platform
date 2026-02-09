# CONTEXT.md — Hive Metastore

## Purpose

Apache Hive 4.0.0 Metastore service that stores table and partition metadata for Delta Lake tables in the medallion lakehouse architecture. Acts as the shared catalog that allows Trino and Spark to discover and query the same tables without duplicating schema definitions.

## Responsibility Boundaries

- **Owns**: Table/partition metadata, schema evolution tracking, warehouse location mappings
- **Delegates to**: postgres-metastore (PostgreSQL 16) for catalog persistence, MinIO for actual data storage via S3A filesystem, Trino and Spark for query execution
- **Does not handle**: Query processing, data storage, authentication, data transformation

## Key Concepts

**Custom Dockerfile**: The base `apache/hive:4.0.0` image ships with Derby as its default metastore backend. The Dockerfile adds the PostgreSQL JDBC driver (`postgresql-42.7.4.jar`) and copies `hadoop-aws` and `aws-java-sdk-bundle` JARs into the Hive classpath for S3A filesystem support.

**S3A Filesystem**: Configured in `hive-site.xml` to connect to MinIO using path-style access (`fs.s3a.path.style.access=true`) over plain HTTP. The default warehouse directory is `s3a://rideshare-silver/warehouse/`.

**Thrift Protocol**: Exposes the Hive Metastore API on port 9083 via Thrift. Trino's Delta Lake connector and Spark both connect to this endpoint to resolve table metadata.

**PostgreSQL Backend**: Catalog data (table definitions, partition info, schema versions) is persisted in the `metastore` database on the `postgres-metastore` service, replacing the default embedded Derby.

## Non-Obvious Details

The Dockerfile downloads the PostgreSQL JDBC driver since the base image only ships with Derby. Schema initialization (`schematool -initSchema`) runs automatically on first startup via the Hive entrypoint.

The `hadoop-aws` and `aws-java-sdk-bundle` JARs are copied from Hadoop's tools directory into Hive's lib directory because they are not on the classpath by default, even though they ship with the base image.

The health check uses a raw TCP socket test (`bash -c 'echo > /dev/tcp/localhost/9083'`) rather than a Thrift client, with a 120-second start period to accommodate schema initialization on first boot.

## Related Modules

- **[services/trino](../trino/CONTEXT.md)** — Connects to Hive Metastore via Thrift for Delta Lake table metadata resolution
- **[services/spark-streaming](../spark-streaming/CONTEXT.md)** — Uses Hive Metastore as the catalog for Spark SQL operations
- **[services/postgres](../postgres/CONTEXT.md)** — postgres-metastore instance provides catalog persistence
- **[infrastructure/docker](../../infrastructure/docker/CONTEXT.md)** — Deployment orchestration; defines hive-metastore service and build context
