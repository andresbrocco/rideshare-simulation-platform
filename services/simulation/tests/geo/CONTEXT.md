# CONTEXT.md — tests/geo

## Purpose

Unit tests for the simulation's geospatial layer, covering zone assignment, route caching, OSRM client integration, distance calculations, GPS noise simulation, and GeoJSON zone loading.

## Responsibility Boundaries

- **Owns**: Behavioral verification of all modules under `src/geo/`
- **Delegates to**: Fixtures in `tests/fixtures/` for sample GeoJSON data (`sample_zones.geojson`, `invalid_zones.geojson`)
- **Does not handle**: Integration tests against a live OSRM service or real map data; those belong in the integration test suite

## Key Concepts

- **H3 cache key granularity**: Both `ZoneAssignmentService` and `RouteCacheService` use H3 resolution 9 as the cache key, meaning coordinates within ~50m of each other share the same cache entry. Tests explicitly verify this property and distinguish it from the distance used for arrival detection (also 50m by default).
- **Zone fallback tiers**: `get_zone_id` and `find_zone_for_location` have two distinct fallback behaviors. Points outside all zone polygons but within 50km return the nearest centroid silently. Points beyond 50km raise `InvalidCoordinatesError`. Tests cover all three cases (inside polygon, nearby fallback, far-field error).
- **Bounding-box pre-check**: `is_within_proximity` applies a latitude/longitude bounding box fast-reject before running Haversine. Tests verify no false negatives at diagonal approaches and confirm the conservative longitude threshold (using the same degree value as latitude, slightly over-inclusive at São Paulo's latitude ~cos 0.917).
- **Async OSRM tests**: `test_osrm_client.py` uses `respx` for httpx mocking and writes bare `async def` test functions without `@pytest.mark.asyncio`; the project's pytest configuration must apply asyncio mode automatically.

## Non-Obvious Details

- `test_zone_loader.py` verifies that `ZoneLoader._polygons` and `_strtree` are populated at construction time (not lazily), which matters for thread safety in the SimPy engine.
- Traffic multiplier tests use exact hour integers (`hour=8`, `hour=18`) and fractional hours (`hour=7.5`) interchangeably; the `TrafficModel` must accept floats.
- GPS noise distribution tests use 1,000 samples and assert the mean offset falls within ±5m of the configured `noise_meters` value, making them probabilistically sensitive — they are marked `@pytest.mark.slow` to allow exclusion from fast test runs.
- `test_route_cache.py` verifies LRU eviction by filling a cache of `maxsize=3` and asserting the first inserted entry is a miss after the fourth entry is added, confirming standard LRU (not LFU) semantics.
