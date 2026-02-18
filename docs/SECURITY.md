# SECURITY.md

> Security-relevant facts for this codebase.

## Authentication

How users and services authenticate to the platform.

### REST API Authentication

**Method**: API key authentication via HTTP headers

**Implementation**:
- Module: `services/simulation/src/api/auth.py`
- Function: `verify_api_key()` validates `X-API-Key` header
- Key storage: Environment variable `API_KEY` (injected from LocalStack Secrets Manager)
- Key validation: Direct string comparison against configured key

**Protected Endpoints**:
- `/simulation/*` - Simulation control commands
- `/agents/*` - Agent management and puppet mode
- `/puppet/*` - Puppet agent controls
- `/metrics/*` - Metrics snapshots

**Unprotected Endpoints**:
- `/health` - Basic health check (for container orchestration)
- `/health/detailed` - Detailed service health with latency metrics

**Login Validation**:
- Endpoint: `GET /auth/validate`
- Frontend: `services/frontend/src/components/LoginScreen.tsx`
- Key storage: `sessionStorage` (browser)
- Response: 200 if valid, 401 if invalid

### WebSocket Authentication

**Method**: API key via WebSocket subprotocol header

**Implementation**:
- Module: `services/simulation/src/api/websocket.py`
- Header: `Sec-WebSocket-Protocol: apikey.<key>`
- Validation: Extracts key from protocol string, validates against `API_KEY`
- Rejection: WebSocket close with code 1008 (policy violation)

### Service-to-Service Authentication

**Kafka (SASL/PLAIN)**:
- Security protocol: `SASL_PLAINTEXT` (local), `SASL_SSL` (production)
- Credentials: `KAFKA_SASL_USERNAME` / `KAFKA_SASL_PASSWORD`
- Module: `services/simulation/src/settings.py` (KafkaSettings)

**Redis (AUTH)**:
- Authentication: Password-based via `AUTH` command
- Credential: `REDIS_PASSWORD`
- Module: `services/simulation/src/settings.py` (RedisSettings)

**Schema Registry (Basic Auth)**:
- Authentication: HTTP Basic Auth
- Credential: `KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO` (format: `username:password`)
- Module: `services/simulation/src/kafka/schema_registry.py`

**Trino (No Auth)**:
- Authentication: None (local development)
- Production: LDAP via OpenLDAP service (optional `spark-testing` profile)

**LDAP (Spark Thrift Server)**:
- Service: OpenLDAP on port 389
- User: `cn=admin,ou=users,dc=rideshare,dc=local`
- Credentials: `LDAP_USERNAME` / `LDAP_PASSWORD`
- Purpose: Authenticate DBT connections to Spark Thrift Server
- Module: `services/openldap/`
- TLS: Disabled in local development (`LDAP_TLS=false`)

### Default Development Credentials

**All Passwords**: `admin` (username: `admin` where applicable)

**API Key**: `admin`

**Purpose**: Self-documenting development credentials, intentionally simple for local testing.

**Production Migration**: Generate secure keys with `openssl rand -hex 32` and store in AWS Secrets Manager.

## Authorization

How permissions are enforced.

### Model

**Simple API Key Authorization**: Single shared secret grants full access to all protected endpoints. No role-based access control (RBAC) or user differentiation.

### Implementation

**Middleware**: FastAPI dependency injection via `Depends(verify_api_key)`
- Applied to route handlers requiring authentication
- Raises `HTTPException(401)` for invalid keys
- No authorization (permission) checks beyond authentication

**Rate Limiting**:
- Module: `services/simulation/src/api/rate_limit.py`
- Library: `slowapi`
- Strategy: Per API key or per IP address
- Limits: Configurable per endpoint (e.g., `@limiter.limit("10/minute")`)
- WebSocket: Sliding window limiter (5 connections per 60 seconds per client)
- Tracking: OpenTelemetry counter for rate limit violations

### Roles

None. All authenticated clients have identical permissions.

