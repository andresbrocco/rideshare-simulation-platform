# Production Security Checklist

This checklist covers security hardening steps required before deploying to production. Items are organized by priority level.

## P0: Critical (Must Have Before Launch)

These items address fundamental security gaps that would expose the system to immediate risk.

### 1. Replace Default API Key

**Current state:** `dev-api-key-change-in-production`

**Action:**
```bash
# Generate cryptographically secure key
openssl rand -hex 32

# Store in AWS Secrets Manager (not environment variables)
aws secretsmanager create-secret \
  --name rideshare/api-key \
  --secret-string "$(openssl rand -hex 32)"
```

**Implementation changes:**
- Remove default value from docker-compose.yml
- Add secrets manager client to simulation service
- Load API key at startup from secrets manager
- Rotate key periodically (quarterly recommended)

### 2. Fix WebSocket Authentication

**Current state:** API key passed via query string, exposed in logs/history.

**Options:**

| Approach | Complexity | Security |
|----------|------------|----------|
| First-message auth | Medium | Good |
| Ticket-based auth | High | Best |
| Cookie + session | Medium | Good |

**Recommended: Ticket-based authentication**

```
1. Client requests short-lived ticket via REST API (authenticated)
2. Server generates ticket (UUID, expires in 30s)
3. Client connects to WebSocket with ticket
4. Server validates ticket, establishes connection
5. Ticket is single-use, cannot be replayed
```

**Implementation outline:**
```python
# REST endpoint
@app.post("/ws/ticket")
async def get_ws_ticket(api_key: str = Depends(verify_api_key)):
    ticket = str(uuid.uuid4())
    await redis.setex(f"ws_ticket:{ticket}", 30, "valid")
    return {"ticket": ticket}

# WebSocket endpoint
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    ticket = websocket.query_params.get("ticket")
    if not await redis.getdel(f"ws_ticket:{ticket}"):
        await websocket.close(code=1008)
        return
    # proceed with connection
```

### 3. Enable HTTPS/TLS

**Components requiring TLS:**

| Component | Solution |
|-----------|----------|
| API Gateway | AWS ALB with ACM certificate |
| Frontend | CloudFront with ACM |
| Internal services | Service mesh (optional) or internal ALB |

**Minimum configuration:**
- TLS 1.2+ only
- Strong cipher suites (ECDHE preferred)
- HSTS header with 1-year max-age
- Redirect HTTP to HTTPS

**AWS ALB listener:**
```
Protocol: HTTPS
Port: 443
Certificate: ACM-issued wildcard or specific domain
Default action: Forward to target group
```

### 4. Configure Secrets Manager

**Secrets to migrate:**

| Secret | Current Location | Target |
|--------|-----------------|--------|
| API_KEY | Environment variable | AWS Secrets Manager |
| KAFKA_SASL_PASSWORD | Environment variable | AWS Secrets Manager |
| Redis password | Environment variable | AWS Secrets Manager |

**Access pattern:**
```python
import boto3
from botocore.exceptions import ClientError

def get_secret(secret_name: str) -> str:
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_name)
    return response["SecretString"]
```

### 5. Set Up IAM Roles

**ECS Task Role permissions:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:rideshare/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

**Principle of least privilege:**
- No wildcard resources where possible
- Separate roles for each service
- No admin credentials in containers

### 6. Enable Network Isolation

