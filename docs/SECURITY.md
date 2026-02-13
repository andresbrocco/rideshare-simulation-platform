# SECURITY.md

> Security-relevant facts for this codebase.

## Authentication

How users are authenticated.

### Method
API key-based authentication using a shared secret.

### Implementation
- Module: `services/simulation/src/api/auth.py`
- Validation function: `verify_api_key()`
- API key storage: Environment variable `API_KEY`
- REST authentication: `X-API-Key` header
- WebSocket authentication: `Sec-WebSocket-Protocol` header with format `apikey.<key>`

### Endpoints
- **Protected (require API key):**
  - `/simulation/*` - Simulation control (start, stop, pause, resume)
  - `/agents/*` - Agent management (create drivers/riders)
  - `/puppet/*` - Puppet agent control
  - `/metrics/*` - Performance metrics
  - `/auth/validate` - API key validation
- **Unprotected (no authentication):**
  - `/health` - Basic health check (for container orchestration)
  - `/health/detailed` - Detailed service health with latency metrics
  - Stream processor endpoints: `/health`, `/metrics` (internal monitoring)

### WebSocket Authentication
- API key encoded in `Sec-WebSocket-Protocol` header as `apikey.<key>` format
- Browser WebSocket API limitation requires subprotocol negotiation approach
- Invalid API key results in WebSocket close with code 1008
- Snapshot-on-connect pattern provides full state to authenticated clients

## Authorization

How permissions are enforced.

### Model
Simple authentication-only model. No role-based access control.

### Implementation
- All authenticated requests have full access
- Single shared API key grants complete control over simulation
- No per-user permissions or role differentiation

### Access Control
- API key validates identity only
- No granular permissions (read vs write, admin vs user)
- All or nothing access model

## Input Validation

How input is validated.

### Library
Pydantic for data validation and settings management.

### Approach
- **Request validation:** Pydantic models validate all API request bodies
- **Settings validation:** Environment variables validated at startup via `pydantic_settings`
- **Event validation:** Kafka events validated against JSON schemas
- **Data sanitization:** PII masking in logs via regex patterns

### Locations
- API layer: `services/simulation/src/api/models/` - Request/response validation
- Settings: `services/simulation/src/settings.py` - Configuration validation
- Events: `services/simulation/src/events/schemas.py` - Event schema definitions
- Kafka: `schemas/kafka/*.json` - JSON Schema validation with Schema Registry
- Logging: `services/simulation/src/sim_logging/filters.py` - PII filter for emails and phone numbers

### Validation Examples
- URL validation: OSRM base URL must start with `http://` or `https://`
- Range validation: Speed multiplier constrained to 1-1024
- Required fields: Pydantic enforces required vs optional fields
- Type safety: Strong typing throughout Python codebase with mypy

## Secrets Management

How secrets are handled.

### Architecture

All secrets are stored in LocalStack Secrets Manager (local dev) or AWS Secrets Manager (cloud):

| Secret Path | Purpose | Consumed By |
|-------------|---------|-------------|
| `rideshare/api-key` | Control Panel API authentication | Simulation, Frontend |
| `rideshare/minio` | S3-compatible storage | MinIO, Spark, Hive, Trino |
| `rideshare/redis` | Cache authentication | Redis server, clients |
| `rideshare/kafka` | Message broker authentication | Kafka broker, all clients |
| `rideshare/schema-registry` | Schema management auth | Schema Registry, clients |
| `rideshare/hive-thrift` | SQL interface auth | DBT, Airflow, scripts |
| `rideshare/ldap` | Directory service | OpenLDAP |
| `rideshare/airflow` | Workflow orchestration | Airflow webserver, scheduler |
| `rideshare/grafana` | Dashboard access | Grafana |
| `rideshare/postgres-airflow` | Airflow metadata database | PostgreSQL, Airflow |
| `rideshare/postgres-metastore` | Hive Metastore database | PostgreSQL, Hive |

### Secret Injection

The `secrets-init` service runs before all other services:
1. Seeds LocalStack Secrets Manager with all credentials
2. Fetches secrets and writes them to `/secrets/*.env` files on a shared volume
3. All services source their credentials from these env files at startup

