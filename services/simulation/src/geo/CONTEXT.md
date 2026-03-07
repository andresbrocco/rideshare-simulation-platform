# CONTEXT.md — Geo

## Purpose

Provides all geospatial computation and routing services used by the simulation engine: real road routing via OSRM, GPS position interpolation along polylines, zone assignment from coordinates, zone loading from GeoJSON, and time-of-day traffic modeling. This module is the simulation's single authority on anything involving latitude/longitude, distance, and map-based movement.

## Responsibility Boundaries

- **Owns**: Haversine distance calculations, GPS noise/dropout simulation, polyline interpolation, OSRM HTTP integration, route LRU caching, zone polygon membership, and traffic multiplier curves
- **Delegates to**: `src/core` for exception hierarchy (`NetworkError`, `ValidationError`), `src/metrics` for OSRM latency recording, OpenTelemetry for distributed tracing spans
- **Does not handle**: Driver/rider agent state, H3 spatial indexing for driver matching (that lives in `src/engine`), or any Kafka/Redis I/O

## Key Concepts

- **Zone**: A named GeoJSON polygon with `demand_multiplier` and `surge_sensitivity` attributes that influence rider demand and pricing. Loaded once at startup from a GeoJSON FeatureCollection file. Centroids are arithmetic means of polygon vertices (not area-weighted).
- **ZoneAssignmentService**: Assigns a coordinate pair to a zone ID using point-in-polygon via Shapely, falling back to nearest centroid (within 50 km). Uses H3 resolution-9 cells (~174 m edge) as LRU cache keys so nearby coordinates within the same cell reuse the result without polygon tests.
- **STRtree vs linear scan**: `ZoneLoader.find_zone_for_location` uses Shapely's STRtree spatial index; `ZoneAssignmentService._find_zone` uses a linear polygon scan. Both coexist — ZoneAssignmentService adds the H3-keyed LRU layer on top.
- **RouteCacheService**: Wraps `OSRMClient` with an LRU cache (default 10,000 entries) keyed by H3 resolution-9 cells for origin and destination. Routes between coordinates in the same pair of cells are served from cache, avoiding repeat OSRM HTTP calls.
- **OSRMClient dual interface**: Exposes both `get_route` (async, httpx) and `get_route_sync` (synchronous, requests). The sync variant exists because SimPy processes run in a separate thread where invoking asyncio would block the event loop — `get_route_sync` must be used from SimPy generators.
- **TrafficModel**: Scales OSRM base durations using sigmoid-smoothed multipliers for morning rush (7–9 AM, +40%), evening rush (5–7 PM, +40%), and night hours (10:30 PM–5:30 AM, −15%). Effects are combined with `max` for overlapping rush periods; night takes priority when active.
- **GPSSimulator**: Adds Gaussian noise (default 10 m sigma, clamped at 15 m) to positions and simulates signal dropout at a configurable probability. Interpolates along a polyline by progress fraction using binary search (`bisect_left`) on precomputed cumulative Haversine distances.

## Non-Obvious Details

- **Coordinate order inconsistency**: GeoJSON standard is `[lon, lat]`, so zone geometry tuples are stored as `(lon, lat)`. Shapely `Point` is created as `Point(lon, lat)`. However, all public API functions (distance, interpolation, OSRM) use `(lat, lon)` order. The conversion comment `# Shapely uses (x, y) = (lon, lat)` appears in multiple places — mixing these will silently produce wrong results.
- **Flat-Earth bounding box pre-check**: `is_within_proximity` applies a cheap rectangular pre-filter before computing Haversine. The longitude threshold deliberately omits the `cos(lat)` correction (conservative at Sao Paulo's ~23.5°S latitude), which means slightly more candidates reach Haversine but guarantees no false negatives.
- **`NoRouteFoundError` is non-retryable**: It inherits from `ValidationError` (permanent failure), not from `NetworkError`. An OSRM "NoRoute" response means no road path exists between the coordinates, so retrying will not help.
- **Cache key precision**: `OSRMClient._generate_cache_key` formats coordinates to 6 decimal places (~11 cm precision). `RouteCacheService` instead uses H3 cells, so the two caching strategies are not equivalent — the route cache is coarser but the client method is unused by the cache service.
- **`precompute_cumulative_distances` return length**: Returns `len(polyline) - 1` entries, not `len(polyline)`. Index `i` stores the cumulative distance from point 0 to point `i+1`. Callers must account for this offset when indexing.

## Related Modules

- [services/simulation/src](../CONTEXT.md) — Reverse dependency — Provides main, SimulationRunner, Settings (+8 more)
- [services/simulation/src/agents](../agents/CONTEXT.md) — Reverse dependency — Provides DriverAgent, RiderAgent, DriverDNA (+8 more)
- [tools/dbt/models/marts/facts](../../../../tools/dbt/models/marts/facts/CONTEXT.md) — Shares Geospatial Processing domain (haversine distance)
