from unittest.mock import AsyncMock, Mock

import h3
import pytest

from src.geo.osrm_client import OSRMClient, RouteResponse
from src.geo.route_cache import RouteCacheService


@pytest.fixture
def mock_osrm_client():
    client = AsyncMock(spec=OSRMClient)
    client.get_route.return_value = RouteResponse(
        distance_meters=1500.0,
        duration_seconds=180.0,
        geometry=[(-23.55, -46.63), (-23.56, -46.64)],
        osrm_code="Ok",
    )
    return client


@pytest.fixture
def route_cache_service(mock_osrm_client):
    return RouteCacheService(osrm_client=mock_osrm_client, maxsize=10)


def test_h3_cell_from_coords():
    lat, lng = -23.55, -46.63
    resolution = 9
    h3_cell = h3.latlng_to_cell(lat, lng, resolution)

    assert isinstance(h3_cell, str)
    assert len(h3_cell) == 15
    assert h3_cell.startswith("89")


def test_cache_key_generation(route_cache_service):
    origin = (-23.55, -46.63)
    destination = (-23.56, -46.64)

    key = route_cache_service._generate_cache_key(origin, destination)

    origin_h3 = h3.latlng_to_cell(origin[0], origin[1], 9)
    dest_h3 = h3.latlng_to_cell(destination[0], destination[1], 9)
    expected_key = f"{origin_h3}|{dest_h3}"

    assert key == expected_key
    assert "|" in key


@pytest.mark.asyncio
async def test_cache_miss_fetches_route(route_cache_service, mock_osrm_client):
    origin = (-23.55, -46.63)
    destination = (-23.56, -46.64)

    route = await route_cache_service.get_route(origin, destination)

    assert route.distance_meters == 1500.0
    assert route.duration_seconds == 180.0
    mock_osrm_client.get_route.assert_called_once_with(origin, destination)


@pytest.mark.asyncio
async def test_cache_hit_skips_osrm(route_cache_service, mock_osrm_client):
    origin = (-23.55, -46.63)
    destination = (-23.56, -46.64)

    # First call - cache miss
    route1 = await route_cache_service.get_route(origin, destination)
    assert mock_osrm_client.get_route.call_count == 1

    # Second call - cache hit
    route2 = await route_cache_service.get_route(origin, destination)
    assert mock_osrm_client.get_route.call_count == 1  # Not called again

    assert route1.distance_meters == route2.distance_meters


@pytest.mark.asyncio
async def test_same_h3_cells_cache_hit(route_cache_service, mock_osrm_client):
    # Two coordinates ~50m apart should map to same H3 cells at resolution 9
    origin1 = (-23.550000, -46.630000)
    destination1 = (-23.560000, -46.640000)

    # Slightly different coords in same H3 cells
    origin2 = (-23.550030, -46.630030)  # ~50m offset
    destination2 = (-23.560030, -46.640030)

    # Verify they map to same H3 cells
    origin_h3_1 = h3.latlng_to_cell(origin1[0], origin1[1], 9)
    origin_h3_2 = h3.latlng_to_cell(origin2[0], origin2[1], 9)
    dest_h3_1 = h3.latlng_to_cell(destination1[0], destination1[1], 9)
    dest_h3_2 = h3.latlng_to_cell(destination2[0], destination2[1], 9)

    assert origin_h3_1 == origin_h3_2
    assert dest_h3_1 == dest_h3_2

    # First request
    await route_cache_service.get_route(origin1, destination1)
    assert mock_osrm_client.get_route.call_count == 1

    # Second request with nearby coords - should hit cache
    await route_cache_service.get_route(origin2, destination2)
    assert mock_osrm_client.get_route.call_count == 1


@pytest.mark.asyncio
async def test_different_h3_cells_cache_miss(route_cache_service, mock_osrm_client):
    # Two coordinates ~500m apart should map to different H3 cells
    origin1 = (-23.550000, -46.630000)
    destination = (-23.560000, -46.640000)

    origin2 = (-23.555000, -46.635000)  # ~500m offset

    # Verify they map to different H3 cells
    origin_h3_1 = h3.latlng_to_cell(origin1[0], origin1[1], 9)
    origin_h3_2 = h3.latlng_to_cell(origin2[0], origin2[1], 9)

    assert origin_h3_1 != origin_h3_2

    # First request
    await route_cache_service.get_route(origin1, destination)
    assert mock_osrm_client.get_route.call_count == 1

    # Second request with different coords - should miss cache
    await route_cache_service.get_route(origin2, destination)
    assert mock_osrm_client.get_route.call_count == 2


@pytest.mark.asyncio
async def test_lru_eviction():
    mock_client = AsyncMock(spec=OSRMClient)
    cache_service = RouteCacheService(osrm_client=mock_client, maxsize=3)

    # Create different routes
    routes = [
        ((-23.55, -46.63), (-23.56, -46.64)),
        ((-23.57, -46.65), (-23.58, -46.66)),
        ((-23.59, -46.67), (-23.60, -46.68)),
        ((-23.61, -46.69), (-23.62, -46.70)),
    ]

    # Mock different responses for each
    mock_client.get_route.return_value = RouteResponse(
        distance_meters=1000.0,
        duration_seconds=120.0,
        geometry=[(-23.55, -46.63)],
        osrm_code="Ok",
    )

    # Fill cache with 3 routes
    for origin, dest in routes[:3]:
        await cache_service.get_route(origin, dest)

    assert mock_client.get_route.call_count == 3

    # Add 4th route - should evict oldest
    await cache_service.get_route(routes[3][0], routes[3][1])
    assert mock_client.get_route.call_count == 4

    # First route should have been evicted
    await cache_service.get_route(routes[0][0], routes[0][1])
    assert mock_client.get_route.call_count == 5  # Cache miss


@pytest.mark.asyncio
async def test_cache_stats_tracking(route_cache_service, mock_osrm_client):
    origin1 = (-23.55, -46.63)
    destination1 = (-23.56, -46.64)
    origin2 = (-23.57, -46.65)
    destination2 = (-23.58, -46.66)

    # First request - miss
    await route_cache_service.get_route(origin1, destination1)
    stats = route_cache_service.get_cache_stats()
    assert stats["requests"] == 1
    assert stats["misses"] == 1
    assert stats["hits"] == 0

    # Second request same route - hit
    await route_cache_service.get_route(origin1, destination1)
    stats = route_cache_service.get_cache_stats()
    assert stats["requests"] == 2
    assert stats["misses"] == 1
    assert stats["hits"] == 1
    assert stats["hit_rate"] == 0.5

    # Third request different route - miss
    await route_cache_service.get_route(origin2, destination2)
    stats = route_cache_service.get_cache_stats()
    assert stats["requests"] == 3
    assert stats["misses"] == 2
    assert stats["hits"] == 1
    assert round(stats["hit_rate"], 2) == 0.33


@pytest.mark.asyncio
async def test_cache_clear(route_cache_service, mock_osrm_client):
    origin = (-23.55, -46.63)
    destination = (-23.56, -46.64)

    # Add route to cache
    await route_cache_service.get_route(origin, destination)
    stats_before = route_cache_service.get_cache_stats()
    assert stats_before["requests"] == 1
    assert stats_before["misses"] == 1

    # Clear cache
    route_cache_service.clear_cache()

    # Stats should be reset
    stats_after = route_cache_service.get_cache_stats()
    assert stats_after["requests"] == 0
    assert stats_after["hits"] == 0
    assert stats_after["misses"] == 0

    # Next request should miss again
    await route_cache_service.get_route(origin, destination)
    assert mock_osrm_client.get_route.call_count == 2
