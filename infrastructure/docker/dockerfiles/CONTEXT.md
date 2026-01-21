# CONTEXT.md — Dockerfiles

## Purpose

Custom Dockerfiles for third-party services that require specialized build configurations, pre-downloaded dependencies, or modifications from their upstream images. These enable reproducible builds with geographically-specific data (São Paulo OSM maps) and pre-installed JARs for the data platform.

## Responsibility Boundaries

- **Owns**: Custom build definitions for MinIO, OSRM, Spark+Delta, and nginx configurations
- **Delegates to**: Upstream base images (golang:alpine, osrm/osrm-backend, apache/spark) for core functionality
- **Does not handle**: Service orchestration (handled by compose.yml), runtime configuration (handled by environment variables in compose files)

## Key Concepts

**Multi-stage builds**: Each Dockerfile uses multi-stage patterns to minimize final image size (build dependencies separated from runtime).

**OSRM map sources**: The `osrm.Dockerfile` supports two build-time strategies via `OSRM_MAP_SOURCE` arg:
- `local` (default): Uses pre-extracted São Paulo map from Git LFS (`data/osrm/sao-paulo-metro.osm.pbf`) for fast builds
- `fetch`: Downloads fresh Geofabrik data and extracts São Paulo bounding box at build time (slow, latest data)

**São Paulo bounding box**: `-46.9233,-24.1044,-46.2664,-23.2566` covers the full simulation area defined in `zones.geojson` with routing padding.

**Spark JAR pre-installation**: `spark-delta.Dockerfile` downloads all required JARs (Delta Lake, S3A, Kafka connectors) into `/opt/spark/jars/` at build time, ensuring they're on the classpath for all Spark sessions without runtime dependency resolution.

## Non-Obvious Details

**OSRM init script**: The `scripts/osrm-init.sh` performs a one-time OSRM data processing step (extract, partition, customize) on first container start, caching results in the container filesystem to avoid reprocessing on restarts.

**Debian archive workaround**: OSRM base image uses EOL Debian Stretch, requiring apt sources to be redirected to `archive.debian.org` for package installation.

**nginx.conf location**: The `nginx.conf` file is a configuration file, not a Dockerfile, but lives here alongside Dockerfiles for the frontend service. It proxies `/api/` and `/ws` to the simulation service for unified routing.

**MinIO version pinning**: Built from source at a specific release tag (`RELEASE.2025-10-15T17-29-55Z`) rather than using official images, likely for consistency or custom build flags.
