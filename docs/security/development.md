# Development Security Model

This document details the current security implementation, designed for local development and portfolio demonstrations.

## Design Philosophy

The platform prioritizes **developer experience** over security hardening:

- Single shared API key (no user management overhead)
- HTTP transport (no certificate management)
- Permissive CORS (any localhost port works)
- No rate limiting (faster iteration during development)

This is acceptable because:
1. All data is synthetic (no real PII)
2. Runs locally or in isolated Docker networks
3. Educational purpose (demonstrates data engineering, not security)
4. Self-documenting defaults make insecure choices obvious

## REST API Authentication

**Implementation:** `simulation/src/api/auth.py`

```python
def verify_api_key(x_api_key: str = Header(...)):
    api_key = os.getenv("API_KEY")
    if x_api_key != api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
```

**Protected routes:**
- `/simulation/*` - Simulation control (start, stop, pause)
- `/agents/*` - Agent management (create drivers/riders)
- `/metrics/*` - Performance metrics

**Unprotected routes:**
- `/health` - Basic health check (for Docker/k8s probes)
- `/health/detailed` - Detailed service health (no auth for monitoring tools)
- `/auth/validate` - API key validation (returns 401 if invalid)

**Usage:**
```bash
curl -H "X-API-Key: dev-api-key-change-in-production" \
     http://localhost:8000/simulation/status
```

## WebSocket Authentication

**Implementation:** `simulation/src/api/websocket.py`

```python
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    api_key = websocket.query_params.get("api_key")
    if not api_key or api_key != settings.api.key:
        await websocket.close(code=1008)
        return
```

**Why query string instead of header?**

Browser WebSocket API doesn't support custom headers. The alternatives are:
1. Query string (current) - Simple but exposes key in logs/history
2. First message authentication - Requires protocol changes
3. Cookie-based - Adds session management complexity

For a demo project, query string is the pragmatic choice.

**Security implications:**
- API key visible in browser developer tools
- API key logged by reverse proxies (nginx access logs)
- API key stored in browser history
- No protection against replay attacks

**Usage (JavaScript):**
```javascript
const ws = new WebSocket("ws://localhost:8000/ws?api_key=dev-api-key-change-in-production");
```

## Stream Processor Security

**Implementation:** `stream-processor/src/api.py`

The stream processor exposes two endpoints without authentication:

| Endpoint | Purpose |
|----------|---------|
| `/health` | Docker health checks, simulation API dependency check |
| `/metrics` | Performance monitoring (throughput, latency) |

**Why no authentication?**

1. Internal service communication within Docker network
2. Only exposes operational metrics, no sensitive data
3. Health endpoints conventionally remain open for infrastructure
4. Adding auth would require shared secret management between services

**Network isolation:**
- Docker Compose creates isolated `rideshare-network`
- Port 8080 is exposed for development convenience, not required
- In production, this would be internal-only

## Transport Security

**Current state:** All HTTP, no TLS

| Component | Protocol | Port |
|-----------|----------|------|
| Simulation API | HTTP | 8000 |
| Stream Processor | HTTP | 8080 |
| Frontend | HTTP | 5173/3000 |
| Kafka | PLAINTEXT | 9092 |
| Redis | TCP (no auth) | 6379 |

**Why no TLS locally?**

- Certificate management overhead
- Self-signed certs cause browser warnings
- localhost traffic isn't intercepted
- Docker network provides isolation

## CORS Configuration

**Implementation:** `simulation/src/api/app.py`

```python
settings = get_settings()
origins = settings.cors.origins.split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Default origins:** `http://localhost:5173,http://localhost:3000`

Additional ports (5174-5178) added in Docker Compose for Vite dev server port conflicts.

**Settings:**
- `allow_credentials=True` - Allows cookies/auth headers
- `allow_methods=["*"]` - All HTTP methods
- `allow_headers=["*"]` - All headers including `X-API-Key`

## Database Security

**SQLite (`simulation.db`):**
- File-based, no network access
- No authentication (file system permissions only)
- Stores agent state, trip history, checkpoints
- Docker volume mount protects from container restarts

## Session Management

No session management implemented. Each request is independently authenticated via API key.

**Implications:**
- No session hijacking risk
- No session fixation risk
- No logout functionality needed
- API key rotation requires restart/redeploy

## Known Security Trade-offs

### 1. Default API Key

**File:** `docker-compose.yml:106`
```yaml
API_KEY=${API_KEY:-dev-api-key-change-in-production}
```

**Risk:** If deployed without changing, anyone can control the simulation.

**Mitigation:** The default value is self-documenting ("change-in-production").

### 2. WebSocket Query String

**Risk:** API key exposure in logs, history, referrer headers.

**Mitigation:**
- Acceptable for synthetic data
- Production would require protocol upgrade

### 3. No Rate Limiting

**Risk:** DoS attacks, resource exhaustion.

**Mitigation:**
- Local deployment only
- Docker resource limits (`mem_limit` in compose)

### 4. Unauthenticated Monitoring

**Risk:** Information disclosure (throughput, latency, connection status).

**Mitigation:**
- No sensitive data exposed
- Metrics are operational, not business data

### 5. HTTP Transport

**Risk:** Credential interception, MITM attacks.

**Mitigation:**
- localhost only
- Docker network isolation

### 6. No Content Security Policy

**Risk:** XSS attacks if user-controlled content rendered.

**Mitigation:**
- No user-generated content in UI
- All data is synthetic, system-controlled

## Environment Variables

Security-related environment variables:

| Variable | Purpose | Default |
|----------|---------|---------|
| `API_KEY` | REST/WebSocket authentication | `dev-api-key-change-in-production` |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:5173,http://localhost:3000` |
| `KAFKA_SASL_USERNAME` | Kafka authentication | (empty for local) |
| `KAFKA_SASL_PASSWORD` | Kafka authentication | (empty for local) |
| `REDIS_PASSWORD` | Redis authentication | (empty for local) |

## Best Practices for Local Development

1. **Keep default API key** - It's obvious and works out of the box
2. **Don't expose ports externally** - Keep everything on localhost
3. **Use Docker Compose** - Network isolation is automatic
4. **Don't add real credentials** - `.env` is gitignored but accidents happen
5. **Treat all data as public** - It's synthetic anyway
