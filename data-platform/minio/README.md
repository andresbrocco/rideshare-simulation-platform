# MinIO Object Storage

S3-compatible object storage for the rideshare data lakehouse.

## Buckets

| Bucket | Purpose |
|--------|---------|
| rideshare-bronze | Raw event data from Kafka |
| rideshare-silver | Cleaned and deduplicated data |
| rideshare-gold | Business-ready aggregates |
| rideshare-checkpoints | Spark Streaming checkpoints |

## Local Development

Start MinIO:
```bash
docker compose up -d minio minio-init
```

Access the console at http://localhost:9001 with:
- Username: `minioadmin`
- Password: `minioadmin`

## API Access

MinIO S3 API is available at http://localhost:9000.

Python example:
```python
import boto3

s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:9000",
    aws_access_key_id="minioadmin",
    aws_secret_access_key="minioadmin",
)

s3.list_buckets()
```

## Bucket Management

List buckets using MinIO Client:
```bash
docker run --rm --network rideshare-network --entrypoint /bin/sh \
  quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z \
  -c "mc alias set local http://minio:9000 minioadmin minioadmin && mc ls local/"
```

Re-initialize buckets:
```bash
docker compose up minio-init
```