## Input Validation

How input is validated across services.

### Primary Library

**Pydantic v2.12.5**

**Approach**:
- All API request/response models use Pydantic data classes
- Automatic validation on FastAPI route handlers
- Settings loaded from environment variables with validation
- DNA models validate behavioral parameters at agent creation

### Validation Locations

**API Layer** (`services/simulation/src/api/models/`):
- `agents.py` - Agent creation requests
- `simulation.py` - Simulation control commands
- `puppet.py` - Puppet mode controls
- `metrics.py` - Metrics snapshots
- `health.py` - Health check responses

**Settings** (`services/simulation/src/settings.py`):
- Environment variable validation with `pydantic-settings`
- Type coercion and constraint validation (e.g., `ge=1, le=1024` for speed multiplier)
- Credential presence validation (raises `ValueError` if missing)

**Events** (`services/simulation/src/events/schemas.py`):
- JSON schema validation for Kafka events
- Schema Registry integration for distributed validation
- Event factory validation before publishing

**Agent DNA** (`services/simulation/src/agents/dna.py`):
- Immutable behavioral parameters validated at creation
- Constraints on acceptance rates, patience thresholds, service quality

**Database Models** (`services/simulation/src/db/`):
- SQLAlchemy ORM with type annotations
- Foreign key constraints, unique constraints

**Frontend** (TypeScript):
- Types generated from OpenAPI schema via `openapi-typescript`
- Runtime validation on API responses

### Schema Registry Integration

**Purpose**: Enforce event schema contracts across Kafka producers/consumers

**Location**: `schemas/kafka/*.json`

**Validation**: JSON Schema Draft 7

**Module**: `services/simulation/src/kafka/schema_registry.py`

**Process**:
1. Producer fetches latest schema from registry
2. Validates event against schema before publishing
3. Consumer validates incoming messages
4. Schema evolution tracked in registry

## Secrets Management

How secrets are handled across environments.

### Storage

**LocalStack Secrets Manager** (Development):
- Endpoint: `http://localstack:4566` (Docker) or `http://localhost:4566` (local)
- Region: `us-east-1`
- Namespace: `rideshare/*`
- 4 secret groups (api-key, core, data-pipeline, monitoring)

**AWS Secrets Manager** (Production):
- Same secret structure as LocalStack
- Migration: Change `AWS_ENDPOINT_URL` from LocalStack to AWS endpoint
- No code changes required

### Secret Groups

| Secret Name | Keys | Used By |
|-------------|------|---------|
| `rideshare/api-key` | API_KEY | simulation, frontend |
| `rideshare/core` | KAFKA_SASL_USERNAME, KAFKA_SASL_PASSWORD, REDIS_PASSWORD, SCHEMA_REGISTRY_USER, SCHEMA_REGISTRY_PASSWORD | kafka, redis, simulation, stream-processor, bronze-ingestion |
| `rideshare/data-pipeline` | MINIO_ROOT_USER, MINIO_ROOT_PASSWORD, POSTGRES_AIRFLOW_USER, POSTGRES_AIRFLOW_PASSWORD, POSTGRES_METASTORE_USER, POSTGRES_METASTORE_PASSWORD, FERNET_KEY, INTERNAL_API_SECRET_KEY, JWT_SECRET, API_SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD, HIVE_LDAP_USERNAME, HIVE_LDAP_PASSWORD, LDAP_ADMIN_PASSWORD, LDAP_CONFIG_PASSWORD | minio, airflow, postgres-*, hive-metastore, openldap |
| `rideshare/monitoring` | ADMIN_USER, ADMIN_PASSWORD | grafana |

### Access Pattern

**Docker Compose**:
1. `secrets-init` service runs on startup
2. Seeds LocalStack Secrets Manager with all credentials
3. Fetches secrets and writes to `/secrets/` shared volume
4. Services source credentials from `/secrets/*.env` files (core.env, data-pipeline.env, monitoring.env)

