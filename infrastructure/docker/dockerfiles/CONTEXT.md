# CONTEXT.md — Dockerfiles

## Purpose

Retained configuration files for services that don't have their own Dockerfile. Most Dockerfiles have been moved to their respective `services/` directories. This directory now only contains the nginx configuration.

## Responsibility Boundaries

- **Owns**: nginx configuration for the frontend service
- **Delegates to**: Individual `services/*/Dockerfile` for service-specific builds, compose.yml for orchestration
- **Does not handle**: Service orchestration (handled by compose.yml), runtime configuration (handled by environment variables)

## Key Concepts

**Dockerfiles moved to services/**: As of the centralization effort, Dockerfiles now live alongside their service configuration in `services/*/Dockerfile`. This directory retains only `nginx.conf`.

**nginx.conf**: Configuration file for the frontend service. It proxies `/api/` and `/ws` to the simulation service for unified routing.

## Non-Obvious Details

**Historical note**: This directory previously contained Dockerfiles for OSRM, MinIO, Spark+Delta, Tempo, and OTel Collector. These have been moved to `services/osrm/`, `services/minio/`, `services/tempo/`, and `services/otel-collector/` respectively. The Spark Streaming service has been replaced by `services/bronze-ingestion/`.
