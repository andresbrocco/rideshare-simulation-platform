import pytest
import respx
from httpx import Response

from src.geo.osrm_client import (
    NoRouteFoundError,
    OSRMClient,
    OSRMServiceError,
    OSRMTimeoutError,
    RouteResponse,
)


@pytest.fixture
def osrm_client() -> OSRMClient:
    return OSRMClient(base_url="http://localhost:5000")


@pytest.fixture
def valid_osrm_response() -> dict:
    return {
        "code": "Ok",
        "routes": [
            {
                "distance": 1234.5,
                "duration": 234.6,
                "geometry": "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
            }
        ],
        "waypoints": [
            {"location": [-46.63, -23.55], "name": ""},
            {"location": [-46.64, -23.56], "name": ""},
        ],
    }


async def test_route_request_valid(osrm_client: OSRMClient, valid_osrm_response: dict):
    async with respx.mock:
        route = respx.route(path__regex=r".*/route/v1/driving/.*").mock(
            return_value=Response(200, json=valid_osrm_response)
        )

        result = await osrm_client.get_route(
            origin=(-23.55, -46.63), destination=(-23.56, -46.64)
        )

        assert route.called
        assert isinstance(result, RouteResponse)
        assert result.distance_meters == 1234.5
        assert result.duration_seconds == 234.6
        assert result.osrm_code == "Ok"
        assert len(result.geometry) > 0


async def test_route_response_parsing(
    osrm_client: OSRMClient, valid_osrm_response: dict
):
    async with respx.mock:
        respx.route(path__regex=r".*/route/v1/driving/.*").mock(
            return_value=Response(200, json=valid_osrm_response)
        )

        result = await osrm_client.get_route(
            origin=(-23.55, -46.63), destination=(-23.56, -46.64)
        )

        assert result.osrm_code == "Ok"
        assert isinstance(result.distance_meters, float)
        assert isinstance(result.duration_seconds, float)
        assert isinstance(result.geometry, list)
        assert all(isinstance(coord, tuple) for coord in result.geometry)
        assert all(len(coord) == 2 for coord in result.geometry)


async def test_route_geometry_decoded():
    encoded = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
    from src.geo.osrm_client import decode_polyline

    coords = decode_polyline(encoded)

    assert len(coords) > 0
    assert all(isinstance(coord, tuple) for coord in coords)
    assert all(len(coord) == 2 for coord in coords)
    lat, lon = coords[0]
    assert -90 <= lat <= 90
    assert -180 <= lon <= 180


async def test_osrm_no_route_found(osrm_client: OSRMClient):
    async with respx.mock:
        no_route_response = {
            "code": "NoRoute",
            "message": "Could not find a route between points",
        }
        respx.route(path__regex=r".*/route/v1/driving/.*").mock(
            return_value=Response(200, json=no_route_response)
        )

        with pytest.raises(NoRouteFoundError):
            await osrm_client.get_route(origin=(-23.55, -46.63), destination=(0.0, 0.0))


async def test_osrm_server_error(osrm_client: OSRMClient):
    async with respx.mock:
        respx.route(path__regex=r".*/route/v1/driving/.*").mock(
            return_value=Response(500, text="Internal Server Error")
        )

        with pytest.raises(OSRMServiceError):
            await osrm_client.get_route(
                origin=(-23.55, -46.63), destination=(-23.56, -46.64)
            )


async def test_osrm_timeout(osrm_client: OSRMClient):
    import httpx

    async with respx.mock:
        respx.route(path__regex=r".*/route/v1/driving/.*").mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        with pytest.raises(OSRMTimeoutError):
            await osrm_client.get_route(
                origin=(-23.55, -46.63), destination=(-23.56, -46.64)
            )


def test_route_cache_key_generation(osrm_client: OSRMClient):
    key1 = osrm_client._generate_cache_key((-23.55, -46.63), (-23.56, -46.64))
    key2 = osrm_client._generate_cache_key((-23.55, -46.63), (-23.56, -46.64))

    assert key1 == key2
    assert isinstance(key1, str)
    assert len(key1) > 0


async def test_async_route_request(osrm_client: OSRMClient, valid_osrm_response: dict):
    async with respx.mock:
        respx.route(path__regex=r".*/route/v1/driving/.*").mock(
            return_value=Response(200, json=valid_osrm_response)
        )

        result = await osrm_client.get_route(
            origin=(-23.55, -46.63), destination=(-23.56, -46.64)
        )

        assert isinstance(result, RouteResponse)
        assert result.osrm_code == "Ok"


async def test_osrm_network_error(osrm_client: OSRMClient):
    import httpx

    async with respx.mock:
        respx.route(path__regex=r".*/route/v1/driving/.*").mock(
            side_effect=httpx.NetworkError("Connection failed")
        )

        with pytest.raises(OSRMServiceError):
            await osrm_client.get_route(
                origin=(-23.55, -46.63), destination=(-23.56, -46.64)
            )
