# auth-deploy

> Control-plane Lambda for platform deploy/teardown lifecycle: API key auth, GitHub Actions workflow dispatch, session time-boxing with auto-teardown, and deploy/teardown progress reporting.

## Quick Reference

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `AWS_REGION` | No | AWS region for all SDK clients (defaults to `us-east-1`) |
| `LOCALSTACK_HOSTNAME` | No | When set, all AWS SDK clients point to `http://<hostname>:4566` instead of AWS. Used in local dev. |
| `SCHEDULER_ROLE_ARN` | Yes | IAM role ARN that EventBridge Scheduler uses to invoke this Lambda for auto-teardown. Injected by Terraform. |
| `SELF_FUNCTION_ARN` | Yes | This Lambda's own ARN, used as the EventBridge schedule target. Injected by Terraform. |
| `VISITOR_TABLE_NAME` | No | DynamoDB table for visitor records (defaults to `rideshare-visitors`). |
| `KMS_VISITOR_PASSWORD_KEY` | Yes | KMS key ARN used to encrypt/decrypt visitor plaintext passwords for post-deploy reprovisioning. |
| `SES_FROM_ADDRESS` | No | Sender address for welcome emails (defaults to `noreply@ridesharing.portfolio.andresbrocco.com`). |
| `SES_FROM_NAME` | No | Sender display name for welcome emails (defaults to `Rideshare Platform`). |
| `SES_REPLY_TO_ADDRESS` | No | Reply-to address for welcome emails. Omitted from SES request if not set. |
| `GRAFANA_URL` | No | Grafana base URL for visitor provisioning (defaults to `http://localhost:3001`). |
| `GRAFANA_ADMIN_PASSWORD` | No | Grafana admin password override; resolved from `rideshare/monitoring` secret when absent. |
| `AIRFLOW_URL` | No | Airflow base URL for visitor provisioning (defaults to `http://localhost:8082`). |
| `AIRFLOW_ADMIN_USER` | No | Airflow admin username for provisioning (defaults to `admin`). |
| `AIRFLOW_ADMIN_PASSWORD` | No | Airflow admin password override; resolved from `rideshare/data-pipeline` secret when absent. |
| `MINIO_ENDPOINT` | No | MinIO endpoint (no scheme) for visitor provisioning (defaults to `localhost:9000`). |
| `MINIO_ACCESS_KEY` | No | MinIO admin access key; resolved from `rideshare/data-pipeline` secret when absent. |
| `MINIO_SECRET_KEY` | No | MinIO admin secret key; resolved from `rideshare/data-pipeline` secret when absent. |
| `SIMULATION_API_URL` | No | Simulation API base URL for visitor provisioning (defaults to production URL). |

### AWS Secrets (read at runtime via Secrets Manager)

| Secret ID | Description |
|---|---|
| `rideshare/api-key` | API key validated on all authenticated actions. Stored as plain string or `{"API_KEY": "..."}`. Also used as the Simulation API admin key during visitor provisioning. |
| `rideshare/github-pat` | GitHub Personal Access Token for workflow dispatch and status polling. Stored as plain string or `{"GITHUB_PAT": "..."}`. |
| `rideshare/monitoring` | JSON-encoded secret containing `ADMIN_PASSWORD` for Grafana admin auth during visitor provisioning. |
| `rideshare/data-pipeline` | JSON-encoded secret containing `AIRFLOW_ADMIN_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` for visitor provisioning. |

### SSM Parameter Store

| Parameter | Description |
|---|---|
| `/rideshare/session/deadline` | JSON blob holding the current session state (deployed_at, deadline, tearing_down flag, deploy_progress map, teardown_run_id). |

### DynamoDB

| Table | Partition Key | Description |
|---|---|---|
| `rideshare-visitors` (env: `VISITOR_TABLE_NAME`) | `email` (String) | Visitor records: display name, PBKDF2 hash, KMS-encrypted password, provisioned services list, consent timestamp. |

