# SECURITY.md

> Security-relevant facts for this codebase.

## Authentication

### Method

API key authentication with two tiers. A static shared admin key grants full access to the simulation REST API and WebSocket. Visitor accounts authenticate via email/password (`POST /auth/login`) and receive short-lived `sess_`-prefixed session keys with `viewer` role (read-only). The Lambda auth-deploy function uses a separate admin API key stored in AWS Secrets Manager for deploy/teardown operations.

### Implementation

- Module: `services/simulation/src/api/auth.py`
- Dependency: `FastAPI.Depends(verify_api_key)` applied to all protected routes
- Key source: `API_KEY` environment variable, loaded from Secrets Manager at container startup
- Settings class: `APISettings` in `services/simulation/src/settings.py` — fails startup if `API_KEY` is absent

### REST API

- Header: `X-API-Key: <key>`
- Validation: `verify_api_key()` in `src/api/auth.py` accepts two key forms:
  1. Keys prefixed `sess_` — looked up in Redis via `session_store.get_session`; carry `role` and `email` from the stored session record
  2. All other keys — compared against the static admin key from settings; receive `role="admin"`
- Returns `AuthContext` (frozen dataclass with `role` and `email`) rather than a raw string; downstream dependencies receive this for RBAC decisions
- HTTP 401 on invalid key; HTTP 500 if the server-side key is unconfigured
- Unauthenticated endpoints: `GET /health`, `GET /health/detailed` (intentionally unauthenticated for infrastructure probes)
- Auth endpoints:
  - `POST /auth/login` — validates email/password against the in-memory `UserStore` (bcrypt), creates a Redis session via `session_store`, returns `{api_key, role, email}`; rate-limited to 10/minute
  - `POST /auth/register` — admin-gated; provisions new `viewer`-role accounts (or updates passwords on existing accounts); rate-limited to 20/minute; called by the Lambda visitor provisioning orchestrator
  - `GET /auth/validate` — tests a key without side effects

### WebSocket

- Header: `Sec-WebSocket-Protocol: apikey.<key>`
- Mechanism: Browsers cannot send custom HTTP headers during WebSocket upgrade; the API key is conveyed via the subprotocol header. The server echoes the subprotocol back on accept to satisfy the browser handshake.
- Both static admin keys and `sess_`-prefixed session keys are accepted via `_is_valid_key`
- Module: `services/simulation/src/api/websocket.py`
- Rejection: `websocket.close(code=1008)` on invalid or missing key

### Lambda (auth-deploy)

- Module: `services/auth-deploy/`
- Mechanism: API key passed in the POST request body field `api_key`, validated against a secret stored in AWS Secrets Manager (`{project}/api-key`)
- Unauthenticated actions (`NO_AUTH_ACTIONS`): `session-status`, `auto-teardown`, `service-health`, `teardown-status`, `get-deploy-progress`, `provision-visitor`, `extend-session`, `shrink-session` — callable without an API key to support frontend polling, EventBridge-triggered teardown, visitor self-registration, and session timer adjustments from the control panel

### Airflow

- Authentication: JWT auth (Airflow 3.x)
- JWT secret stored in `{project}/data-pipeline` Secrets Manager secret under key `JWT_SECRET`

### Grafana

- Authentication: HTTP Basic auth (username/password)
- Credentials stored in `{project}/monitoring` Secrets Manager secret

---

## Authorization

### Model

Two roles exist: `admin` and `viewer`. Role is carried in the `AuthContext` returned by `verify_api_key`.

- **`admin`**: the static admin key always resolves to this role. Full access to all endpoints.
- **`viewer`**: session keys provisioned via `POST /auth/login` for visitor accounts carry `role="viewer"`. Read-only access — mutation endpoints (start/pause/resume/stop/reset simulation, set speed, create agents, puppet transitions, register users) are guarded by `require_admin` (`Depends(require_admin)`) which raises HTTP 403 when `role != "admin"`.

### Scope

The performance controller calls `PUT /simulation/speed` using the same admin API key, proxied through the simulation API's `/controller/` route prefix so the frontend does not expose the performance controller port directly.

