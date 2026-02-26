# INFRASTRUCTURE.md

> Operations and infrastructure facts for this codebase.

## CI/CD

### Pipeline
GitHub Actions

### Workflows
| Workflow | Trigger | Purpose |
|----------|---------|---------|
| ci.yml | push to main, PRs | Linters, type checks, unit tests, frontend build, API contract validation |
| integration-tests.yml | Daily 2 AM UTC, manual dispatch | Integration tests with full Docker stack |

### Pipeline Steps (Checks Workflow)
1. Checkout repository
2. Set up Python 3.13 and Node.js 20
3. Install dependencies (simulation, stream-processor, dbt, airflow, great-expectations, lakehouse, frontend)
4. Run pre-commit hooks on all files (black, ruff, mypy, eslint, prettier, detect-secrets)
5. Run unit tests (simulation, stream-processor)
6. Build frontend

### Pipeline Steps (Integration Tests)
1. Free disk space (remove .NET, Android SDK, GHC, CodeQL)
2. Checkout repository with LFS
3. Set up Python 3.13
4. Install test dependencies and DBT
5. Build and start core + data-pipeline Docker Compose profiles
6. Wait for services (MinIO, Kafka, Schema Registry, Redis, LocalStack, Spark Thrift Server)
7. Verify secrets initialization
8. Run integration tests
9. Collect container logs on failure

### Pre-Commit Hooks
- trailing-whitespace
- end-of-file-fixer
- check-yaml (multi-document support)
- check-added-large-files (500KB limit)
- black (Python formatting)
- ruff (Python linting with auto-fix)
- mypy (type checking for simulation, stream-processor, dbt, airflow, great-expectations, lakehouse)
- lint-staged (frontend ESLint/Prettier)
- TypeScript type checking (frontend)
- detect-secrets (baseline validation)

## Containerization

### Docker
- Base images:
  - Simulation: `python:3.13-slim`
  - Stream Processor: `python:3.13-slim`
  - Frontend: `node:20-alpine` (build), `nginx:alpine` (runtime)
  - Bronze Ingestion: `python:3.13-slim`
  - Hive Metastore: `apache/hive:4.0.0`
  - OSRM: `osrm/osrm-backend:v5.27.1`
  - MinIO: Custom with mc CLI
  - Tempo: `grafana/tempo:2.3.1`
  - OTel Collector: `otel/opentelemetry-collector-contrib:0.96.0`

### Docker Compose
- File: `infrastructure/docker/compose.yml`
- Profiles:
  | Profile | Services | Purpose |
  |---------|----------|---------|
  | core | kafka, schema-registry, redis, osrm, simulation, stream-processor, frontend | Simulation runtime |
  | data-pipeline | minio, bronze-ingestion, localstack, airflow, hive-metastore, trino, postgres-airflow, postgres-metastore | ETL and lakehouse |
  | monitoring | prometheus, cadvisor, grafana, otel-collector, loki, tempo | Observability |
  | spark-testing | spark-thrift-server, openldap | Dual-engine DBT validation |

### Build Commands
```bash
# Build specific service
docker compose -f infrastructure/docker/compose.yml build simulation

# Build all services in profile
docker compose -f infrastructure/docker/compose.yml --profile core build
```

### Run Commands
```bash
# Start core services
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Start multiple profiles
docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline up -d

# View logs
docker compose -f infrastructure/docker/compose.yml --profile core logs -f simulation

# Stop services
docker compose -f infrastructure/docker/compose.yml --profile core down
```

## Kubernetes

### Cluster Type
Kind (Kubernetes in Docker) - local development cluster

### Cluster Configuration
- 1 control-plane node
- 2 worker nodes
- 10GB total Docker memory budget
- Configuration: `infrastructure/kubernetes/kind/cluster-config.yaml`

### Management Scripts
| Script | Purpose |
|--------|---------|
| create-cluster.sh | Create Kind cluster and install External Secrets Operator |
| deploy-services.sh | Deploy all services via Kustomize |
| health-check.sh | Validate pod health and readiness |
| smoke-test.sh | Test core functionality (simulation start, agent spawning) |
| teardown.sh | Delete Kind cluster |