### Lambda Configuration

| Property | Value |
|---|---|
| Function name | `rideshare-auth-deploy` |
| Runtime | Python 3.13 |
| Handler | `handler.lambda_handler` |
| Timeout | 30 seconds |
| Memory | 256 MB |
| Log group | `/aws/lambda/rideshare-auth-deploy` (14-day retention) |
| Log format | CloudWatch (print statements) |

### Function URL

The Lambda is exposed via an AWS Lambda Function URL (public, no IAM auth — application-level auth is handled inside the handler). CORS is configured at the Function URL level in Terraform; do not add CORS headers in code.

**Production URL:** emitted as Terraform output `module.lambda_auth_deploy.function_url`

**CORS allowed origins:**
- `https://ridesharing.portfolio.andresbrocco.com`
- `https://control-panel.ridesharing.portfolio.andresbrocco.com`
- `http://localhost:5173`

### API Actions

All requests use `POST` with a JSON body `{ "action": "<action>", "api_key": "<key>", ... }`.

The Lambda supports two invocation modes:
- **Function URL** — HTTP envelope with `body` as a JSON string. Returns `{ statusCode, headers, body }`.
- **Direct invocation** — action/api_key as top-level event fields. Returns the business response dict directly. Used by EventBridge Scheduler and local dev.

#### Actions requiring API key

| Action | Extra fields | Description |
|---|---|---|
| `validate` | — | Check whether the API key is valid. |
| `deploy` | `dbt_runner` (`duckdb`\|`glue`, default `duckdb`) | Dispatch `deploy.yml` GitHub Actions workflow and create a deploying session. Returns 409 if a session already exists. |
| `status` | — | Return the latest `deploy.yml` run status from GitHub. |
| `activate-session` | — | Set the session deadline (starts countdown). Idempotent — safe to call multiple times. |
| `report-deploy-progress` | `service` (string), `ready` (bool) | Mark a named service as ready/not-ready in the session. Called by the deploy workflow. |
| `set-teardown-run-id` | `run_id` (int) | Cache the teardown workflow run ID in SSM. Called by `teardown-platform.yml`. |
| `complete-teardown` | — | Delete the session from SSM. Called by `teardown-platform.yml` on completion. |
| `reprovision-visitors` | — | Scan DynamoDB visitors table, decrypt passwords, and recreate ephemeral service accounts in Grafana, Airflow, MinIO, and the Simulation API. Called by the deploy workflow after services are healthy. Requires API key. |

#### Actions requiring no API key

| Action | Extra fields | Description |
|---|---|---|
| `session-status` | — | Return the current session phase (inactive / deploying / active with countdown / tearing_down). Includes cost estimate. |
| `service-health` | — | Parallel health-check of all production service endpoints. Returns `{ services: { <id>: bool } }`. |
| `teardown-status` | — | Return step-level teardown progress (5 UI steps mapped from GitHub Actions job steps). |
| `get-deploy-progress` | — | Return per-service deploy readiness and `all_ready` flag. |
| `auto-teardown` | — | Internal — called by EventBridge Scheduler. Triggers teardown unless a deploy is in progress (in which case it reschedules 5 min later). |
| `provision-visitor` | `email` (string), `password` (string, optional — auto-generated if absent), `name` (string) | Phase 1: KMS-encrypt password in DynamoDB, send SES welcome email. Returns `{ provisioned, email_sent, services }`. |
| `extend-session` | — | Add 15 minutes to the deadline (max 2 hours remaining). |
| `shrink-session` | — | Remove 15 minutes from the deadline (min 0 minutes remaining). |

### Tracked Services (deploy progress)

`kafka`, `redis`, `schema-registry`, `osrm`, `stream-processor`, `simulation`, `bronze-ingestion`, `airflow`, `glue-catalog`, `trino`, `prometheus`, `grafana`, `loki`, `tempo`, `control-panel`, `performance-controller`