**Kubernetes**:
1. External Secrets Operator (ESO) syncs secrets from LocalStack/AWS Secrets Manager
2. Creates Kubernetes Secrets in cluster
3. Pods reference secrets via `secretKeyRef` in environment variables

**Script**: `infrastructure/scripts/seed-secrets.py` - Idempotent seeding script

**Fetch Script**: `infrastructure/scripts/fetch-secrets.py` - Retrieves secrets for local development

### Security Practices

**Never Logged**: Secrets are never logged or printed to stdout
- Settings classes use `model_config` with no repr for sensitive fields
- Log formatters do not expose environment variables

**Never Committed**: `.gitignore` excludes `.env.local`, `/secrets/`, and other credential files

**Validation**: Pydantic validators ensure required secrets are present at startup (raises `ValueError` if missing)

**Rotation**: Airflow uses deterministic Fernet keys for local development (base64-encoded "admin-dev-fernet-key-00000000")

**Override Support**: `OVERRIDE_<KEY>` environment variables allow per-secret overrides during seeding

## Cryptography

Cryptographic operations used in the system.

### Password Hashing

**None**: This is a development/portfolio platform with synthetic data. No user passwords are hashed.

**Airflow Fernet Key**: Used for encrypting connection strings and variables in Airflow metadata database.
- Algorithm: Fernet (symmetric encryption, AES-128-CBC with HMAC)
- Key: Base64-encoded 32-byte key
- Local development: Deterministic key (`admin-dev-fernet-key-00000000`)
- Production: Generate with `from cryptography.fernet import Fernet; Fernet.generate_key()`

### Data Encryption

**None at rest**: Local development stores data unencrypted in MinIO, SQLite, PostgreSQL, Redis.

**TLS in transit** (Production only):
- Kafka: `SASL_SSL` security protocol
- Redis: `REDIS_SSL=true` for ElastiCache
- MinIO: HTTPS endpoint
- LDAP: `ldaps://` with certificates (disabled in local development)

### Token Generation

**API Keys**: Not generated by the system. Provided externally via secrets management.

**Correlation IDs**: UUID4 for distributed tracing (not cryptographic)

**Session Tokens**: None. API key is used directly for each request.

## Security Headers

HTTP security headers applied to all responses.

### Implementation

**Middleware**: `services/simulation/src/api/middleware/security_headers.py`

**Class**: `SecurityHeadersMiddleware` (FastAPI middleware)

### Headers Applied

| Header | Value | Purpose |
|--------|-------|---------|
| `Content-Security-Policy` | `default-src 'self'; connect-src 'self' ws: wss:; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self'` | Restrict resource loading to same-origin, allow WebSockets |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Enforce HTTPS for 1 year (only effective over HTTPS) |
| `X-Frame-Options` | `DENY` | Prevent clickjacking by disallowing iframe embedding |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME type sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer information leakage |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Restrict browser feature access |

### CORS Configuration

**Module**: `services/simulation/src/api/app.py`

**Middleware**: `CORSMiddleware` (FastAPI/Starlette)

**Configuration**:
- Allowed origins: `CORS_ORIGINS` environment variable (comma-separated)
- Default: `http://localhost:5173,http://localhost:3000`
- Credentials: Allowed
- Methods: All (`["*"]`)
- Headers: All (`["*"]`)

**Purpose**: Enable frontend access from development servers

## PII Handling

How personally identifiable information is managed.

### PII Masking

**Module**: `services/simulation/src/sim_logging/filters.py`

**Class**: `PIIFilter` (logging.Filter)

**Patterns**:
- Emails: `[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+` -> `[EMAIL]`
- Phone numbers: `\d{3}[-.\s]?\d{3}[-.\s]?\d{4}` -> `[PHONE]`

**Application**: Applied globally to all log handlers via `handler.addFilter(PIIFilter())`

**Scope**: Masks PII in log messages before writing to stdout, files, or log aggregation services (Loki)

### Synthetic Data