### GitOps
- Tool: ArgoCD
- Installation: `infrastructure/kubernetes/argocd/install.yaml`
- Applications:
  - `app-core-services.yaml` - Core simulation services
  - `app-data-pipeline.yaml` - Data lakehouse services
- Sync Policy: Auto-sync with self-healing (local), manual sync (production)

### Environment Overlays
- Base: `infrastructure/kubernetes/base/`
- Local: `infrastructure/kubernetes/overlays/local/`
- Production: `infrastructure/kubernetes/overlays/production/`
- Tool: Kustomize

### Ingress
- ALB Ingress Controller with IngressGroup (production)
- Gateway API (GatewayClass, Gateway, HTTPRoute) (local)
- Production routes (subdomain-per-service via shared ALB):
  - `api.ridesharing.portfolio.andresbrocco.com` -> simulation:8000
  - `grafana.ridesharing.portfolio.andresbrocco.com` -> grafana:3000
  - `airflow.ridesharing.portfolio.andresbrocco.com` -> airflow-webserver:8080
  - `trino.ridesharing.portfolio.andresbrocco.com` -> trino:8080
  - `prometheus.ridesharing.portfolio.andresbrocco.com` -> prometheus:9090

## Configuration Management

### Secrets Management
- Source: AWS Secrets Manager (LocalStack for development, AWS for production)
- Bootstrap: `secrets-init` service fetches secrets and writes to `/secrets` volume
- Secrets:
  | Secret | Keys | Purpose |
  |--------|------|---------|
  | rideshare/api-key | API_KEY | REST API authentication |
  | rideshare/core | KAFKA_SASL_USERNAME, KAFKA_SASL_PASSWORD, REDIS_PASSWORD, SCHEMA_REGISTRY_USER, SCHEMA_REGISTRY_PASSWORD | Core services (Kafka, Redis, Schema Registry) |
  | rideshare/data-pipeline | MINIO_ROOT_USER, MINIO_ROOT_PASSWORD, POSTGRES_AIRFLOW_USER, POSTGRES_AIRFLOW_PASSWORD, POSTGRES_METASTORE_USER, POSTGRES_METASTORE_PASSWORD, FERNET_KEY, INTERNAL_API_SECRET_KEY, JWT_SECRET, API_SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD, HIVE_LDAP_USERNAME, HIVE_LDAP_PASSWORD, LDAP_ADMIN_PASSWORD, LDAP_CONFIG_PASSWORD | Data pipeline (MinIO, PostgreSQL, Airflow, Hive, LDAP) |
  | rideshare/monitoring | ADMIN_USER, ADMIN_PASSWORD | Monitoring (Grafana) |

### Secrets Initialization
```bash
# Manual seeding (runs automatically via secrets-init service)
AWS_ENDPOINT_URL=http://localhost:4566 \
AWS_ACCESS_KEY_ID=test \
AWS_SECRET_ACCESS_KEY=test \
AWS_DEFAULT_REGION=us-east-1 \
./venv/bin/python3 infrastructure/scripts/seed-secrets.py
```

### Environment Variables
- Simulation settings: `SIM_*` (speed_multiplier, log_level, checkpoint_interval)
- Kafka settings: `KAFKA_*` (bootstrap servers, security protocol, SASL credentials)
- Redis settings: `REDIS_*` (host, port, password, SSL)
- OSRM settings: `OSRM_*` (base_url, threads)
- API settings: `API_*` (key, host, port)
- CORS settings: `CORS_*` (allowed origins)
- Stream processor: `PROCESSOR_*` (window size, aggregation strategy, topics)
- OpenTelemetry: `OTEL_*` (exporter endpoint)

### Configuration Files
| File | Purpose |
|------|---------|
| .env.example | Template for environment variables |
| services/kafka/topics.yaml | Kafka topic definitions |
| services/prometheus/prometheus.yml | Metrics scrape configuration |
| services/grafana/provisioning/datasources/datasources.yml | Grafana datasources |
| infrastructure/kubernetes/manifests/configmap-core.yaml | Core services config (K8s) |
| infrastructure/kubernetes/manifests/configmap-data-pipeline.yaml | Data pipeline config (K8s) |

