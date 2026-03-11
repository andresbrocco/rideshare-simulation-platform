# CONTEXT.md — Middleware

## Purpose

HTTP middleware layer for the simulation API. Provides two cross-cutting concerns applied to every request: security response headers and structured access logging with user identity resolution.

## Responsibility Boundaries

- **Owns**: Security header values and their policy strings; access log structure and the identity-resolution logic used exclusively for logging
- **Delegates to**: `api.session_store.get_session` for Redis-backed session lookups; `settings.get_settings()` for the static admin key value
- **Does not handle**: Authentication or authorization enforcement (that is handled by route-level `Depends(verify_api_key)`); WebSocket requests

## Key Concepts

- **Identity resolution for logging**: `RequestLoggerMiddleware` reads the `X-API-Key` header and maps it to a `(user_identity, user_role)` pair. Keys with a `sess_` prefix are looked up in Redis to retrieve email and role from the session store. The static admin key resolves to `("admin", "admin")`. Any other key or a lookup failure resolves to `("anonymous", "anonymous")`. This lookup is best-effort — exceptions are swallowed at DEBUG level so logging never fails a request.
- **Post-response identity resolution**: Identity resolution happens after `call_next` returns, meaning the response is already produced before the Redis lookup. The duration timer also starts before `call_next`, so it captures full round-trip time including route handler execution.

## Non-Obvious Details

- Health check paths (`/health`, `/health/detailed`) are explicitly skipped by `RequestLoggerMiddleware` to avoid log noise from orchestrator liveness probes.
- The CSP in `SecurityHeadersMiddleware` explicitly allows `ws:` and `wss:` under `connect-src` to support the simulation's WebSocket clients. Removing those directives would break browser WebSocket connections without any server-side error.
- HSTS (`max-age=31536000; includeSubDomains`) is applied unconditionally, including in local development over plain HTTP. Browsers that follow HSTS on localhost may require cache clearing if the service is later accessed without TLS.
- Access logs are emitted under logger name `api.access` (not the root `api` logger), allowing them to be routed or filtered independently in log aggregation.
