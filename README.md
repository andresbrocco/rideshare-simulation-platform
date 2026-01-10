# Rideshare Simulation Platform

A ride-sharing simulation platform that generates realistic synthetic data for data engineering portfolio demonstrations.

> **Repository Reorganization (2026-01-15)**: This monorepo was reorganized to improve structure.
> Services are now under `services/`, data engineering under `data-platform/`, and infrastructure
> under `infrastructure/`. Docker Compose service names remain unchanged for compatibility.

## Environment Setup

### 1. Copy Environment Template

```bash
cp .env.example .env
```

### 2. Configure Required Variables

Edit `.env` and set the following required variables:

**Kafka (Confluent Cloud)**
- `KAFKA_BOOTSTRAP_SERVERS` - Your Confluent Cloud bootstrap servers
- `KAFKA_SASL_USERNAME` - Confluent Cloud API Key (cluster-level)
- `KAFKA_SASL_PASSWORD` - Confluent Cloud API Secret (cluster-level)
- `KAFKA_SCHEMA_REGISTRY_URL` - Schema Registry endpoint
- `KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO` - Schema Registry credentials (`key:secret`)

**Databricks**
- `DATABRICKS_HOST` - Workspace URL (e.g., `https://dbc-xxxxx.cloud.databricks.com`)
- `DATABRICKS_TOKEN` - Personal access token from User Settings > Developer > Access Tokens

**API Authentication**
- `API_KEY` - Generate a secure key with: `openssl rand -hex 32`

**Control Panel Frontend**
- `VITE_API_URL` - Backend API URL (default: http://localhost:8000)
- `VITE_WS_URL` - WebSocket URL for real-time updates (default: ws://localhost:8000/ws)

**Optional Variables (have sensible defaults)**
- `SIM_SPEED_MULTIPLIER` - Simulation speed (default: 1)
- `SIM_LOG_LEVEL` - Logging level (default: INFO)
- `REDIS_HOST` - Redis hostname (default: localhost)
- `OSRM_BASE_URL` - OSRM routing service (default: http://localhost:5000)
- `AWS_REGION` - AWS region (default: us-east-1)
- `CORS_ORIGINS` - CORS allowed origins (default: http://localhost:5173,http://localhost:3000)

### 3. Local Development

For local development with Docker Compose services, see `.env.local` as a reference. The simulation can run against:
- Local Kafka/Redis containers (via Docker Compose)
- Confluent Cloud + local Redis
- Full cloud stack (Confluent Cloud, ElastiCache, etc.)

### 4. Loading Settings in Code

```python
from settings import get_settings

settings = get_settings()
print(f"Kafka brokers: {settings.kafka.bootstrap_servers}")
print(f"Speed multiplier: {settings.simulation.speed_multiplier}")
```

## Security

This project uses a development-first security model optimized for local development and portfolio demonstrations. All data is synthetic.

**Quick start:** The default API key (`dev-api-key-change-in-production`) works out of the box for local development.

For details, see [Security Documentation](docs/security/README.md):
- [Development Security Model](docs/security/development.md) - Current implementation
- [Production Checklist](docs/security/production-checklist.md) - Hardening guide
