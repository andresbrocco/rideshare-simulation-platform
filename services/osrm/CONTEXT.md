# CONTEXT.md — OSRM

## Purpose

Provides a self-contained road-network routing service for the Sao Paulo metropolitan area. The simulation engine queries this service to obtain realistic route geometries between pickup and dropoff points rather than computing straight-line paths.

## Responsibility Boundaries

- **Owns**: Containerized OSRM backend with pre-processed Sao Paulo road data; Docker image build pipeline for the OSM extract
- **Delegates to**: Simulation service (`src/geo`) for interpreting route responses; Geofabrik for upstream OSM source data when building from scratch
- **Does not handle**: H3 spatial indexing, driver-to-rider matching, or any application logic — it is a pure routing HTTP server

## Key Concepts

- **MLD algorithm**: The server starts with `--algorithm=mld` (Multi-Level Dijkstra), which requires the three-step processing pipeline (`osrm-extract` → `osrm-partition` → `osrm-customize`) rather than the simpler CH (Contraction Hierarchies) pipeline. MLD supports live traffic updates but is the only option here because the data is pre-built for MLD.
- **Bounding box**: The Sao Paulo metro extract covers `-46.9233,-24.1044,-46.2664,-23.2566` (min_lon, min_lat, max_lon, max_lat), matching the simulation zone area defined in `zones.geojson`.
- **Git LFS data file**: `data/sao-paulo-metro.osm.pbf` is a large binary tracked via Git LFS. Cloning without LFS support will produce a pointer file stub, causing the Docker build to fail at the COPY step.

## Non-Obvious Details

- **Dual-source build**: The Dockerfile has a `OSRM_MAP_SOURCE` build argument (`local` or `fetch`). `local` (default) copies the pre-extracted `.osm.pbf` from Git LFS — fast and reproducible. `fetch` downloads the full Sudeste (SE Brazil) region from Geofabrik and extracts the bounding box at build time using `osmium` — slow but always uses the latest OSM data.
- **Idempotent init**: `osrm-init.sh` writes a `.osrm-processed` marker after the three processing steps complete. On container restarts the expensive extraction is skipped, serving from already-processed files.
- **Debian archive workaround**: The `osrm/osrm-backend:v5.25.0` base image runs Debian Stretch (EOL). The Dockerfile rewrites `/etc/apt/sources.list` to point at `archive.debian.org` so `apt-get install wget curl` can succeed. This is required for the health-check tooling in the init script.
- **Thread tuning**: The number of routing threads defaults to `nproc` (all available cores) but can be overridden via the `OSRM_THREADS` environment variable if CPU sharing is needed in a constrained environment.

## Related Modules

- [infrastructure/docker](../../infrastructure/docker/CONTEXT.md) — Reverse dependency — Consumed by this module