### Lambda Actions

The Lambda function uses a hardcoded `NO_AUTH_ACTIONS` set (see Authentication → Lambda section) to allow unauthenticated access. All other actions require a valid API key.

### IAM (Production)

- All workload IAM roles use EKS Pod Identity, not IRSA
- Trust policies target `pods.eks.amazonaws.com` with `sts:AssumeRole` and `sts:TagSession`
- Pod Identity associations are declared in `infrastructure/terraform/platform/main.tf`
- Secrets Manager access is scoped to `{project_name}/*` prefix (not account-wide)
- GitHub Actions uses OIDC (not static access keys); trust is scoped to a specific org/repo/branch via `StringLike` on the `sub` claim
- Module: `infrastructure/terraform/foundation/modules/iam/`

---

## Input Validation

### Library

Pydantic v2 (`pydantic>=2.12.5`, `pydantic-settings>=2.7.1`) for all Python services. JSON Schema (`jsonschema>=4.25.1`) for Kafka event validation.

### Approach

- All REST API request bodies are Pydantic models defined in `services/simulation/src/api/models/`
- All settings classes are Pydantic `BaseSettings` subclasses with field constraints (`ge`, `le`, `Literal`) — service startup fails if required credentials or out-of-range values are provided
- Kafka events are validated against JSON Schema Draft 2020-12 files in `schemas/kafka/` via Schema Registry at publish time; validation failure is non-fatal (logged as warning) to avoid halting the simulation
- WebSocket input from connected clients (`websocket.receive_text()`) is not processed as commands — the WebSocket is one-way (server to client)

### Locations

- REST API validation: `services/simulation/src/api/models/` (Pydantic)
- Settings validation: `services/simulation/src/settings.py` (Pydantic BaseSettings)
- Kafka event schema: `schemas/kafka/*.json` + Schema Registry
- Bronze ingestion DLQ: `services/bronze-ingestion/src/` validates events against `schemas/kafka/` JSON Schemas; malformed messages are routed to per-topic DLQ Delta tables rather than discarded

---

## Rate Limiting

### Implementation

- Library: `slowapi>=0.1.9` (wraps `limits` library)
- Module: `services/simulation/src/api/rate_limit.py`
- Key function: API key if present, falls back to client IP address
- Exceeded response: HTTP 429 with `Retry-After` header; tracked via OTel counter `api_rate_limit_hits_total`

### WebSocket

- Module: `WebSocketRateLimiter` in `services/simulation/src/api/rate_limit.py`
- Limit: 5 connections per 60-second sliding window, keyed by API key
- Rejection: `websocket.close(code=1008)`

---

## Security Headers

Applied to all HTTP responses by `SecurityHeadersMiddleware` in `services/simulation/src/api/middleware/`. A second middleware (`RequestLoggerMiddleware`) also runs on all requests and emits structured access log entries under logger `api.access` — see Audit Logging section below.

| Header | Value |
|--------|-------|
| `Content-Security-Policy` | `default-src 'self'; connect-src 'self' ws: wss:; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self'` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` |

### Access Log Identity Resolution

`RequestLoggerMiddleware` resolves caller identity for structured HTTP audit logs:

- `X-API-Key` header with `sess_` prefix: Redis lookup via `session_store.get_session` to retrieve email and role
- Static admin key: resolves to `("admin", "admin")`
- Any other value or lookup failure: resolves to `("anonymous", "anonymous")`
- Health check paths (`/health`, `/health/detailed`) are skipped to suppress probe noise
- Identity resolution is best-effort; exceptions are swallowed at DEBUG level so logging never fails a request
- Log fields: `user_identity`, `user_role`, `method`, `path`, `status_code`, `duration_ms` (emitted as top-level JSON keys by `JSONFormatter`)

### CORS

- Middleware: FastAPI `CORSMiddleware`
- Allowed origins: configured via `CORS_ORIGINS` environment variable (comma-separated); defaults to `http://localhost:5173,http://localhost:3000` for local development
- Settings class: `CORSSettings` in `services/simulation/src/settings.py`

