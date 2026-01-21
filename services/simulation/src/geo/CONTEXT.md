# CONTEXT.md — Geo

## Purpose

Handles all geospatial operations for the ride-sharing simulation including route calculation, zone assignment, GPS simulation, and traffic modeling. Provides the geographic foundation that enables realistic driver-rider matching, trip execution, and surge pricing based on supply/demand by zone.

## Responsibility Boundaries

- **Owns**: Route calculation and caching via OSRM, zone assignment with point-in-polygon detection, GPS position interpolation and noise simulation, time-of-day traffic multipliers, Haversine distance calculations
- **Delegates to**: OSRM service for actual route computation, Shapely for geometric operations, H3 for spatial indexing
- **Does not handle**: Driver/rider matching logic (handled by matching module), trip state management (handled by trips module), surge pricing calculation (handled by matching module)

## Key Concepts

- **H3 Spatial Indexing**: Uses Uber's H3 at resolution 9 (~174m edge) as cache keys for both route caching and zone assignment, reducing expensive operations
- **Route Caching**: LRU cache with H3-based keys prevents redundant OSRM calls for similar origin-destination pairs (maxsize: 10,000 routes)
- **Zone Assignment**: Two-phase lookup (point-in-polygon first, nearest centroid fallback within 50km) ensures all valid coordinates map to a zone
- **GPS Noise**: Gaussian noise clamped to 15m max with 5% dropout probability simulates realistic GPS inaccuracy
- **Traffic Multipliers**: Sigmoid-smoothed time-of-day adjustments (1.4x rush hour, 0.85x night) applied to OSRM base durations
- **Coordinate Ordering**: OSRM and GeoJSON use (lon, lat) ordering; internal operations use (lat, lon) — careful conversion required

## Non-Obvious Details

**Synchronous OSRM Client**: The `get_route_sync()` method exists specifically for SimPy processes, which run in a separate thread and cannot use `asyncio.run()` without blocking the event loop. Uses `requests` library instead of `httpx`.

**Zone Assignment Cache**: ZoneAssignmentService pre-builds Shapely polygons at initialization for fast point-in-polygon tests, then caches results by H3 cell to avoid repeated geometric operations.

**Traffic Model Wraparound**: Night traffic period (10:30 PM - 5:30 AM) requires special handling for midnight wraparound, calculating distance differently based on whether hour > 12.

**Cache Statistics**: Both RouteCacheService and ZoneAssignmentService track hits/misses/requests for observability, accessible via `get_cache_stats()` for monitoring cache effectiveness.

**GPS Interpolation**: Position calculation along a polyline walks through segments accumulating distance until target progress is reached, then linearly interpolates within that segment for smooth movement.
