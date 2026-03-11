# infrastructure/lambda

> Serverless control plane for portfolio platform lifecycle management — authentication, session tracking, cost metering, and GitHub Actions workflow dispatch/coordination.

## Quick Reference

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `AWS_REGION` | No | AWS region for all SDK clients (default: `us-east-1`) |
| `LOCALSTACK_HOSTNAME` | No | Set in local dev to route SDK calls to `http://{LOCALSTACK_HOSTNAME}:4566` instead of AWS |
| `SCHEDULER_ROLE_ARN` | Yes (prod) | IAM role ARN that EventBridge Scheduler uses to invoke this Lambda |
| `SELF_FUNCTION_ARN` | Yes (prod) | This Lambda's own ARN — used as the EventBridge Scheduler target for auto-teardown |
| `VISITORS_TABLE_NAME` | Yes (prod) | DynamoDB table name for durable visitor records (default: `rideshare-visitors`) |
| `VISITOR_KMS_KEY_ID` | Yes (prod) | KMS key ID used to encrypt/decrypt visitor plaintext passwords in DynamoDB |
| `SES_SENDER_EMAIL` | Yes (prod) | Verified SES sender address for visitor welcome emails |

### Secrets (AWS Secrets Manager)

| Secret ID | Key | Description |
|---|---|---|
| `rideshare/api-key` | `API_KEY` | Shared API key validated on all authenticated actions |
| `rideshare/github-pat` | `GITHUB_PAT` | GitHub Personal Access Token used for workflow dispatch and status polling |
| `rideshare/monitoring` | `ADMIN_PASSWORD` | Grafana admin password used by visitor provisioning sub-module |
| `rideshare/data-pipeline` | `AIRFLOW_ADMIN_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | Airflow and MinIO admin credentials used by visitor provisioning sub-modules |

### SSM Parameter Store

| Parameter | Description |
|---|---|
| `/rideshare/session/deadline` | JSON blob holding the active session state (deployed_at, deadline, tearing_down, deploy_progress, teardown_run_id) |

### Actions (API Surface)

All requests are JSON with an `action` field. Via Function URL, POST with `Content-Type: application/json`. Via direct invocation, pass the payload as the Lambda event.

#### Unauthenticated actions (no `api_key` required)

| Action | Description |
|---|---|
| `session-status` | Returns current session state, remaining time, cost-so-far |
| `service-health` | Parallel health check of all production service endpoints |
| `get-deploy-progress` | Returns per-service readiness map and `all_ready` flag |
| `teardown-status` | Returns step-level teardown progress from GitHub Actions |
| `auto-teardown` | Internal — invoked by EventBridge Scheduler when deadline expires |
| `provision-visitor` | Registers a visitor: stores Trino hash + KMS-encrypted password in DynamoDB, sends welcome email via SES (Phase 1 of two-phase provisioning) |
| `extend-session` | Adds 15 minutes to the current deadline (max 2 hours remaining) |
| `shrink-session` | Removes 15 minutes from the current deadline (min 0 minutes remaining) |

#### Authenticated actions (require `api_key`)

| Action | Extra fields | Description |
|---|---|---|
| `validate` | — | Validates the API key; returns `{"valid": true/false}` |
| `deploy` | `dbt_runner` (`"duckdb"` or `"glue"`, default `"duckdb"`) | Dispatches deploy.yml workflow; creates a deploying session |
| `status` | — | Returns latest deploy workflow run status from GitHub |
| `activate-session` | — | Sets the first deadline (called by frontend after health checks pass); idempotent |
| `reprovision-visitors` | — | Phase 2 of visitor provisioning — scans DynamoDB, decrypts passwords, creates ephemeral accounts in Grafana/Airflow/MinIO/Simulation API |
| `report-deploy-progress` | `service` (string), `ready` (bool) | Marks a service as ready in the SSM session; called by the deploy workflow |
| `set-teardown-run-id` | `run_id` (int) | Caches the teardown workflow run ID in the session for progress polling |
| `complete-teardown` | — | Deletes the session; called by teardown workflow at completion |

### Service Health Check Endpoints

| Service | URL |
|---|---|
| simulation_api | `https://api.ridesharing.portfolio.andresbrocco.com/health` |
| grafana | `https://grafana.ridesharing.portfolio.andresbrocco.com/api/health` |
| airflow | `https://airflow.ridesharing.portfolio.andresbrocco.com/api/v2/monitor/health` |
| trino | `https://trino.ridesharing.portfolio.andresbrocco.com/v1/info` |
| prometheus | `https://prometheus.ridesharing.portfolio.andresbrocco.com/-/healthy` |

### Session Constants

