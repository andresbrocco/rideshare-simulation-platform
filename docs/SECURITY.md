# SECURITY.md

> Security-relevant facts for this codebase.

## Authentication

### Method

API key authentication. A single shared API key grants full access to the simulation REST API and WebSocket. There is no user account system, RBAC, or per-user differentiation.

### Implementation

- Module: `services/simulation/src/api/auth.py`
- Dependency: `FastAPI.Depends(verify_api_key)` applied to all protected routes
- Key source: `API_KEY` environment variable, loaded from Secrets Manager at container startup
- Settings class: `APISettings` in `services/simulation/src/settings.py` — fails startup if `API_KEY` is absent

### REST API

- Header: `X-API-Key: <key>`
- Validation: `verify_api_key()` in `src/api/auth.py` performs string equality check; returns HTTP 401 on mismatch, HTTP 500 if the server-side key is unconfigured
- Unauthenticated endpoints: `GET /health`, `GET /health/detailed` (intentionally unauthenticated for infrastructure probes)
- Auth validation endpoint: `GET /auth/validate` — used by the frontend login screen to confirm key validity

### WebSocket

- Header: `Sec-WebSocket-Protocol: apikey.<key>`
- Mechanism: Browsers cannot send custom HTTP headers during WebSocket upgrade; the API key is conveyed via the subprotocol header. The server echoes the subprotocol back on accept to satisfy the browser handshake.
- Module: `services/simulation/src/api/websocket.py`
- Rejection: `websocket.close(code=1008)` on invalid or missing key

### Lambda (auth-deploy)

- Module: `infrastructure/lambda/auth-deploy/`
- Mechanism: API key passed in the POST request body field `api_key`, validated against a secret stored in AWS Secrets Manager (`{project}/api-key`)
- Unauthenticated actions: `session-status`, `auto-teardown`, `service-health`, `teardown-status`, `get-deploy-progress` — these are callable without an API key to support frontend polling and EventBridge-triggered teardown

### Airflow

- Authentication: JWT auth (Airflow 3.x)
- JWT secret stored in `{project}/data-pipeline` Secrets Manager secret under key `JWT_SECRET`

### Grafana

- Authentication: HTTP Basic auth (username/password)
- Credentials stored in `{project}/monitoring` Secrets Manager secret

---

## Authorization

### Model

No role-based access control. Authentication is binary: a request either carries the valid API key or it does not. All authenticated callers have equivalent access to all simulation endpoints.

### Scope

The performance controller calls `PUT /simulation/speed` using the same API key, proxied through the simulation API's `/controller/` route prefix so the frontend does not expose the performance controller port directly.

### Lambda Actions

The Lambda function uses a hardcoded `NO_AUTH_ACTIONS` set to allow specific actions (status polling, EventBridge teardown trigger) without credentials. All other actions require a valid API key.

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

Applied to all HTTP responses by `SecurityHeadersMiddleware` in `services/simulation/src/api/middleware/security_headers.py`.

| Header | Value |
|--------|-------|
| `Content-Security-Policy` | `default-src 'self'; connect-src 'self' ws: wss:; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self'` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` |

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

### No Password Hashing

There is no user account system. The API key is a plain random string; comparison is done with string equality. No password hashing libraries (bcrypt, argon2, etc.) are used.

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

## Known Security Considerations

- **Single shared API key**: The simulation API key grants full access with no scope restrictions. All clients (Control Panel, Performance Controller, CI scripts) share the same key.
- **`/health` is unauthenticated**: The `GET /health` and `GET /health/detailed` endpoints are intentionally unauthenticated for Kubernetes probes and load balancer health checks.
- **Trino has no local auth**: Trino runs without authentication in local development. Production deployments are authenticated.
- **Prometheus has no auth**: The Prometheus HTTP API (port 9090) runs without authentication in both local and production environments.
- **Intentional data corruption**: The simulation supports `MALFORMED_EVENT_RATE` (float 0.0-1.0) that publishes additional corrupted event copies to exercise the Bronze DLQ pipeline. Disabled by default (0.0).
- **Public-only subnets (Production)**: The production VPC uses a public-subnet-only design with no NAT gateways; all EKS nodes have public IPs but are controlled by security groups.
- **ArgoCD `selfHeal: true`**: Manual `kubectl` changes to ArgoCD-managed resources are automatically reverted. The ArgoCD deployment watches the `deploy` branch.
- **Session time-boxing**: The Lambda auth-deploy function enforces a session deadline with auto-teardown via EventBridge Scheduler. A deploying session older than 30 minutes is auto-deleted (assumed failed). A tearing-down session older than 15 minutes is auto-deleted (assumed stale).
- **Frontend cookie scope**: The API key is carried in a cookie scoped to the parent domain (`ridesharing.portfolio.andresbrocco.com`) shared across the landing page and control-panel subdomains.