Loaded via: `services/simulation/src/settings.py` using Pydantic settings
- Never logged: PII filter masks sensitive patterns
- Not exposed in API responses

### Local Development

Default credentials (dev mode only):
- All usernames/passwords: `admin` / `admin`
- API key: `admin`
- Airflow Fernet key: Format-compliant generated key (reproducible for dev)

**Never commit production credentials.** Use `.env.local` (gitignored) for local overrides if needed.

### Authentication Mechanisms

| Service | Mechanism | Protocol |
|---------|-----------|----------|
| Kafka | SASL PLAIN | SASL_PLAINTEXT |
| Schema Registry | HTTP Basic Auth | HTTP |
| Redis | AUTH | Redis protocol |
| Spark Thrift | LDAP | HiveServer2 |
| MinIO | Access Key / Secret Key | S3 API |
| Airflow | Flask session + JWT | HTTP |
| Grafana | Basic Auth | HTTP |

### Secret Detection

Pre-commit hook (`detect-secrets`) prevents accidental secret commits:
- Scans all staged files for potential secrets
- Uses `.secrets.baseline` for known-safe patterns
- Blocks commits with detected secrets

### Production Deployment Checklist

- [ ] Configure AWS Secrets Manager with production credentials
- [ ] Update `AWS_ENDPOINT_URL` to point to real AWS Secrets Manager
- [ ] Rotate all default `admin` credentials to strong passwords
- [ ] Generate secure Airflow Fernet key
- [ ] Enable TLS for all services

## Cryptography

Cryptographic operations used.

### Password Hashing
Not applicable - no user passwords stored.

### Data Encryption
No encryption of data at rest or in transit in local development mode.

**Transport security:**
- Local development: HTTP (no TLS)
- Kafka: SASL_PLAINTEXT for local broker, SASL_SSL for Confluent Cloud
- Redis: AUTH over TCP for local, optional SSL for ElastiCache

## Security Headers

HTTP security headers.

### CORS Configuration
- Middleware: FastAPI `CORSMiddleware`
- Module: `services/simulation/src/api/app.py`
- Allowed origins: Configurable via `CORS_ORIGINS` environment variable
- Default origins: `http://localhost:5173,http://localhost:3000`
- Allow credentials: `True`
- Allow methods: All (`["*"]`)
- Allow headers: All (`["*"]`)

### HTTP Security Headers
- Middleware: `SecurityHeadersMiddleware`
- Module: `services/simulation/src/api/middleware/security_headers.py`
- Applied to all HTTP responses globally

**Configured headers:**

| Header | Value | Purpose |
|--------|-------|---------|
| `Content-Security-Policy` | `default-src 'self'; connect-src 'self' ws: wss:; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self'` | Mitigate XSS attacks, allow WebSocket connections |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Enforce HTTPS for 1 year including subdomains |
| `X-Frame-Options` | `DENY` | Prevent clickjacking attacks |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME type sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer information leakage |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Disable unnecessary browser features |

**CSP directives:**
- `default-src 'self'`: Only load resources from same origin by default
- `connect-src 'self' ws: wss:`: Allow WebSocket connections for real-time updates
- `style-src 'self' 'unsafe-inline'`: Allow inline styles for frontend compatibility
- `img-src 'self' data:`: Allow data URIs for inline images
- `script-src 'self'`: Only execute scripts from same origin

## Logging and Monitoring

Security-relevant logging practices.

### PII Protection
- Filter: `services/simulation/src/sim_logging/filters.py`
- Email pattern: `[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+` replaced with `[EMAIL]`
- Phone pattern: `\d{3}[-.]?\s?\d{3}[-.]?\s?\d{4}` replaced with `[PHONE]`
- Applied to all log messages before output

### Correlation IDs
- Module: `services/simulation/src/core/correlation.py`
- Event correlation: All Kafka events include `correlation_id` for distributed tracing
- Session tracking: `session_id` (UUID) identifies each simulation run
- Context propagation: Correlation IDs flow through logs and events