## Logging & Monitoring

### Logging
- Library: Python `logging` (simulation, stream-processor), console (frontend)
- Format: JSON (structured logging in containers)
- Aggregation: Loki (monitoring profile)
- Output: stdout (collected by Docker/Kubernetes)

### Metrics
- Collection: Prometheus
- Exporters:
  - Simulation: OpenTelemetry -> OTel Collector -> Prometheus remote_write
  - Stream Processor: OpenTelemetry -> OTel Collector -> Prometheus remote_write
  - cAdvisor: Direct Prometheus scrape
  - OTel Collector: Self-metrics on port 8888
- Storage: Prometheus TSDB
- Scrape interval: 15s

### Distributed Tracing
- Tool: Tempo
- Protocol: OpenTelemetry (OTLP)
- Endpoint: otel-collector:4317 (gRPC), otel-collector:4318 (HTTP)
- Trace IDs: Propagated in event headers (`trace_id`, `span_id`, `trace_flags`)

### Dashboards
- Tool: Grafana
- Port: 3001
- Datasources: Prometheus, Trino, Loki, Tempo
- Dashboards:
  - Simulation Overview (agents, trips, matching performance)
  - Container Metrics (cAdvisor data)
  - Stream Processor (aggregation latency, Redis ops)

### Health Checks
- Simulation: `/health` (basic), `/health/detailed` (dependencies)
- Stream Processor: `/health`
- Kafka: `kafka-broker-api-versions`
- Redis: `redis-cli ping`
- MinIO: `/minio/health/live`
- Schema Registry: `/subjects`
- OSRM: `/route/v1/driving` test route
- LocalStack: `/_localstack/health`

## Deployment

### Method
Docker Compose (local/development), Kubernetes with Kind (cloud parity testing)

