# CONTEXT.md — Scripts

## Purpose

Root-level developer utility scripts for one-off and dev-lifecycle operations: bootstrapping the local dev environment end-to-end, regenerating simulation geospatial data from upstream sources, and migrating accumulated local data to AWS S3 before a cloud deployment.

## Responsibility Boundaries

- **Owns**: Developer-facing automation for environment setup, geospatial data refresh, and local-to-cloud data migration
- **Delegates to**: Docker Compose for service lifecycle, Simulation REST API for agent spawning, Airflow REST API for DAG management, MapShaper (via npx) for polygon simplification, boto3 for S3 operations
- **Does not handle**: Production deployments (see `infrastructure/`), CI/CD pipelines, or per-service scripts (those live under each service directory)

## Key Concepts

- **Immediate vs. scheduled agents** (`dev_test.py`): The simulation distinguishes agents spawned in `immediate` mode (active at startup) from `scheduled` mode (distributed across the simulation timeline). Drivers and riders are seeded separately, and the spawn order matters — drivers first, then riders.
- **GeoSampa zones** (`fetch_geosampa_zones.py`): São Paulo's 96 official administrative districts sourced from the `codigourbano/distritos-sp` GitHub repository. Each district is enriched with demand and surge parameters from `subprefecture_config.json` and must result in exactly 96 unique `zone_id` values — the script hard-asserts this count.
- **Bucket naming convention** (`sync-to-cloud.py`): Local MinIO buckets use the pattern `rideshare-{suffix}` (e.g., `rideshare-bronze`). AWS S3 destination buckets use `rideshare-{account_id}-{suffix}` to avoid global naming collisions.

## Non-Obvious Details

- `fetch_geosampa_zones.py` runs mapshaper simplification **twice** in sequence (visvalingam 1% per pass) rather than once at a higher percentage — this produces better geometry quality for the simulation's polygon membership checks. Requires `npx` to be available on the host (not inside Docker).
- The `ZoneLoader` inside the simulation only supports `Polygon` geometry, not `MultiPolygon`. The fetch script converts any `MultiPolygon` by selecting the largest polygon by area via the shoelace formula.
- `dev_test.py` respects per-endpoint batch limits: drivers cap at 100 per request, riders at 2000. It loops internally rather than exposing this to the caller.
- `dev_test.py` uses Airflow 3.x JWT auth (`POST /auth/token`) rather than HTTP Basic auth for DAG management calls.
- `sync-to-cloud.py` streams objects directly from MinIO to AWS S3 without writing temporary files — necessary given Delta Lake's many small-file pattern can produce thousands of objects.
- `sync-to-cloud.py` always uses the `rideshare` AWS CLI profile (never the default profile), consistent with the project-wide convention.

## Related Modules

- [infrastructure/docker](../infrastructure/docker/CONTEXT.md) — Dependency — Docker Compose configuration defining the complete local development environment...
