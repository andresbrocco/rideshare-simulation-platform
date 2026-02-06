# CI/CD Workflows

This directory is reserved for GitHub Actions workflow files.

## Directory Structure

When creating workflows, use the following path structure:

### Services

| Service | Path | Working Directory |
|---------|------|-------------------|
| Simulation | `services/simulation/` | `./services/simulation` |
| Stream Processor | `services/stream-processor/` | `./services/stream-processor` |
| Frontend | `services/frontend/` | `./services/frontend` |

### Data Platform

| Component | Path | Working Directory |
|-----------|------|-------------------|
| DBT | `data-platform/dbt/` | `./data-platform/dbt` |
| Spark Streaming | `data-platform/streaming/` | `./data-platform/streaming` |
| Orchestration (DAGs) | `data-platform/orchestration/` | `./data-platform/orchestration` |

### Infrastructure

| Component | Path | Working Directory |
|-----------|------|-------------------|
| Docker | `infrastructure/docker/` | `./infrastructure/docker` |
| Terraform | `infrastructure/terraform/` | `./infrastructure/terraform` |
| Kubernetes | `infrastructure/kubernetes/` | `./infrastructure/kubernetes` |
| Grafana | `services/grafana/` | `./services/grafana` |
| Prometheus | `services/prometheus/` | `./services/prometheus` |

## Docker Compose

Docker Compose must be run from `infrastructure/docker/`:

```yaml
# Correct
- name: Start services
  run: docker compose up -d
  working-directory: ./infrastructure/docker

# Or using -f flag
- name: Start services
  run: docker compose -f infrastructure/docker/compose.yml up -d
```

## Path Filters

Example path filters for workflow triggers:

```yaml
on:
  push:
    paths:
      # Simulation service
      - 'services/simulation/**'
      # Stream processor
      - 'services/stream-processor/**'
      # Frontend
      - 'services/frontend/**'
      # Data platform
      - 'data-platform/**'
      # Infrastructure
      - 'infrastructure/**'
```

## Test Commands

```yaml
# Simulation tests
- name: Run simulation tests
  run: ./venv/bin/pytest
  working-directory: ./services/simulation

# Frontend tests/build
- name: Build frontend
  run: npm run build
  working-directory: ./services/frontend

# Stream processor
- name: Run stream processor tests
  run: ./venv/bin/pytest
  working-directory: ./services/stream-processor
```