### Environments
| Environment | Access | Branch | Orchestration |
|-------------|--------|--------|---------------|
| Development | localhost:5173 | feature/* | Docker Compose (core profile) |
| Integration Testing | localhost:5173 | main | Docker Compose (core + data-pipeline) |
| Local Kubernetes | localhost:80 | main | Kind cluster |
| Production | ridesharing.portfolio.andresbrocco.com | main | AWS EKS + ArgoCD |

### Deployment Process (Docker Compose)
1. Start LocalStack (if using data-pipeline profile)
2. Run `secrets-init` service to seed credentials
3. Start services in dependency order (healthcheck-based)
4. Wait for all healthchecks to pass (~60-90 seconds)
5. Optionally run smoke tests

### Deployment Process (Kubernetes)
1. Create Kind cluster: `./infrastructure/kubernetes/scripts/create-cluster.sh`
2. Install External Secrets Operator
3. Seed secrets to LocalStack
4. Deploy services: `./infrastructure/kubernetes/scripts/deploy-services.sh`
5. Wait for pods to be Ready
6. Run health check: `./infrastructure/kubernetes/scripts/health-check.sh`
7. Run smoke test: `./infrastructure/kubernetes/scripts/smoke-test.sh`

### Cloud Deployment (AWS)

The platform can be deployed to AWS EKS for public demos. See [CLOUD-DEPLOYMENT.md](CLOUD-DEPLOYMENT.md) for complete runbook.

Architecture:

- **Foundation** (always-on): CloudFront, S3, Route 53, ECR, Secrets Manager (~$7.50/mo)
- **Platform** (on-demand): EKS cluster, RDS, ALB (~$0.65/hr)

GitHub Actions workflows:

| Workflow | Purpose |
|----------|---------|
| `deploy.yml` | Build images, deploy platform, and/or deploy frontend (input-driven) |
| `teardown.yml` | Destroy platform, preserve foundation |

Service URLs:

- Frontend: https://ridesharing.portfolio.andresbrocco.com (always available)
- API: https://api.ridesharing.portfolio.andresbrocco.com (when platform running)
- Grafana: https://grafana.ridesharing.portfolio.andresbrocco.com
- Airflow: https://airflow.ridesharing.portfolio.andresbrocco.com
- Trino: https://trino.ridesharing.portfolio.andresbrocco.com
- Prometheus: https://prometheus.ridesharing.portfolio.andresbrocco.com

### Resource Limits (Docker)
| Service | Memory Limit | CPU Limit |
|---------|--------------|-----------|
| kafka | 1280m | 1.5 |
| schema-registry | 512m | 0.5 |
| redis | 512m | - |
| osrm | 1g | - |
| simulation | 2g | 2.0 |
| stream-processor | 256m | 1.0 |
| frontend | 256m | - |
| minio | 512m | - |
| bronze-ingestion | 1g | - |
| hive-metastore | 2g | - |
| trino | 4g | - |
| airflow-scheduler | 2g | - |
| airflow-webserver | 1g | - |
| prometheus | 512m | - |
| grafana | 256m | - |
| otel-collector | 512m | - |
| loki | 512m | - |
| tempo | 512m | - |
| spark-thrift-server | 3g | - |

## Development Setup

### Prerequisites
- Docker Desktop with 10GB RAM allocated
- Docker Compose v2+
- Python 3.13+
- Node.js 20+
- Git LFS (for OSRM map data)

### Setup Steps
```bash
# Clone repository
git clone <repo-url>
cd rideshare-simulation-platform

# Configure environment
cp .env.example .env
# Edit .env if needed (most values injected from secrets)

# Start core services
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Wait for services to be healthy
sleep 60

# Verify health
curl http://localhost:8000/health

# Start simulation
curl -X POST -H "X-API-Key: admin" http://localhost:8000/simulation/start

# Spawn agents
curl -X POST -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"count": 50}' \
  http://localhost:8000/agents/drivers

curl -X POST -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"count": 100}' \
  http://localhost:8000/agents/riders

# Access frontend
open http://localhost:5173
```

### Common Commands
| Command | Purpose |
|---------|---------|
| `docker compose -f infrastructure/docker/compose.yml --profile core up -d` | Start core services |
| `docker compose -f infrastructure/docker/compose.yml --profile core logs -f` | View logs |
| `docker compose -f infrastructure/docker/compose.yml --profile core down` | Stop services |
| `cd services/simulation && ./venv/bin/pytest` | Run simulation tests |
| `cd services/stream-processor && ./venv/bin/pytest` | Run stream processor tests |
| `cd services/control-panel && npm run dev` | Start frontend dev server |
| `cd services/control-panel && npm run test` | Run frontend tests |
| `cd tools/dbt && ./venv/bin/dbt run` | Run DBT transformations |
| `./infrastructure/kubernetes/scripts/create-cluster.sh` | Create Kind cluster |
| `./infrastructure/kubernetes/scripts/deploy-services.sh` | Deploy to Kind |
| `./infrastructure/kubernetes/scripts/health-check.sh` | Check K8s health |
| `./infrastructure/kubernetes/scripts/teardown.sh` | Delete Kind cluster |

### Port Reference
See README.md Port Reference section for complete port mapping (22 services exposed on localhost).

### Troubleshooting
```bash
# Check secrets initialization
docker compose -f infrastructure/docker/compose.yml logs secrets-init

# Verify Kafka topics created
docker compose -f infrastructure/docker/compose.yml exec kafka \
  kafka-topics --list --bootstrap-server localhost:9092 \
  --command-config /tmp/kafka-client.properties

# Check Redis connectivity
docker compose -f infrastructure/docker/compose.yml exec redis \
  redis-cli -a admin ping

# View all service statuses
docker compose -f infrastructure/docker/compose.yml ps

# Rebuild specific service
docker compose -f infrastructure/docker/compose.yml build simulation
docker compose -f infrastructure/docker/compose.yml up -d simulation

# Check Kubernetes pod status
kubectl get pods -A

# Describe failing pod
kubectl describe pod <pod-name>

# View pod logs
kubectl logs <pod-name> -f
```

---

**Generated**: 2026-02-13
**Codebase**: rideshare-simulation-platform
**CI/CD**: GitHub Actions (4 workflows)
**Containerization**: Docker Compose (4 profiles, 30+ services)
**Deployment**: Docker Compose (local), Kind cluster (Kubernetes testing)
**Monitoring**: Prometheus + Grafana + Loki + Tempo via OpenTelemetry