**VPC design:**
```
┌─────────────────────────────────────────┐
│                  VPC                     │
│  ┌─────────────────────────────────┐    │
│  │        Public Subnets            │    │
│  │  ALB, NAT Gateway                │    │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │        Private Subnets           │    │
│  │  ECS Tasks, RDS, ElastiCache     │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

**Security groups:**
- ALB: Allow 443 from internet
- ECS: Allow from ALB only on app ports
- RDS/ElastiCache: Allow from ECS only

---

## P1: High Priority (Required for Production)

### 7. Add API Rate Limiting

**Recommended limits:**

| Endpoint Pattern | Limit | Window |
|-----------------|-------|--------|
| `/simulation/*` | 60 | 1 min |
| `/agents/*` | 100 | 1 min |
| `/metrics/*` | 30 | 1 min |
| `/ws` | 5 connections | per API key |

**Implementation options:**

1. **AWS WAF** (if using ALB) - Managed, no code changes
2. **FastAPI middleware** - `slowapi` library
3. **Redis-based** - Custom sliding window counter

**slowapi example:**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/simulation/status")
@limiter.limit("60/minute")
async def get_status(request: Request):
    ...
```

### 8. WebSocket Connection Limits

**Limits to implement:**
- Max connections per API key: 10
- Max connections total: 1000
- Idle timeout: 5 minutes
- Message size limit: 64KB

**Implementation:**
```python
class ConnectionManager:
    MAX_CONNECTIONS_PER_KEY = 10
    MAX_TOTAL_CONNECTIONS = 1000

    def __init__(self):
        self.connections_by_key: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, api_key: str):
        if len(self.connections_by_key.get(api_key, set())) >= self.MAX_CONNECTIONS_PER_KEY:
            await websocket.close(code=1008, reason="Connection limit exceeded")
            return False
        # ... proceed with connection
```

### 9. Migrate to PostgreSQL

**Why migrate from SQLite:**
- Connection pooling for concurrent access
- Network-accessible for multiple services
- Better backup/restore tooling
- Row-level locking

**AWS RDS configuration:**
- Instance: db.t3.micro (dev) / db.r5.large (prod)
- Multi-AZ: Yes for production
- Encryption: At rest (KMS) and in transit (SSL)
- Automated backups: 7-day retention

### 10. Add Audit Logging

**Events to log:**

| Event | Data to Capture |
|-------|-----------------|
| Authentication success/failure | Timestamp, IP, API key hash |
| Simulation state changes | User, action, previous state |
| Agent creation/deletion | User, agent ID, type |
| Configuration changes | User, setting, old/new value |

**Log format (JSON):**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "event_type": "simulation.started",
  "user": "api_key_hash_abc123",
  "source_ip": "10.0.1.50",
  "details": {"speed_multiplier": 10}
}
```

**Destination:** CloudWatch Logs with 90-day retention

### 11. Configure Monitoring Alarms

**Critical alarms:**

| Metric | Threshold | Action |
|--------|-----------|--------|
| API 5xx rate | > 1% for 5 min | PagerDuty alert |
| API latency p99 | > 2s for 5 min | Slack notification |
| Auth failures | > 50/min | Security alert |
| WebSocket disconnects | > 100/min | Investigation |

**CloudWatch alarm example:**
```yaml
AuthFailureAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    MetricName: AuthenticationFailure
    Namespace: Rideshare/API
    Statistic: Sum
    Period: 60
    EvaluationPeriods: 1
    Threshold: 50
    ComparisonOperator: GreaterThanThreshold
```

---

## P2: Medium Priority (Recommended)

### 12. Implement Multi-Key Authentication

**Use cases:**
- Different keys per environment (dev, staging, prod)
- Different keys per client/integration
- Key rotation without downtime

**Schema:**
```python
class APIKey(BaseModel):
    key_hash: str  # bcrypt hash
    name: str
    permissions: list[str]  # ["read", "write", "admin"]
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
```

### 13. Add Security Headers

**Headers to add:**

```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    return response
```

### 14. Enable Container Image Scanning

**ECR scanning configuration:**
- Enable scan on push
- Block deployments with critical CVEs
- Weekly full scans of running images

**GitHub Actions integration:**
```yaml
- name: Scan image
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ env.ECR_REGISTRY }}/rideshare-simulation:${{ github.sha }}
    exit-code: '1'
    severity: 'CRITICAL,HIGH'
```

### 15. Configure Secret Rotation

**Rotation schedule:**

| Secret | Frequency | Method |
|--------|-----------|--------|
| API keys | 90 days | Lambda rotation |
| Database password | 30 days | RDS automatic |
| Kafka credentials | 90 days | Manual (Confluent Cloud) |

**AWS Secrets Manager rotation:**
```python
# Lambda function triggered by Secrets Manager
def rotate_secret(event, context):
    step = event["Step"]
    if step == "createSecret":
        # Generate new secret
    elif step == "setSecret":
        # Update the service with new secret
    elif step == "testSecret":
        # Verify new secret works
    elif step == "finishSecret":
        # Mark rotation complete
```

---

## P3: Lower Priority (Nice to Have)

### 16. GDPR Compliance

**If handling EU user data:**

- [ ] Data processing agreement with Confluent Cloud
- [ ] Right to deletion implementation
- [ ] Data export functionality
- [ ] Consent management
- [ ] Privacy policy documentation
- [ ] DPO appointment (if required)

### 17. SOC 2 Preparation

**Controls to implement:**

- [ ] Access review process (quarterly)
- [ ] Change management documentation
- [ ] Incident response plan
- [ ] Business continuity plan
- [ ] Vendor security assessments
- [ ] Security awareness training

---

## Verification Checklist

Before go-live, verify:

```
[ ] Default API key replaced
[ ] WebSocket auth upgraded from query string
[ ] All traffic over HTTPS
[ ] Secrets in Secrets Manager (not env vars)
[ ] IAM roles configured with least privilege
[ ] VPC with private subnets
[ ] Rate limiting enabled
[ ] Audit logging active
[ ] Monitoring alarms configured
[ ] Container images scanned
[ ] Security headers present
[ ] Penetration test completed (recommended)
```

## References

- [AWS Security Best Practices](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/welcome.html)
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
