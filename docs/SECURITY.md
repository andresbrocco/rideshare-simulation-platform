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

### Storage
- **Development:** Environment variables loaded from `.env` file (gitignored)
- **Docker:** Environment variables passed via `compose.yml` with defaults
- **Production:** Intended for AWS Secrets Manager (not currently implemented)

### Access
- Loaded via: `services/simulation/src/settings.py` using Pydantic settings
- Never logged: PII filter masks sensitive patterns
- Not exposed in API responses

### Required Secrets
| Secret | Purpose | Environment Variable |
|--------|---------|---------------------|
| API_KEY | REST and WebSocket authentication | API_KEY |
| KAFKA_SASL_USERNAME | Confluent Cloud cluster access | KAFKA_SASL_USERNAME |
| KAFKA_SASL_PASSWORD | Confluent Cloud cluster access | KAFKA_SASL_PASSWORD |
| KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO | Schema Registry access | KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO |
| REDIS_PASSWORD | Redis authentication (optional) | REDIS_PASSWORD |
| DATABRICKS_TOKEN | Databricks workspace access | DATABRICKS_TOKEN |
| AWS_ACCESS_KEY_ID | AWS services access (optional) | AWS_ACCESS_KEY_ID |
| AWS_SECRET_ACCESS_KEY | AWS services access (optional) | AWS_SECRET_ACCESS_KEY |

### Default API Key
Development default: `dev-api-key-change-in-production`
- Intentionally self-documenting to indicate insecurity
- Must be changed for any non-local deployment
- Generation: `openssl rand -hex 32`

## Cryptography

Cryptographic operations used.

### Password Hashing
Not applicable - no user passwords stored.

### Data Encryption
No encryption of data at rest or in transit in local development mode.

**Transport security:**
- Local development: HTTP (no TLS)
- Kafka: PLAINTEXT for local broker, SASL_SSL for Confluent Cloud
- Redis: TCP without TLS for local, optional SSL for ElastiCache

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
| Kafka | 9092 | Kafka | SASL for cloud, none for local |
| Redis | 6379 | Redis | Password optional |
| OSRM | 5050 | HTTP | None (internal) |
| Schema Registry | 8085 | HTTP | Basic auth for cloud |

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

1. **Default API key:** `dev-api-key-change-in-production` is insecure if unchanged
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
- Replace default API key with cryptographically secure value
- Migrate to ticket-based WebSocket authentication
- Enable HTTPS/TLS for all public endpoints
- Move secrets to AWS Secrets Manager
- Implement IAM roles with least privilege
- ✓ Add API rate limiting (implemented with tiered limits)
- Enable network isolation with VPC and security groups
- ✓ Add security headers (HSTS, CSP, X-Frame-Options)
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
**Authentication Method:** Shared API key
**Primary Risk:** Default credentials if deployed unchanged
**Mitigation Strategy:** Self-documenting defaults and comprehensive production checklist
