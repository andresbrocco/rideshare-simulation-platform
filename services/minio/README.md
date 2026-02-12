# MinIO Object Storage

> MinIO RELEASE.2025-10-15T17-29-55Z (built from source)

## Purpose

S3-compatible object storage for the rideshare data lakehouse.

**Files in this directory:**

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build from Go source for ARM64/AMD64 compatibility |
| `README.md` | This file |
| `CONTEXT.md` | Architecture context for AI agents |

## Buckets

| Bucket | Purpose |
|--------|---------|
| rideshare-bronze | Raw event data from Kafka |
| rideshare-silver | Cleaned and deduplicated data |
| rideshare-gold | Business-ready aggregates |
| rideshare-checkpoints | Bronze ingestion checkpoints |

## Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| S3 API Port | 9000 | S3-compatible API endpoint |
| Console Port | 9001 | Web UI for bucket management |
| Username | `minioadmin` | Default access key |
| Password | `minioadmin` | Default secret key |
| Memory Limit | 512MB | Docker container memory limit |
| Profile | `data-pipeline` | Docker Compose profile |

## Local Development

Start MinIO:
```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d minio minio-init
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
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up minio-init
```

## Troubleshooting

### MinIO not starting

Check container logs:
```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline logs minio
```

### Buckets not created

The `minio-init` sidecar creates buckets on startup. Check its logs:
```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline logs minio-init
```

Re-run bucket initialization:
```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up minio-init
```

### S3 connection refused from other services

Verify MinIO is healthy:
```bash
curl http://localhost:9000/minio/health/live
```

Ensure services are on the same Docker network (`rideshare-network`).

### Console not accessible

The console runs on port 9001, not 9000. Navigate to http://localhost:9001.

## References

- [CONTEXT.md](CONTEXT.md) - Architecture and design decisions
- [MinIO Documentation](https://min.io/docs/minio/linux/index.html)
- [MinIO Docker Guide](https://min.io/docs/minio/container/index.html)
- [infrastructure/docker/compose.yml](../../infrastructure/docker/compose.yml) - Docker service definitions