### TLS (Production)

- CloudFront enforces `TLSv1.2_2021` minimum protocol version
- ACM certificate provisioned in `us-east-1` via `infrastructure/terraform/foundation/modules/acm/`
- Origin Access Control (OAC) restricts S3 bucket access to CloudFront only (SigV4 signed requests)
- Module: `infrastructure/terraform/foundation/modules/cloudfront/`

---

## Secrets Management

### Storage

| Environment | Backend |
|-------------|---------|
| Local development | LocalStack Secrets Manager (emulated AWS) |
| Production | AWS Secrets Manager |

Credentials are never hardcoded in `.env` files. No static AWS credentials are committed to the repository.

### Bootstrap Flow (Local Development)

1. `localstack` container starts
2. `secrets-init` runs `infrastructure/scripts/seed-secrets.py` to populate secrets in LocalStack
3. `fetch-secrets.py` reads secrets and writes grouped `.env` files to a shared Docker volume at `/secrets/`
4. All other services mount `/secrets/` read-only and source `core.env`, `data-pipeline.env`, or `monitoring.env` in their entrypoints

### Bootstrap Flow (Production)

- External Secrets Operator (ESO) reads from AWS Secrets Manager and syncs to Kubernetes Secrets
- `SecretStore` uses the EKS node IAM role (not Pod Identity) to avoid a circular dependency during cluster bootstrap
- `ExternalSecret` CRDs: `external-secrets-api-keys.yaml`, `external-secrets-app-credentials.yaml`
- Module: `infrastructure/kubernetes/manifests/`

### Secret Groups

