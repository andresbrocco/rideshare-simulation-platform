# LocalStack

> AWS service emulation (Secrets Manager, SNS, SQS, Lambda) for local development — eliminates the need for a real AWS account when running the platform.

## Quick Reference

### Ports

| Port | Description |
|------|-------------|
| `4566` | LocalStack unified API endpoint (all AWS services) |
| `4510–4559` | LocalStack internal service port range |

### Health Endpoint

```bash
curl http://localhost:4566/_localstack/health
```

Returns a JSON object showing the health status of each emulated AWS service.

### Environment Variables

These variables are set inside the `localstack` container. Services that connect to LocalStack use these same values:

| Variable | Value | Description |
|----------|-------|-------------|
| `SERVICES` | `secretsmanager,sns,sqs,lambda` | AWS services to emulate |
| `LOCALSTACK_HOST` | `localhost:4566` | Advertised hostname for the LocalStack container |
| `PERSISTENCE` | `0` | No persistence across restarts (data lost on container stop) |
| `DEBUG` | `0` | Disable verbose LocalStack debug output |
| `LS_LOG` | `info` | Log level |

Connecting services (e.g., `secrets-init`, `lambda-init`, simulation) use:

| Variable | Value |
|----------|-------|
| `AWS_ENDPOINT_URL` | `http://localstack:4566` (container-to-container) or `http://localhost:4566` (host) |
| `AWS_ACCESS_KEY_ID` | `test` |
| `AWS_SECRET_ACCESS_KEY` | `test` |
| `AWS_DEFAULT_REGION` | `us-east-1` |

### Docker Service

```yaml
image: localstack/localstack:4.12.0
profiles: [core, data-pipeline, monitoring, performance]
```

LocalStack is present in all profiles — it is a dependency for every other service that reads credentials from Secrets Manager.

### Secrets Stored in LocalStack

All platform credentials live under the `rideshare/*` namespace in Secrets Manager. Seeded automatically by `secrets-init` on compose startup.

| Secret Name | Keys |
|-------------|------|
| `rideshare/api-key` | `API_KEY` |
| `rideshare/core` | `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD`, `REDIS_PASSWORD`, `SCHEMA_REGISTRY_USER`, `SCHEMA_REGISTRY_PASSWORD`, `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD` |
| `rideshare/data-pipeline` | `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `POSTGRES_AIRFLOW_USER`, `POSTGRES_AIRFLOW_PASSWORD`, `POSTGRES_METASTORE_USER`, `POSTGRES_METASTORE_PASSWORD`, `FERNET_KEY`, `INTERNAL_API_SECRET_KEY`, `JWT_SECRET`, `API_SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` |
| `rideshare/github-pat` | `GITHUB_PAT` |

### Lambda Functions Deployed

| Function Name | Runtime | Handler |
|---------------|---------|---------|
| `auth-deploy` | `python3.13` | `handler.lambda_handler` |

Deployed automatically by `lambda-init` after secrets are seeded.

### Commands

**Run the validation script against a running LocalStack instance:**

```bash
# From the services/localstack directory, targeting the running container:
AWS_ACCESS_KEY_ID=test \
AWS_SECRET_ACCESS_KEY=test \
AWS_DEFAULT_REGION=us-east-1 \
bash services/localstack/test-services.sh
```

**Manually re-seed secrets (e.g., after restarting LocalStack without restarting compose):**

```bash
AWS_ENDPOINT_URL=http://localhost:4566 \
AWS_ACCESS_KEY_ID=test \
AWS_SECRET_ACCESS_KEY=test \
AWS_DEFAULT_REGION=us-east-1 \
./venv/bin/python3 infrastructure/scripts/seed-secrets.py
```

**Override a specific secret value at seed time:**

```bash
OVERRIDE_MINIO_ROOT_PASSWORD=mysecret \
AWS_ENDPOINT_URL=http://localhost:4566 \
AWS_ACCESS_KEY_ID=test \
AWS_SECRET_ACCESS_KEY=test \
AWS_DEFAULT_REGION=us-east-1 \
./venv/bin/python3 infrastructure/scripts/seed-secrets.py
```

**Manually re-deploy the Lambda function:**

```bash
AWS_ENDPOINT_URL=http://localhost:4566 \
AWS_ACCESS_KEY_ID=test \
AWS_SECRET_ACCESS_KEY=test \
AWS_DEFAULT_REGION=us-east-1 \
./venv/bin/python3 infrastructure/scripts/deploy-lambda.py
```

**List all secrets via AWS CLI:**

```bash
aws --endpoint-url=http://localhost:4566 \
    --profile rideshare \
    secretsmanager list-secrets \
    --region us-east-1
```

**Retrieve a specific secret:**

```bash
aws --endpoint-url=http://localhost:4566 \
    --profile rideshare \
    secretsmanager get-secret-value \
    --secret-id rideshare/api-key \
    --region us-east-1
```

## Common Tasks

### Check which AWS services are healthy

```bash
curl -s http://localhost:4566/_localstack/health | python3 -m json.tool
```

### Inspect a secret value

```bash
aws --endpoint-url=http://localhost:4566 \
    --profile rideshare \
    secretsmanager get-secret-value \
    --secret-id rideshare/core \
    --query SecretString \
    --output text \
    --region us-east-1 | python3 -m json.tool
```

### Verify the auth Lambda is deployed

```bash
aws --endpoint-url=http://localhost:4566 \
    --profile rideshare \
    lambda get-function \
    --function-name auth-deploy \
    --region us-east-1
```

### Run the full AWS service smoke test

```bash
AWS_ACCESS_KEY_ID=test \
AWS_SECRET_ACCESS_KEY=test \
bash services/localstack/test-services.sh
```

This tests Secrets Manager (create + get), SNS (create topic + publish), and SQS (create queue + send + receive).

## Troubleshooting

**LocalStack takes too long to start / other services fail to connect**

LocalStack is a dependency for `secrets-init` and `lambda-init`, which gate the rest of the platform. Wait for the health check to pass before starting dependent services. The compose health check polls `/_localstack/health` every 10 seconds with up to 5 retries and a 10-second start period.

**Secrets missing after compose restart**

`PERSISTENCE=0` means all data is lost when the container stops. The `secrets-init` container re-seeds on every compose up. If you restart LocalStack without restarting compose, re-run `seed-secrets.py` manually (see Commands above).

**"No credentials found" errors in services**

Services read credentials from Secrets Manager at startup via `fetch-secrets.py`. If LocalStack was not healthy when `secrets-init` ran, secrets may be absent. Restart the `secrets-init` and `lambda-init` containers or run the seed script manually.

**AWS CLI profile not configured for LocalStack**

The `--profile rideshare` flag requires a profile with any non-empty credentials. Alternatively, export `AWS_ACCESS_KEY_ID=test` and `AWS_SECRET_ACCESS_KEY=test` directly and omit the profile flag.

## Prerequisites

- Docker with compose (`docker compose`)
- AWS CLI (for manual inspection commands)
- `./venv/bin/python3` with `boto3` and `mypy-boto3-secretsmanager` (installed in `secrets-init` container automatically)

## Related

- [infrastructure/scripts/seed-secrets.py](/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/infrastructure/scripts/seed-secrets.py) — Secret seeding script
- [infrastructure/scripts/deploy-lambda.py](/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/infrastructure/scripts/deploy-lambda.py) — Lambda deployment script
- [infrastructure/docker/compose.yml](/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/infrastructure/docker/compose.yml) — Full service definitions including `secrets-init` and `lambda-init`
- [docs/SECURITY.md](../../docs/SECURITY.md) — Secrets management policy and production guidance