### Health Endpoints Checked (service-health)

| Service | URL |
|---|---|
| `simulation_api` | `https://api.ridesharing.portfolio.andresbrocco.com/health` |
| `grafana` | `https://grafana.ridesharing.portfolio.andresbrocco.com/api/health` |
| `airflow` | `https://airflow.ridesharing.portfolio.andresbrocco.com/api/v2/monitor/health` |
| `trino` | `https://trino.ridesharing.portfolio.andresbrocco.com/v1/info` |
| `prometheus` | `https://prometheus.ridesharing.portfolio.andresbrocco.com/-/healthy` |

### Session Lifecycle

```
deploy → deploying (deployed_at set, no deadline)
    ↓ (activate-session called after all services ready)
active (deadline set, EventBridge schedule created)
    ↓ (deadline reached or manual teardown)
tearing_down (tearing_down: true, teardown workflow dispatched)
    ↓ (complete-teardown called by workflow)
inactive (SSM parameter deleted)
```

**Session step:** 15 minutes per extend/shrink increment.
**Maximum session:** 2 hours remaining.
**Stale deploying timeout:** 30 minutes (auto-deleted if no activation).
**Stale tearing_down timeout:** 15 minutes (auto-deleted if teardown workflow finishes).

### Visitor Provisioning (Two-Phase)

Visitor accounts are created in two phases to tolerate a cold-start where the platform is not yet deployed:

**Phase 1 — `provision-visitor` (unauthenticated, pre-deploy)**

1. Validates `email` and `password` (auto-generates a 12-char password if omitted).
2. Stores the KMS-encrypted password and record in DynamoDB.
3. Sends a welcome email via SES with login credentials for all services.

**Phase 2 — `reprovision-visitors` (authenticated, post-deploy)**

Called by the deploy workflow via `POST {"action": "reprovision-visitors", "api_key": "..."}` after services report healthy. It:

1. Scans DynamoDB for all visitor records.
2. Decrypts each password using KMS.
3. Calls provisioning sub-modules for Grafana, Airflow, MinIO, and the Simulation API.
4. Returns `{ provisioned: N, failed: M, results: [...] }` with HTTP 200 (all success) or 207 (partial failure).

#### Provisioning sub-modules

| Module | Function | Idempotency signal |
|---|---|---|
| `provision_grafana_viewer.py` | `provision_viewer()` | HTTP 412 on POST → update existing user |
| `provision_airflow_viewer.py` | `provision_viewer()` | HTTP 409 on POST → PATCH existing user |
| `provision_minio_visitor.py` | `provision_visitor()` | `user_info` check → `user_add` upsert |
| `provision_simulation_api_viewer.py` | `provision_viewer()` | HTTP 200 (updated) vs 201 (created) |

## Common Tasks

### Test an action locally (direct invocation against LocalStack)

```bash
# Validate API key
aws lambda invoke \
  --function-name rideshare-auth-deploy \
  --payload '{"action": "validate", "api_key": "admin"}' \
  --endpoint-url http://localhost:4566 \
  --profile rideshare \
  /dev/stdout

# Check session status (no auth)
aws lambda invoke \
  --function-name rideshare-auth-deploy \
  --payload '{"action": "session-status"}' \
  --endpoint-url http://localhost:4566 \
  --profile rideshare \
  /dev/stdout

# Trigger deploy
aws lambda invoke \
  --function-name rideshare-auth-deploy \
  --payload '{"action": "deploy", "api_key": "admin", "dbt_runner": "duckdb"}' \
  --endpoint-url http://localhost:4566 \
  --profile rideshare \
  /dev/stdout
```

### Call via Function URL (production)