### Log Formats
- Development: Human-readable text format via `DevFormatter`
- Production: Structured JSON format via `JSONFormatter`
- Fields: timestamp, level, logger, message, correlation_id, trip_id, driver_id, rider_id

## Network Security

Network isolation and exposure.

### Docker Network Isolation
- Network: `rideshare-network` (isolated Docker bridge network)
- Internal communication: Services communicate via container names
- Port exposure: Selected ports exposed to host for development access

### Exposed Ports
| Service | Port | Protocol | Authentication |
|---------|------|----------|----------------|
| Simulation API | 8000 | HTTP | API key required |
| Frontend | 3000, 5173 | HTTP | None (static assets) |
| Stream Processor | 8080 | HTTP | None (monitoring only) |
| Kafka | 9092 | Kafka | SASL_PLAINTEXT (all environments) |
| Redis | 6379 | Redis | AUTH password required |
| OSRM | 5050 | HTTP | None (internal) |
| Schema Registry | 8085 | HTTP | HTTP Basic Auth required |

### Service-to-Service Communication
- Kafka broker: Accessed by simulation, bronze-ingestion, stream-processor
- Redis: Accessed by simulation, stream-processor
- OSRM: Accessed by simulation only
- No service mesh or mutual TLS

## Known Security Considerations

Security-relevant notes from documentation and code analysis.

### Development Security Model
- **Design philosophy:** Prioritizes developer experience over security hardening
- **Target environment:** Local development and portfolio demonstrations
- **Data sensitivity:** All data is synthetic (no real PII)
- **Network assumption:** localhost or isolated Docker networks only
- **Compliance:** None required (educational purpose)

### Documented Limitations
From `docs/security/development.md`:

1. **Default credentials:** All services use `admin`/`admin` in dev mode — must be rotated for production
2. **HTTP transport:** No TLS encryption in local development
3. **Unauthenticated monitoring:** `/health` and `/metrics` endpoints have no auth
4. **Permissive CORS:** Allows all methods and headers from configured origins

### Session Management
- No session cookies or tokens
- Stateless authentication on every request
- API key rotation requires service restart
- No logout functionality (not applicable)

### SQLite Security
- Database: `services/simulation/simulation.db`
- File-based storage with no network access
- No authentication (filesystem permissions only)
- Contains agent state, trip history, checkpoints
- Docker volume mount persists across container restarts

### Production Hardening Checklist
Documented in `docs/security/production-checklist.md`:
- ✓ Centralized secrets management (LocalStack / AWS Secrets Manager)
- ✓ Service authentication (Kafka SASL, Redis AUTH, Schema Registry Basic Auth, LDAP)
- ✓ Secret detection pre-commit hook (detect-secrets)
- ✓ Add API rate limiting (implemented with tiered limits)
- ✓ Add security headers (HSTS, CSP, X-Frame-Options)
- Replace default `admin` credentials with strong passwords
- Migrate to ticket-based WebSocket authentication
- Enable HTTPS/TLS for all public endpoints
- Switch `AWS_ENDPOINT_URL` from LocalStack to AWS Secrets Manager
- Implement IAM roles with least privilege
- Enable network isolation with VPC and security groups
- Migrate from SQLite to PostgreSQL
- Implement audit logging
- Configure monitoring alarms

### Event Flow Security
- Single source of truth: Simulation publishes exclusively to Kafka
- Stream processor bridges Kafka to Redis (eliminates duplicate events)
- No direct Redis publishing from simulation
- Event replay capability via Kafka retention
- Correlation IDs enable duplicate detection

### Geographic Data
- Zone boundaries: `services/simulation/data/zones.geojson` - public geographic data
- No sensitivity concerns (Sao Paulo districts are public information)

---

**Generated:** 2026-01-21
**Codebase:** rideshare-simulation-platform
**Security Model:** Development-first (local/demo environments)
**Authentication Method:** API key + per-service auth (SASL, Basic Auth, AUTH, LDAP)
**Secrets Management:** LocalStack Secrets Manager (local) / AWS Secrets Manager (cloud)
**Primary Risk:** Default `admin` credentials if deployed unchanged
**Mitigation Strategy:** Centralized secrets with detect-secrets pre-commit hook
