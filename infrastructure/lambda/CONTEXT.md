# CONTEXT.md — Lambda

## Purpose

AWS Lambda functions that serve as the serverless control plane for portfolio platform lifecycle management. The primary function (`auth-deploy`) gates deploy and teardown operations behind API key authentication, manages a session state machine that tracks platform cost and uptime, and bridges the frontend control panel to GitHub Actions workflows.

## Responsibility Boundaries

- **Owns**: API key validation, session lifecycle (deploying → active → tearing_down → gone), EventBridge auto-teardown scheduling, GitHub Actions workflow dispatch and status polling, deploy progress aggregation, service health checks
- **Delegates to**: GitHub Actions workflows (actual Terraform deploy/teardown), SSM Parameter Store (session state persistence), EventBridge Scheduler (auto-teardown timing), AWS Secrets Manager (credentials)
- **Does not handle**: Infrastructure provisioning, Kubernetes operations, application-level health beyond HTTP endpoint reachability

## Key Concepts

**Session lifecycle**: Platform uptime is tracked as a session in SSM Parameter Store (`/rideshare/session/deadline`). A session passes through distinct states: deploying (no deadline yet), active (countdown running), tearing_down (teardown workflow in flight). The `deployed_at` timestamp is always present; `deadline` is added only after `activate-session` is called by the frontend once health checks pass.

**Two-phase session activation**: Deploy workflow creates a deploying session immediately (no deadline). The frontend polls `get-deploy-progress` until all services report ready, then calls `activate-session` to set the first deadline and start the cost countdown. This avoids charging time against deploy duration.

**Auto-teardown via EventBridge**: Each session stores a deadline enforced by an EventBridge one-time schedule that invokes the Lambda itself with `{"action": "auto-teardown"}`. The schedule is upserted (create-or-update) on every deadline change so extend/shrink operations correctly reschedule the teardown. If a deploy workflow is running when the timer fires, teardown is rescheduled 5 minutes later to avoid tearing down mid-deploy.

**Session as the source of truth**: Stale session states (deploying session older than 30 min, tearing_down flag older than 15 min) are auto-cleaned by the `session-status` handler. The handler also cross-checks GitHub API to clear sessions whose underlying workflow has failed or completed unexpectedly.

**Deploy progress aggregation**: The deploy workflow reports each service's readiness via `report-deploy-progress`. Progress is stored as `deploy_progress` inside the SSM session JSON, making SSM the single store for both session metadata and per-service readiness.

**Dual invocation modes**: The handler supports two event formats — Function URL (HTTP envelope with `body` as JSON string, returns `statusCode`/`headers`/`body`) and direct invocation (action fields at the top level, returns the business response dict directly). Direct invocation is used by LocalStack during local development.

## Non-Obvious Details

- CORS headers are intentionally absent from the Lambda response — they are injected by the Lambda Function URL configuration in Terraform. Adding them in code would duplicate headers and cause browser rejections.
- `SESSION_STEP_MINUTES = 15`: sessions extend and shrink in fixed 15-minute increments; the maximum remaining time is capped at 2 hours. Shrinking to exactly 0 is allowed; shrinking below 0 is rejected.
- Cost tracking uses a hardcoded `PLATFORM_COST_PER_HOUR = 0.31` (1x t3.xlarge). The `cost_so_far` field is computed on every `session-status` call from `elapsed_seconds`, not stored in SSM.
- Teardown step-to-UI-label mapping uses `TEARDOWN_STEP_RANGES` to group raw GitHub Actions job steps (by index) into five labelled UI steps. The teardown run ID is cached in the SSM session after the first GitHub API lookup to reduce redundant calls.
- The `auto-teardown`, `session-status`, `service-health`, `teardown-status`, and `get-deploy-progress` actions require no API key — they are publicly readable so the frontend can poll without exposing credentials.
- Service health checks run in parallel via `ThreadPoolExecutor` against hardcoded production HTTPS endpoints. These checks are frontend-facing (confirming all services are up post-deploy) and are separate from Kubernetes liveness probes.