**No Real PII**: All driver/rider data is generated using `Faker` library with Brazilian locale.

**Generator**: `services/simulation/src/agents/faker_provider.py`

**Data**: Names, emails, phone numbers, CPF (Brazilian tax ID) - all synthetic

**Purpose**: Portfolio demonstration with no risk of exposing real user data

## Known Security Considerations

Security-relevant notes from codebase analysis.

### Development-Only Security Model

**Shared API Key**: All clients use the same API key. No user differentiation or audit trail of which client performed which action.

**Default Credentials**: All services use `admin`/`admin` credentials. Acceptable for local development, insecure for production.

**No TLS Locally**: HTTP, LDAP, Kafka, Redis use unencrypted protocols. Production requires TLS/SSL configuration.

### Rate Limiting

**REST API**: Configurable limits per endpoint (e.g., 10 requests/minute)
- Tracked by API key (preferred) or IP address (fallback)
- Returns 429 with `Retry-After` header
- Metrics: OpenTelemetry counter for rate limit violations

**WebSocket**: Sliding window limiter (5 connections per 60 seconds per client)
- Closes connection with code 1008 on limit exceeded
- No retry-after guidance

### Schema Validation

**Kafka Events**: JSON Schema validation via Schema Registry ensures event contracts are enforced across producers and consumers.

**API Requests**: Pydantic validates all incoming requests, rejects invalid data with 422 Unprocessable Entity.

**Settings**: Pydantic validates environment variables at startup, crashes service if required secrets are missing (fail-fast).

### Container Security

**Pre-commit Hooks**: Detect committed secrets using `detect-secrets` (configured in `.pre-commit-config.yaml`)

**Secrets Baseline**: `.secrets.baseline` tracks known false positives

**Docker Secrets Volume**: `/secrets/` volume is ephemeral, not persisted in Docker images

### Observability Security

**Metrics Exposure**: Prometheus metrics at `/metrics` endpoint (unauthenticated) expose operational data but no PII or credentials.

**Log Aggregation**: Loki receives logs from all services. PII masking applied before emission.

**Tracing**: OpenTelemetry traces may contain correlation IDs but no credentials or PII.

### Database Security

**SQLite**: Local file storage with no authentication. Acceptable for simulation checkpoints (no PII).

**PostgreSQL**: Used by Airflow and Hive Metastore. Credentials injected from secrets. No encryption at rest.

**Redis**: AUTH password required. Data is ephemeral (pub/sub, state snapshots). No persistence.

**MinIO**: S3-compatible storage with access key / secret key authentication. Local development only.

### Frontend Security

**API Key Storage**: Stored in `sessionStorage` (cleared on tab close). Not persisted in `localStorage`.

**No XSS Protection**: React's default JSX escaping prevents injection, but no Content-Security-Policy nonce enforcement.

**WebSocket Hijacking**: Subprotocol-based authentication mitigates hijacking, but no additional CSRF tokens.

### Production Readiness Gaps

**Multi-Tenancy**: No support for multiple users or organizations. Single API key grants full access.

**Audit Logging**: No structured audit trail of who performed which actions (correlation IDs track requests, but not users).

**Secret Rotation**: No automated credential rotation. Manual secret updates required.

**Certificate Management**: No certificate provisioning or renewal automation. TLS certificates must be managed externally.

**Network Segmentation**: All services in single Docker network. No DMZ or segmentation by trust level.

**Intrusion Detection**: No IDS/IPS. Rate limiting is the only abuse prevention mechanism.

---

**Generated**: 2026-02-13
**Codebase**: rideshare-simulation-platform
**Security Model**: Development/Portfolio (Shared API Key)
**Secrets Management**: LocalStack Secrets Manager (local), AWS Secrets Manager (production)
**Authentication**: API Key (REST), API Key via Subprotocol (WebSocket)
**Validation**: Pydantic, JSON Schema (Kafka)
**PII Protection**: Log masking (emails, phone numbers)
