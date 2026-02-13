# CONTEXT.md — OSRM

## Purpose

Routing engine service for the rideshare simulation platform, providing real-time route calculation, distance estimation, and duration estimation for the Sao Paulo metropolitan area. Uses a pre-processed OpenStreetMap extract with the Multi-Level Dijkstra (MLD) algorithm to deliver fast point-to-point routing between simulation coordinates.

## Responsibility Boundaries

- **Owns**: Route calculation between coordinate pairs, distance/duration estimation, OSM data processing (extract/partition/customize), serving the OSRM HTTP API
- **Delegates to**: Simulation service for making route requests, Docker for container lifecycle management, Geofabrik for source map data (fetch mode only)
- **Does not handle**: Traffic data, real-time routing updates, map rendering, route visualization, trip business logic

## Key Concepts

**Multi-Stage Dockerfile**: The Dockerfile supports two build modes controlled by the `OSRM_MAP_SOURCE` build argument. `local` (default) copies a pre-extracted `sao-paulo-metro.osm.pbf` from the `data/` directory for fast, reproducible builds. `fetch` downloads the full `brazil-latest.osm.pbf` from Geofabrik and uses `osmium extract` with the Sao Paulo bounding box to produce a fresh extract, which is slower but yields the latest map data.

**MLD Algorithm**: OSRM is configured to use the Multi-Level Dijkstra algorithm (`--algorithm mld`) for routing. MLD offers a good balance between preprocessing time and query speed for metropolitan-scale routing.

**Data Processing Pipeline**: On first startup, `osrm-init.sh` runs a three-step pipeline — `osrm-extract` (parses OSM data into OSRM format), `osrm-partition` (creates routing hierarchy), `osrm-customize` (applies edge weights). Subsequent starts skip these steps because processed data is persisted in the `osrm-data` Docker volume.

**Thread Configuration**: The `OSRM_THREADS` environment variable controls how many threads `osrm-routed` uses for serving HTTP requests, defaulting to the number of available CPU cores.

## Non-Obvious Details

Runs on `linux/amd64` only because the OSRM backend image does not support ARM. On Apple Silicon Macs, Docker uses Rosetta emulation, which works but is slower than native execution.

First startup is slow (approximately 3 minutes) because `osrm-extract`, `osrm-partition`, and `osrm-customize` must process the full OSM data file. Subsequent starts skip this step since processed data is persisted in the `osrm-data` named volume.

The Sao Paulo bounding box used for map extraction (`-46.9233,-24.1044,-46.2664,-23.2566`) matches the simulation's `zones.geojson` boundaries, ensuring all simulation coordinates fall within the routable area.
