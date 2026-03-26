# CONTEXT.md — auth-deploy

## Purpose

AWS Lambda function that serves as the control-plane backend for the portfolio platform's deploy/teardown UI. It authenticates requests against a stored API key, triggers GitHub Actions workflows for deploy and teardown, manages a time-bounded session with cost tracking, and reports real-time deploy/teardown progress to the frontend.

## Responsibility Boundaries

- **Owns**: API key validation, session lifecycle (SSM state), EventBridge Scheduler management, GitHub Actions workflow dispatch, deploy/teardown progress state, visitor account provisioning (two-phase), visitor credential storage (DynamoDB + KMS), welcome email dispatch (SES)
- **Delegates to**: GitHub Actions for the actual infrastructure deploy/teardown work; AWS Secrets Manager for credential storage; SSM Parameter Store for session persistence; EventBridge Scheduler for deadline-triggered auto-teardown; DynamoDB for durable visitor records; KMS for visitor password encryption; SES for welcome emails; Grafana/Airflow/MinIO/Simulation API for ephemeral service account creation (via provisioning sub-modules)
- **Does not handle**: CORS (handled by Lambda Function URL configuration in Terraform); infrastructure provisioning itself; service health recovery

## Key Concepts

**Session lifecycle**: A session has three phases stored in the SSM parameter `/rideshare/session/deadline`:
1. **Deploying** — `deployed_at` set, `deadline` absent. Created when deploy workflow is dispatched. No countdown yet.
2. **Active** — `deadline` set (after frontend calls `activate-session` once health checks pass). EventBridge schedule fires at the deadline.
3. **Tearing down** — `tearing_down: true` flag added. Set either by `auto-teardown` (EventBridge-triggered) or implicitly detected. Session is deleted by `complete-teardown` when the GitHub teardown workflow finishes.

**Dual invocation format**: The handler supports two event shapes. A Lambda Function URL invocation wraps the request in an HTTP envelope (event has `body` as a JSON string and `statusCode` in the response). A direct invocation (used by EventBridge Scheduler and local dev) passes the action/api_key as top-level event fields and receives the business response dict directly without an HTTP wrapper.

**Action authorization split**: Actions in `NO_AUTH_ACTIONS` (`session-status`, `auto-teardown`, `service-health`, `teardown-status`, `get-deploy-progress`, `provision-visitor`, `extend-session`, `shrink-session`) are callable without an API key, enabling the frontend status polling, the EventBridge auto-teardown trigger, and visitor self-registration to work without credentials.

**Two-phase visitor provisioning**: `provision-visitor` (Phase 1) is invoked directly from the visitor form before the platform is deployed. It stores the visitor record durably (KMS-encrypted password in DynamoDB) and sends the welcome email. Phase 2 (`reprovision-visitors`, authenticated) is called by the deploy workflow after all services are healthy — it scans DynamoDB, decrypts each password, and creates ephemeral accounts in Grafana, Airflow, MinIO, and the Simulation API.

**Visitor provisioning sub-modules**: `provision_grafana_viewer.py`, `provision_airflow_viewer.py`, `provision_minio_visitor.py`, and `provision_simulation_api_viewer.py` are co-located Python modules loaded at runtime via `_load_module`. Each exposes a single `provision_viewer` / `provision_visitor` function and is idempotent (create-or-update semantics).

**Visitor credential storage**: Each visitor record in DynamoDB (`rideshare-visitors` table) stores: email (partition key), display name, PBKDF2 password hash (for visitor login verification), KMS-encrypted plaintext password (for post-deploy service provisioning), provisioned service list, and consent timestamp. The KMS ciphertext enables the Lambda to decrypt and replay the password without storing it in plaintext.

**Teardown step mapping**: GitHub Actions job steps are grouped into 5 UI-level phases via `TEARDOWN_STEP_RANGES` index ranges. The handler maps raw job step statuses (step indices 0–10) to labeled UI steps shown in the frontend progress bar.

**Deploy progress tracking**: Each service in `DEPLOY_PROGRESS_SERVICES` reports its readiness via `report-deploy-progress`. Progress is stored as a dict inside the SSM session JSON. `all_ready` becomes true when all 15 services have `ready: true`.

## Non-Obvious Details

- **Session not deleted on teardown trigger**: When `auto-teardown` fires, it sets `tearing_down=True` but does NOT delete the SSM parameter. The session persists so the frontend can poll teardown progress. Cleanup only happens when the teardown workflow calls `complete-teardown`.
- **Stale state auto-cleanup**: Both `session-status` and `auto-teardown` have timeout guards. A `deploying` session older than 30 minutes is deleted (assumes failed deploy). A `tearing_down` session older than 15 minutes is deleted (assumes stale flag). Both also validate against GitHub API to detect failed workflows.
- **Auto-teardown defer on concurrent deploy**: If a deploy workflow is in_progress when the auto-teardown fires, it reschedules itself 5 minutes later rather than tearing down over a running deploy.
- **activate-session is idempotent**: Calling it when a deadline already exists returns the existing deadline without modification. This prevents countdown reset on double-click.
- **CORS not set in handler**: The `get_response_headers()` docstring explicitly notes that CORS headers are omitted because Lambda Function URLs handle them — adding them in code would cause browsers to reject duplicate header values.
- **`teardown_run_id` caching**: The first time `teardown-status` is polled it may not have a run ID, so it queries recent workflow runs and caches the resolved ID back into SSM to avoid repeated GitHub API calls on subsequent polls.
- **Secret format handling**: `get_secret` handles both plain string secrets and JSON-encoded secrets with either `API_KEY` or `GITHUB_PAT` keys, normalizing them to a plain string.
- **`extend-session` and `shrink-session` are unauthenticated**: Both actions are in `NO_AUTH_ACTIONS` so the frontend control panel can adjust the session timer without storing the admin API key in the browser. They enforce guards against going below 0 or above 2 hours remaining.
- **`provision-visitor` email failure returns 500 but visitor is stored**: If SES delivery fails after DynamoDB write succeeds, the response is `{"provisioned": true, "email_sent": false, ...}` with HTTP 500. The visitor record is durable — `reprovision-visitors` will recreate service accounts after deploy regardless of the email outcome.
- **Grafana admin password sourced from `rideshare/core` secret**: That secret is JSON-encoded; the handler extracts `GRAFANA_ADMIN_PASSWORD`. Airflow and MinIO credentials come from `rideshare/data-pipeline` (JSON with `AIRFLOW_ADMIN_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`). Simulation API uses the platform `rideshare/api-key`.
- **`minio-visitor-readonly.json` policy bundled in Lambda zip**: The MinIO provisioner looks for the policy file co-located with the module first, then falls back to `infrastructure/policies/`. Ensure the file is present when packaging the Lambda archive.

## Related Modules

- [infrastructure/terraform](../../terraform/CONTEXT.md) — Reverse dependency — Provides vpc_id, public_subnet_ids, eks_cluster_role_arn (+13 more)
- [infrastructure/terraform/foundation](../../terraform/foundation/CONTEXT.md) — Reverse dependency — Provides vpc_id, public_subnet_ids, eks_nodes_sg_id (+22 more)