| Secret Name | Purpose | Keys |
|-------------|---------|------|
| `{project}/api-key` | Simulation service API key | `API_KEY` |
| `{project}/core` | Kafka and Redis credentials | `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD`, `REDIS_PASSWORD`, `SCHEMA_REGISTRY_USER`, `SCHEMA_REGISTRY_PASSWORD` |
| `{project}/data-pipeline` | MinIO, PostgreSQL, Airflow internal secrets | `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `POSTGRES_AIRFLOW_USER`, `POSTGRES_AIRFLOW_PASSWORD`, `POSTGRES_METASTORE_USER`, `POSTGRES_METASTORE_PASSWORD`, `FERNET_KEY`, `INTERNAL_API_SECRET_KEY`, `JWT_SECRET`, `API_SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` |
| `{project}/monitoring` | Grafana admin credentials | `ADMIN_USER`, `ADMIN_PASSWORD` |
| `{project}/rds` | RDS master credentials and endpoint | `PASSWORD`, `USERNAME`, `ENDPOINT` |
| `{project}/github-pat` | GitHub PAT for workflow dispatch | `GITHUB_PAT` |

Terraform-generated production credentials: API key uses 32-character random string; all other passwords use configurable `password_length` (default 16). Module: `infrastructure/terraform/foundation/modules/secrets_manager/`.

### Visitor Credential Storage (Lambda)

Visitor records stored in the DynamoDB `rideshare-visitors` table contain:
- Email (partition key), display name, consent timestamp
- KMS-encrypted plaintext password — enables the Lambda to decrypt and replay the password after platform deploy without ever storing it in plaintext; KMS key ARN is in `infrastructure/terraform/foundation/`
- List of provisioned services — used by Phase 2 (`reprovision-visitors`) to determine which service accounts to (re)create

If SES email delivery fails after DynamoDB write succeeds, the visitor record is still durable and `reprovision-visitors` will recreate service accounts after the next deploy.

### Individual Secret Override (Dev)

`seed-secrets.py` supports `OVERRIDE_<KEY>` environment variables to replace default local values (e.g., `OVERRIDE_API_KEY=mykey`) without modifying the script.

### GitHub PAT

The `{project}/github-pat` secret is seeded with a placeholder value on first Terraform apply. The `ignore_changes` lifecycle rule prevents Terraform from overwriting a real token set out-of-band. The real token must be set manually after initial provisioning.

---

## PII Handling

### Masking in Logs

- Module: `services/simulation/src/sim_logging/`
- `PIIFilter` is applied at the log handler level (intercepts all records regardless of origin)
- Email addresses are masked to `[EMAIL]`
- Phone numbers are masked to `[PHONE]`
- Masking applies only to `str`-type log messages; structured fields (formatted arguments, JSON objects) are not scanned

### PII in Kafka Events

Profile schemas (`driver_profile_event`, `rider_profile_event`) carry PII fields (name, email, phone, home_location). These are synthetic values generated by the `Faker` library for the simulation. Schema definitions are in `schemas/kafka/`.

---

## Kafka Security

### Authentication

- Protocol: SASL/PLAIN
- Applied in both local (via LocalStack-seeded credentials) and production environments
- Credentials: `KAFKA_SASL_USERNAME` / `KAFKA_SASL_PASSWORD` from Secrets Manager
- Local JAAS config written dynamically at container startup via shell `printf` to `/tmp/kafka_jaas.conf`

### Schema Registry

- Authentication: HTTP BASIC auth (`SCHEMA_REGISTRY_AUTHENTICATION_METHOD: BASIC`)
- Credentials from a mounted `users.properties` file injected from Secrets Manager
- JSON Schema Draft 2020-12 enforcement for all 8 application topics

---

## Cryptography

### Password Hashing

- **Simulation API user accounts**: Visitor passwords are hashed using `bcrypt` and stored in the in-memory `UserStore` (`services/simulation/src/api/user_store.py`). The bcrypt hash is used for `POST /auth/login` credential verification. The static admin API key is not password-hashed — comparison is done with string equality.
- **KMS envelope encryption**: Visitor plaintext passwords are encrypted with a KMS key before storage in DynamoDB. `Encrypt`/`Decrypt`/`GenerateDataKey` permissions are granted to the Lambda execution role.

### Airflow Fernet Key

- Purpose: Encrypts connection passwords stored in the Airflow metadata database
- Format: 32-byte URL-safe base64 string
- Generated by Terraform using `random_bytes` (not `random_password`) for correct format
- Stored in `{project}/data-pipeline` Secrets Manager secret under key `FERNET_KEY`

### TLS

- All production traffic served via HTTPS (CloudFront + ACM, minimum TLSv1.2_2021)
- Simulation API HSTS header: `max-age=31536000; includeSubDomains`

---

## Default Credentials (Local Development)

All services use simplified credentials for local development seeded by `infrastructure/scripts/seed-secrets.py`. These defaults must not be used in production.

| Service | Default Value |
|---------|--------------|
| API key | `admin` |
| Kafka SASL username/password | `admin` / `admin` |
| Redis password | `admin` |
| Schema Registry | `admin` / `admin` |
| MinIO root user/password | `admin` / `adminadmin` |
| PostgreSQL (Airflow) | `admin` / `admin` |
| PostgreSQL (Metastore) | `admin` / `admin` |
| Grafana admin | `admin` / `admin` |
| Airflow admin | `admin` / `admin` |
| GitHub PAT | placeholder — must be replaced |

Production credentials are randomly generated by Terraform at `apply` time and stored only in AWS Secrets Manager and Terraform state.

---

## Audit Logging

### Simulation API Access Logs

`RequestLoggerMiddleware` emits one structured log record per request under logger `api.access`. Fields promoted to top-level JSON keys by `JSONFormatter`: `method`, `path`, `status_code`, `duration_ms`, `user_identity`, `user_role`. Logs are shipped to Loki via the OTel Collector.

### Grafana Audit Events

- Enabled via `GF_AUDIT_ENABLED=true` on the Grafana container
- Audit events appear in the Grafana container log stream and are queryable in Loki (`{container="rideshare-grafana"} |= "action="`)
- If `GF_AUDIT_ENABLED` is absent, the Loki panel in the visitor-activity dashboard returns no results silently

### Trino Query Audit

- `event-listener.properties` configures the `query-event-listener` plugin
- Completed queries are logged to Trino's standard log output (`QueryCompletedEvent`) and collected by Loki
- In-flight queries are not captured; only completed queries appear in the audit trail

### MinIO Audit Events

- Enabled via `MINIO_AUDIT_CONSOLE_ENABLE=on` on the MinIO container
- Audit events are collected by Loki under the MinIO container label
- If this flag is absent, the MinIO panel in the visitor-activity dashboard returns no results silently

### Admin Visitor Activity Dashboard

An admin-only Grafana dashboard (`services/grafana/dashboards/admin/visitor-activity.json`) aggregates per-service last-access timestamps across Airflow (via `airflow-postgres` Postgres datasource querying `ab_user`), Grafana (Loki), Simulation API (Loki + `api.access`), Trino (Loki + `QueryCompletedEvent`), and MinIO (Loki). Dashboard is provisioned into the `Admin` folder in Grafana (not visible to viewer-role users).

---

## Known Security Considerations

- **`/health` is unauthenticated**: The `GET /health` and `GET /health/detailed` endpoints are intentionally unauthenticated for Kubernetes probes and load balancer health checks.
- **Trino uses header-based identity**: Trino identifies callers via the `X-Trino-User` header with no password authentication. Access control is enforced by file-based catalog ACL (`rules.json`) — `admin` has full access; all other users are read-only on `delta` and blocked from `system`. Rules reload every 60 seconds.
- **Prometheus has no auth**: The Prometheus HTTP API (port 9090) runs without authentication in both local and production environments.
- **Intentional data corruption**: The simulation supports `MALFORMED_EVENT_RATE` (float 0.0-1.0) that publishes additional corrupted event copies to exercise the Bronze DLQ pipeline. Disabled by default (0.0).
- **Public-only subnets (Production)**: The production VPC uses a public-subnet-only design with no NAT gateways; all EKS nodes have public IPs but are controlled by security groups.
- **ArgoCD `selfHeal: true`**: Manual `kubectl` changes to ArgoCD-managed resources are automatically reverted. The ArgoCD deployment watches the `deploy` branch.
- **Session time-boxing**: The Lambda auth-deploy function enforces a session deadline with auto-teardown via EventBridge Scheduler. A deploying session older than 30 minutes is auto-deleted (assumed failed). A tearing-down session older than 15 minutes is auto-deleted (assumed stale).
- **Frontend cookie scope**: The admin API key is carried in a cookie scoped to the parent domain (`ridesharing.portfolio.andresbrocco.com`) shared across the landing page and control-panel subdomains. The control-panel page consumes the cookie exactly once on mount, migrates the key into `sessionStorage`, and then clears the cookie. Visitor accounts do not use the cookie path — they authenticate via `POST /auth/login` and store the session key in `sessionStorage` directly.
- **Session-based viewer keys**: Session keys returned by `POST /auth/login` carry a `sess_` prefix and are persisted as Redis hashes at `session:{api_key}` with TTL-based auto-eviction. Explicit invalidation is provided by `delete_session`. The static admin key bypasses Redis entirely and is never stored in the session store.
- **`LoginDialog` replaces raw API key entry for visitors**: The frontend `LoginDialog` calls `POST /auth/login` with `{email, password}` and receives a session key. Visitors never interact with the raw simulation API key.
- **Single shared API key**: The simulation API admin key grants full access with no scope restrictions. All admin callers (Control Panel admin mode, Performance Controller, CI scripts) share the same key. Viewer-role visitors receive scoped session keys.
- **Trino `rules.json` changes take up to 60 seconds**: The file-based access control rules reload every 60 seconds. A brief window exists after modifying `rules.json` before the change takes effect; a container restart applies the change immediately.
- **IMDS hop limit of 2 on EKS nodes**: The EKS launch template sets `http_put_response_hop_limit = 2` (not the IMDSv2-hardened default of 1) to allow containers inside pods to reach the instance metadata service. Checkov rule `CKV_AWS_341` is explicitly skipped with this justification.
