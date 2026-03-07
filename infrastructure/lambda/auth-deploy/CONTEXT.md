# CONTEXT.md — auth-deploy

## Purpose

AWS Lambda function that serves as the control-plane backend for the portfolio platform's deploy/teardown UI. It authenticates requests against a stored API key, triggers GitHub Actions workflows for deploy and teardown, manages a time-bounded session with cost tracking, and reports real-time deploy/teardown progress to the frontend.

## Responsibility Boundaries

- **Owns**: API key validation, session lifecycle (SSM state), EventBridge Scheduler management, GitHub Actions workflow dispatch, deploy/teardown progress state
- **Delegates to**: GitHub Actions for the actual infrastructure deploy/teardown work; AWS Secrets Manager for credential storage; SSM Parameter Store for session persistence; EventBridge Scheduler for deadline-triggered auto-teardown
- **Does not handle**: CORS (handled by Lambda Function URL configuration in Terraform); infrastructure provisioning itself; service health recovery

## Key Concepts

**Session lifecycle**: A session has three phases stored in the SSM parameter `/rideshare/session/deadline`:
1. **Deploying** — `deployed_at` set, `deadline` absent. Created when deploy workflow is dispatched. No countdown yet.
2. **Active** — `deadline` set (after frontend calls `activate-session` once health checks pass). EventBridge schedule fires at the deadline.
3. **Tearing down** — `tearing_down: true` flag added. Set either by `auto-teardown` (EventBridge-triggered) or implicitly detected. Session is deleted by `complete-teardown` when the GitHub teardown workflow finishes.

**Dual invocation format**: The handler supports two event shapes. A Lambda Function URL invocation wraps the request in an HTTP envelope (event has `body` as a JSON string and `statusCode` in the response). A direct invocation (used by EventBridge Scheduler and local dev) passes the action/api_key as top-level event fields and receives the business response dict directly without an HTTP wrapper.

**Action authorization split**: Actions in `NO_AUTH_ACTIONS` (`session-status`, `auto-teardown`, `service-health`, `teardown-status`, `get-deploy-progress`) are callable without an API key, enabling the frontend status polling and the EventBridge auto-teardown trigger to work without credentials.

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

## Related Modules

- [infrastructure/terraform](../../terraform/CONTEXT.md) — Reverse dependency — Provides vpc_id, public_subnet_ids, eks_cluster_role_arn (+13 more)
- [infrastructure/terraform/foundation](../../terraform/foundation/CONTEXT.md) — Reverse dependency — Provides vpc_id, public_subnet_ids, eks_nodes_sg_id (+22 more)