```bash
LAMBDA_URL="https://<url-id>.lambda-url.us-east-1.on.aws"

# Validate
curl -s -X POST "$LAMBDA_URL" \
  -H "Content-Type: application/json" \
  -d '{"action": "validate", "api_key": "<key>"}'

# Trigger deploy
curl -s -X POST "$LAMBDA_URL" \
  -H "Content-Type: application/json" \
  -d '{"action": "deploy", "api_key": "<key>", "dbt_runner": "duckdb"}'

# Poll session status
curl -s -X POST "$LAMBDA_URL" \
  -H "Content-Type: application/json" \
  -d '{"action": "session-status"}'

# Poll deploy progress
curl -s -X POST "$LAMBDA_URL" \
  -H "Content-Type: application/json" \
  -d '{"action": "get-deploy-progress"}'
```

### Run unit tests

```bash
cd services/auth-deploy
../../venv/bin/python3 -m pytest test_handler.py -v
```

### Deploy updated Lambda code

```bash
# Terraform applies the archive_file source_dir automatically:
cd infrastructure/terraform/foundation
terraform apply -target=module.lambda_auth_deploy --profile rideshare
```

### Read logs

```bash
aws logs tail /aws/lambda/rideshare-auth-deploy --follow --profile rideshare
```

### Inspect current session state

```bash
aws ssm get-parameter \
  --name /rideshare/session/deadline \
  --profile rideshare \
  --query Parameter.Value \
  --output text | python3 -m json.tool
```

### Manually clear a stuck session

```bash
aws ssm delete-parameter \
  --name /rideshare/session/deadline \
  --profile rideshare

aws scheduler delete-schedule \
  --name rideshare-auto-teardown \
  --group-name default \
  --profile rideshare
```

## Troubleshooting

### 409 on deploy — "Deployment already in progress"

An SSM session parameter exists from a previous run. Check if the session is stale:

```bash
aws ssm get-parameter --name /rideshare/session/deadline --profile rideshare --query Parameter.Value --output text
```

If the `deployed_at` timestamp is old (>30 min for deploying, >15 min for tearing_down), `session-status` will auto-clear it on next call. Otherwise, delete manually (see above).

### Lambda returns 500 on secret retrieval

The Secrets Manager secret (`rideshare/api-key` or `rideshare/github-pat`) does not exist or the Lambda IAM role lacks `secretsmanager:GetSecretValue`. Verify:

```bash
aws secretsmanager get-secret-value --secret-id rideshare/api-key --profile rideshare
```

### EventBridge schedule not created

`SCHEDULER_ROLE_ARN` or `SELF_FUNCTION_ARN` environment variables are missing/empty. Confirm via:

```bash
aws lambda get-function-configuration --function-name rideshare-auth-deploy --profile rideshare \
  --query Environment.Variables
```

### CORS errors in browser

Do not add CORS headers inside `handler.py` — they are set exclusively by the Lambda Function URL configuration in Terraform. Adding them in code causes browsers to reject duplicate header values. Verify CORS origins in `infrastructure/terraform/foundation/main.tf` under `module.lambda_auth_deploy`.

### teardown-status returns no steps / run_id is null

The teardown workflow was just dispatched and has not been picked up by GitHub yet. The handler searches recent `teardown-platform.yml` runs within a 60-second window of `tearing_down_at`. Poll again after 10–15 seconds.

## Prerequisites

- AWS Secrets Manager secrets: `rideshare/api-key`, `rideshare/github-pat`
- SSM Parameter Store path: `/rideshare/session/*` (read/write/delete)
- EventBridge Scheduler group: `default`
- IAM role for scheduler invocation: `rideshare-scheduler-exec`
- GitHub PAT with `workflow` scope (to dispatch `deploy.yml` and `teardown-platform.yml`)

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context
- [infrastructure/terraform/foundation](../../terraform/foundation/CONTEXT.md) — Terraform module that provisions this Lambda, its IAM roles, EventBridge scheduler role, and CORS configuration
- [infrastructure/terraform/foundation/modules/lambda](../../terraform/foundation/modules/lambda/main.tf) — Reusable Lambda Terraform module
