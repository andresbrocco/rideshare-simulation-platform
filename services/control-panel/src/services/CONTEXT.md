# CONTEXT.md — Services

## Purpose

Single-file HTTP client layer for the control panel frontend. All communication with the backend Lambda function flows through this module — authentication, deployment lifecycle, session management, teardown tracking, and service health checks.

## Responsibility Boundaries

- **Owns**: All fetch calls to the Lambda URL, request payload construction, runtime response validation, typed error classification
- **Delegates to**: The Lambda function (at `VITE_LAMBDA_URL`) to perform the actual operations; React hooks and components to interpret results
- **Does not handle**: State storage, polling schedules, UI feedback, or retry logic

## Key Concepts

All actions are sent as POST requests to a single Lambda endpoint, distinguished by an `action` string field in the payload. This single-endpoint dispatch pattern means the Lambda function acts as a router, not a REST API. The `callLambda` generic handles the full request-error-validation cycle; all exported functions are thin wrappers over it.

Runtime type guards (`isValidateResponse`, `isDeployResponse`, etc.) validate response shapes at runtime before TypeScript narrowing is applied. This is necessary because the Lambda response arrives as `unknown` JSON.

## Non-Obvious Details

- `control_panel` health is derived from `simulation_api` health — there is no independent health check for the control panel service itself. If `simulation_api` is down, both show as down.
- `getTeardownStatus` and `getDeployProgress` send no `api_key` field; they are unauthenticated actions on the Lambda.
- `VITE_LAMBDA_URL` must be set at build time (Vite inlines env vars). A missing URL throws `LambdaServiceError` with code `INVALID_RESPONSE`, not `NETWORK_ERROR`, which callers should handle distinctly.
- The `LambdaErrorCode` union (`NETWORK_ERROR` | `INVALID_RESPONSE` | `LAMBDA_ERROR`) maps to: transport failure, shape mismatch, and non-2xx HTTP status respectively.
