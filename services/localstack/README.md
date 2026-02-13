# LocalStack

> Local AWS service emulation for Secrets Manager, SNS, and SQS during development.

## Quick Reference

### Service Configuration

| Property | Value |
|----------|-------|
| Image | `localstack/localstack:4.12.0` |
| Port | `4566` (unified endpoint) |
| Additional Ports | `4510-4559` (individual service APIs) |
| Health Check | `http://localhost:4566/_localstack/health` |
| Profiles | `core`, `data-pipeline`, `monitoring` |

### Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `SERVICES` | `secretsmanager,sns,sqs` | Enabled AWS services |
| `PERSISTENCE` | `0` | Ephemeral data (lost on restart) |
| `LOCALSTACK_HOST` | `localhost:4566` | Endpoint for service-to-service calls |
| `DEBUG` | `0` | Debug logging disabled |
| `LS_LOG` | `info` | Log level |

### AWS Services Available

| Service | Purpose | Used By |
|---------|---------|---------|
| **Secrets Manager** | Credential storage and retrieval | All services via `secrets-init` |
| **SNS** | Pub/sub messaging | Currently unused, available for future features |
| **SQS** | Message queuing | Currently unused, available for future features |

### Secrets Managed

All application credentials are stored in LocalStack Secrets Manager:

| Secret Path | Contains | Used By |
|-------------|----------|---------|
| `rideshare/api-key` | API authentication key | `simulation`, `frontend` |
| `rideshare/minio` | S3-compatible storage credentials | `bronze-ingestion`, `airflow`, `trino` |
| `rideshare/redis` | Redis AUTH password | `simulation`, `stream-processor` |
| `rideshare/kafka` | SASL authentication | `kafka`, `simulation`, `stream-processor`, `bronze-ingestion` |
| `rideshare/schema-registry` | Schema registry credentials | `simulation`, `stream-processor`, `bronze-ingestion` |
| `rideshare/hive-thrift` | Hive Metastore authentication | `trino`, `hive-metastore` |
| `rideshare/ldap` | LDAP admin credentials | `openldap` (Kubernetes only) |
| `rideshare/airflow` | Airflow webserver/database | `airflow` |
| `rideshare/grafana` | Grafana admin credentials | `grafana` |
| `rideshare/postgres-airflow` | Airflow database | `postgres-airflow`, `airflow` |
| `rideshare/postgres-metastore` | Hive Metastore database | `postgres-metastore`, `hive-metastore` |

All secrets default to `admin` for username/password or format-compliant dev values for cryptographic keys.

### AWS CLI Configuration

```bash
export AWS_ACCESS_KEY_ID="test"
export AWS_SECRET_ACCESS_KEY="test"
export AWS_DEFAULT_REGION="us-east-1"
export AWS_ENDPOINT_URL="http://localhost:4566"
```

LocalStack accepts any credentials (no IAM validation). Convention is to use `test`/`test`.

## Common Tasks

### Verify Services Are Running

```bash
# Check LocalStack health
curl http://localhost:4566/_localstack/health

# Expected response (excerpt):
{
  "services": {
    "secretsmanager": "running",  # pragma: allowlist secret
    "sns": "running",
    "sqs": "running"
  }
}
```

### Test All Services

Run the validation script (requires AWS CLI installed locally):

```bash
cd /Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/localstack
./test-services.sh
```

This creates test resources (secret, SNS topic, SQS queue) and verifies round-trip functionality.

### List All Secrets

```bash
aws --endpoint-url=http://localhost:4566 secretsmanager list-secrets
```

### Retrieve a Secret

```bash
aws --endpoint-url=http://localhost:4566 \
  secretsmanager get-secret-value \
  --secret-id rideshare/api-key \
  --query SecretString \
  --output text
```

### Create a Custom Secret

```bash
aws --endpoint-url=http://localhost:4566 \
  secretsmanager create-secret \
  --name my-custom-secret \
  --secret-string '{"username":"admin","password":"admin"}'  # pragma: allowlist secret
```

### Create an SNS Topic

```bash
aws --endpoint-url=http://localhost:4566 \
  sns create-topic \
  --name my-notifications
```

### Create an SQS Queue

```bash
aws --endpoint-url=http://localhost:4566 \
  sqs create-queue \
  --queue-name my-queue
```

### View LocalStack Logs

```bash
docker compose -f infrastructure/docker/compose.yml logs -f localstack
```

## Secrets Initialization Flow

1. **LocalStack starts** - Health check waits for `/_localstack/health` to return 200
2. **`secrets-init` service runs** - Depends on LocalStack health
   - Runs `seed-secrets.py` to create all secrets in Secrets Manager
   - Runs `fetch-secrets.py` to download secrets and write to `/secrets/*.env` files
3. **Application services start** - Depend on `secrets-init` completion
   - Read credentials from `/secrets/core.env`, `/secrets/data-pipeline.env`, etc.

See `infrastructure/scripts/seed-secrets.py` for secret definitions.

## Troubleshooting

### LocalStack fails health check

**Symptom**: Container restarts repeatedly, `secrets-init` never runs.

**Cause**: Insufficient memory allocation.

**Solution**: LocalStack requires at least 256MB. Current config:
```yaml
mem_limit: 256m
```

If still failing, temporarily increase to 512MB and file an issue.

### Secrets not found after restart

**Symptom**: Services fail with "Secret not found" errors after `docker compose down/up`.

**Cause**: `PERSISTENCE=0` means all state is ephemeral.

**Solution**: This is expected behavior. `secrets-init` recreates secrets on every startup. Verify:
```bash
docker compose -f infrastructure/docker/compose.yml logs secrets-init
```

Look for "Successfully seeded X secrets" message.

### AWS CLI commands fail

**Symptom**: `aws` commands return connection errors.

**Cause**: LocalStack not running or wrong endpoint.

**Solution**:
```bash
# Check LocalStack is running
docker compose -f infrastructure/docker/compose.yml ps localstack

# Verify endpoint
curl http://localhost:4566/_localstack/health

# Ensure --endpoint-url is set
aws --endpoint-url=http://localhost:4566 secretsmanager list-secrets
```

### Different secret values in Kubernetes vs Docker

**Symptom**: Application works in Docker but fails in Kubernetes with auth errors.

**Cause**: Kubernetes uses External Secrets Operator (ESO) which may be out of sync.

**Solution**: Verify ESO is syncing from LocalStack:
```bash
kubectl get externalsecrets -A
kubectl describe externalsecret <name> -n <namespace>
```

See `infrastructure/kubernetes/CONTEXT.md` for ESO troubleshooting.

## Prerequisites

- Docker with at least 256MB allocatable to LocalStack
- AWS CLI (for testing and manual secret operations)
- LocalStack will **not** work without `/var/run/docker.sock` mounted (required for some internal features)

## Related

- [CONTEXT.md](CONTEXT.md) - Architecture context for LocalStack emulation
- [infrastructure/scripts/seed-secrets.py](/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/infrastructure/scripts/seed-secrets.py) - Secret definitions and seeding logic
- [infrastructure/scripts/fetch-secrets.py](/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/infrastructure/scripts/fetch-secrets.py) - Secret retrieval and `.env` file generation
- [infrastructure/kubernetes/CONTEXT.md](/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/infrastructure/kubernetes/CONTEXT.md) - External Secrets Operator integration
