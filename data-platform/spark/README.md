# Spark Cluster with Delta Lake

Apache Spark cluster configured for the rideshare data lakehouse.

## Services

| Service | Port | Description |
|---------|------|-------------|
| spark-master | 7077 | Spark master RPC |
| spark-master | 4040 | Spark master web UI |
| spark-worker | 8081 | Worker web UI |
| spark-thrift-server | 10000 | Thrift JDBC/ODBC SQL endpoint |
| spark-thrift-server | 4041 | Thrift Server Spark UI |

## Quick Start

```bash
docker compose up -d minio minio-init spark-master spark-worker spark-thrift-server
```

Access the Spark master UI at http://localhost:4040 and Thrift Server UI at http://localhost:4041.

## Configuration

The cluster runs Spark 4.0.0 with Delta Lake 4.0.0. S3A filesystem is pre-configured to connect to MinIO.

Worker resources:
- Memory: 1536MB
- Cores: 2

## Running Jobs

Submit a PySpark job:
```bash
docker exec rideshare-spark-worker spark-submit \
  --master spark://spark-master:7077 \
  --packages io.delta:delta-spark_2.13:4.0.0,org.apache.hadoop:hadoop-aws:3.4.1 \
  /opt/spark-scripts/test-delta-access.py
```

Interactive shell:
```bash
docker exec -it rideshare-spark-worker spark-shell \
  --master spark://spark-master:7077 \
  --packages io.delta:delta-spark_2.13:4.0.0,org.apache.hadoop:hadoop-aws:3.4.1
```

## Testing Delta Lake + MinIO

Verify the setup works:
```bash
docker exec rideshare-spark-worker spark-submit \
  --master spark://spark-master:7077 \
  --packages io.delta:delta-spark_2.13:4.0.0,org.apache.hadoop:hadoop-aws:3.4.1 \
  /opt/spark-scripts/test-delta-access.py
```

This creates a test Delta table in `s3a://rideshare-bronze/test-delta-table`.

## MinIO Integration

S3A configuration is passed at runtime via `--packages` and Spark config:

| Property | Value |
|----------|-------|
| fs.s3a.endpoint | http://minio:9000 |
| fs.s3a.path.style.access | true |
| fs.s3a.connection.ssl.enabled | false |

## Thrift Server (SQL Access)

The Thrift Server provides a JDBC/ODBC interface for SQL queries. External tools like DBT and Superset connect through this endpoint.

### Testing with Beeline

Connect to the Thrift Server:
```bash
docker exec -it rideshare-spark-thrift-server /opt/spark/bin/beeline -u jdbc:hive2://localhost:10000
```

Run the test script:
```bash
docker exec rideshare-spark-thrift-server /opt/spark/bin/beeline -u jdbc:hive2://localhost:10000 -f /opt/spark-scripts/thrift-test.sql
```

### JDBC Connection

For external tools:
- **Connection URL:** `jdbc:hive2://localhost:10000`
- **Driver class:** `org.apache.hive.jdbc.HiveDriver`
- **Username/Password:** None required for local dev

### SQL Examples

Create and query tables stored in MinIO:
```sql
-- Create a table in S3
CREATE TABLE my_table (id INT, name STRING)
USING parquet
LOCATION 's3a://rideshare-bronze/my-table';

-- Insert and query
INSERT INTO my_table VALUES (1, 'test');
SELECT * FROM my_table;
```