| Constant | Value | Description |
|---|---|---|
| `SESSION_STEP_MINUTES` | 15 | Granularity for extend/shrink operations |
| `MAX_REMAINING_SECONDS` | 7200 (2 h) | Hard cap on remaining session time |
| `PLATFORM_COST_PER_HOUR` | $0.31 | Hardcoded cost rate (1x t3.xlarge); drives `cost_so_far` calculation |
| `DEPLOYING_TIMEOUT_SECONDS` | 1800 (30 min) | Stale deploying session auto-cleanup threshold |
| `TEARDOWN_TIMEOUT_SECONDS` | 900 (15 min) | Stale tearing_down flag auto-cleanup threshold |
| `RESCHEDULE_DELAY_SECONDS` | 300 (5 min) | Reschedule delay when auto-teardown fires during an active deploy |

## Common Tasks

### Invoke locally via LocalStack

```bash
# Set env var so SDK routes to LocalStack
export LOCALSTACK_HOSTNAME=localhost

# Validate the API key
aws lambda invoke \
  --function-name auth-deploy \
  --payload '{"action":"validate","api_key":"admin"}' \
  --profile rideshare \
  /tmp/response.json && cat /tmp/response.json

# Check session status (no auth required)
aws lambda invoke \
  --function-name auth-deploy \
  --payload '{"action":"session-status"}' \
  --profile rideshare \
  /tmp/response.json && cat /tmp/response.json
```

### Trigger a deploy (Function URL)

```bash
curl -s -X POST "$LAMBDA_FUNCTION_URL" \
  -H "Content-Type: application/json" \
  -d '{"action":"deploy","api_key":"<your-api-key>","dbt_runner":"duckdb"}' | jq .
```

### Poll deploy progress (no auth)

```bash
curl -s -X POST "$LAMBDA_FUNCTION_URL" \
  -H "Content-Type: application/json" \
  -d '{"action":"get-deploy-progress"}' | jq .
```

### Activate session after deploy completes

```bash
curl -s -X POST "$LAMBDA_FUNCTION_URL" \
  -H "Content-Type: application/json" \
  -d '{"action":"activate-session","api_key":"<your-api-key>"}' | jq .
```

### Extend session by 15 minutes

```bash
# No api_key required — extend-session is unauthenticated
curl -s -X POST "$LAMBDA_FUNCTION_URL" \
  -H "Content-Type: application/json" \
  -d '{"action":"extend-session"}' | jq .
```

### Run unit tests

```bash
cd infrastructure/lambda/auth-deploy
./venv/bin/pytest test_handler.py -v
```

## Session Lifecycle

```
[no session]
    |
    | deploy action (creates deploying session — no deadline)
    v
[deploying: deployed_at set, deadline absent]
    |
    | activate-session (called by frontend when all services report ready)
    v
[active: deadline set, EventBridge schedule created]
    |
    | deadline reached (EventBridge fires auto-teardown)
    | OR manual teardown from frontend
    v
[tearing_down: tearing_down=true, teardown workflow dispatched]
    |
    | complete-teardown (called by teardown workflow at end)
    v
[no session]
```

## Troubleshooting

**Session stuck in `deploying` for over 30 minutes**
The session is auto-cleaned by the next `session-status` call. Stale deploying sessions older than 30 minutes are deleted automatically. If the deploy workflow failed, the session will also be cleared when `session-status` cross-checks the GitHub API and finds `conclusion: "failure"` or `"cancelled"`.

**Session stuck in `tearing_down` for over 15 minutes**
The stale `tearing_down` flag is auto-cleared by the next `session-status` call (15-minute timeout). If the teardown workflow finished but `complete-teardown` was never called, session-status also validates against the GitHub API and deletes the session when the workflow is no longer running.

**Auto-teardown fires but deploy is in progress**
The handler detects the in-progress deploy workflow and reschedules auto-teardown 5 minutes later. The session deadline is also updated in SSM so the frontend countdown remains accurate.

**`extend-session` returns 400 "Cannot extend beyond 2 hours remaining"**
The maximum allowed remaining time is 2 hours. Reduce current remaining time first by calling `shrink-session` (also unauthenticated), or wait for natural time to elapse.

**Function URL returns duplicate CORS headers**
CORS headers are intentionally absent from `get_response_headers()` in the handler code — they are injected solely by the Lambda Function URL configuration in Terraform. If duplicate headers appear, check that a middleware layer is not also adding CORS headers.

**`report-deploy-progress` returns 400 "Unknown service"**
The `service` field must be one of the 15 values in `DEPLOY_PROGRESS_SERVICES`: `kafka`, `redis`, `schema-registry`, `osrm`, `stream-processor`, `simulation`, `bronze-ingestion`, `airflow`, `trino`, `prometheus`, `grafana`, `loki`, `tempo`, `control-panel`, `performance-controller`.

## Related

- [auth-deploy/CONTEXT.md](auth-deploy/CONTEXT.md) — Architecture context for the auth-deploy function
- [infrastructure/terraform CONTEXT.md](../terraform/CONTEXT.md) — Terraform module that provisions the Lambda Function URL, EventBridge role, and secrets
