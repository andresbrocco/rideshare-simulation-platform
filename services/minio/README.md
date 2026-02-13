# MinIO

> S3-compatible object storage for the medallion lakehouse architecture (Bronze, Silver, Gold buckets)

## Quick Reference

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MINIO_ROOT_USER` | MinIO root username | Injected from `rideshare/minio` secret | Yes |
| `MINIO_ROOT_PASSWORD` | MinIO root password | Injected from `rideshare/minio` secret | Yes |

**Note:** Credentials are managed via LocalStack Secrets Manager and injected by the `secrets-init` service. See `CLAUDE.md` for details.

### Ports

| Port | Service | URL |
|------|---------|-----|
| 9000 | S3 API | http://localhost:9000 |
| 9001 | Web Console | http://localhost:9001 |

### Buckets

| Bucket | Layer | Purpose |
|--------|-------|---------|
| `rideshare-bronze` | Bronze | Raw event data ingestion |
| `rideshare-silver` | Silver | Cleaned and validated data |
| `rideshare-gold` | Gold | Business-ready analytics tables |

Buckets are created automatically by the `minio-init` service on startup.

### Health Check

```bash
# Check MinIO health
curl -f http://localhost:9000/minio/health/live
```

## Common Tasks

### Start MinIO

```bash
# Start MinIO with data-pipeline profile
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d minio

# Wait for health check to pass
docker compose -f infrastructure/docker/compose.yml ps minio
```

### Access Web Console

1. Navigate to http://localhost:9001
2. Login with credentials from LocalStack Secrets Manager (default: `admin` / `admin`)
3. Browse buckets: `rideshare-bronze`, `rideshare-silver`, `rideshare-gold`

### List Buckets Using mc CLI

```bash
# Exec into minio-init container (has mc client)
docker exec -it rideshare-minio-init sh

# List buckets
mc ls local/

# List objects in bronze bucket
mc ls local/rideshare-bronze/
```

### Upload Files Manually

```bash
# Upload a file to bronze bucket
mc cp /path/to/file.json local/rideshare-bronze/prefix/
```

### Query Bucket Policies

```bash
# Get bucket policy
mc policy get local/rideshare-bronze

# Set public read policy (not recommended for production)
mc policy set download local/rideshare-bronze
```

## Configuration

| File | Purpose |
|------|---------|
| `Dockerfile` | Custom MinIO build from source (RELEASE.2025-10-15T17-29-55Z) |
| `infrastructure/docker/compose.yml` | Service definition, volume mounts, health checks |

### Volume Mounts

- `/data` → `minio-data` volume (persistent object storage)

## Prerequisites

- Docker Compose
- `secrets-init` service completed (provides MinIO credentials)

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `minio` service unhealthy | Health check failing at `/minio/health/live` | Check container logs: `docker compose -f infrastructure/docker/compose.yml logs minio` |
| Buckets not created | `minio-init` service failed | Check init logs: `docker compose -f infrastructure/docker/compose.yml logs minio-init` |
| Access denied errors | Invalid credentials | Verify `secrets-init` completed and secrets are readable in `/secrets/minio.env` |
| Connection refused on 9000 | Service not started or port conflict | Ensure `--profile data-pipeline` is used; check `docker compose ps` |
| Web console shows blank page | Browser cache or network issue | Clear browser cache, verify http://localhost:9001 is accessible |

### Debug Secrets

```bash
# Check if secrets are available
docker compose -f infrastructure/docker/compose.yml exec minio cat /secrets/minio.env

# Verify secrets-init completed
docker compose -f infrastructure/docker/compose.yml logs secrets-init
```

### Inspect Storage

```bash
# Check data volume
docker volume inspect rideshare-simulation-platform_minio-data

# View bucket contents from host
docker compose -f infrastructure/docker/compose.yml exec minio ls -la /data/
```

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context
- [../../infrastructure/docker/compose.yml](../../infrastructure/docker/compose.yml) — Service definition
- [../bronze-ingestion/README.md](../bronze-ingestion/README.md) — Kafka → Bronze ingestion
- [../../tools/dbt/README.md](../../tools/dbt/README.md) — Bronze → Silver → Gold transformations
