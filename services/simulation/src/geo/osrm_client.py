import time

import httpx
import polyline
import requests
from pydantic import BaseModel

from core.exceptions import (
    NetworkError,
    ServiceUnavailableError,
    ValidationError,
)
from metrics import get_metrics_collector


class RouteResponse(BaseModel):
    distance_meters: float
    duration_seconds: float
    geometry: list[tuple[float, float]]
    osrm_code: str


class NoRouteFoundError(ValidationError):
    """No route found between coordinates. Inherits from ValidationError (non-retryable)."""

    pass


class OSRMServiceError(ServiceUnavailableError):
    """OSRM service error (5xx). Inherits from ServiceUnavailableError (retryable)."""

    pass


class OSRMTimeoutError(NetworkError):
    """OSRM request timeout. Inherits from NetworkError (retryable)."""

    pass


def decode_polyline(encoded: str, precision: int = 5) -> list[tuple[float, float]]:
    """Decode polyline string to list of (lat, lon) tuples."""
    coords = polyline.decode(encoded, precision)
    return [(lat, lon) for lat, lon in coords]


class OSRMClient:
    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def get_route(
        self, origin: tuple[float, float], destination: tuple[float, float]
    ) -> RouteResponse:
        """Get route between two coordinates using OSRM."""
        origin_lat, origin_lon = origin
        dest_lat, dest_lon = destination

        url = (
            f"{self.base_url}/route/v1/driving/"
            f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        )
        params = {"overview": "full", "geometries": "polyline"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)

                if response.status_code >= 500:
                    raise OSRMServiceError(f"OSRM server error: {response.status_code}")

                data = response.json()

                if data.get("code") == "NoRoute":
                    raise NoRouteFoundError("No route found between coordinates")

                route = data["routes"][0]
                return RouteResponse(
                    distance_meters=float(route["distance"]),
                    duration_seconds=float(route["duration"]),
                    geometry=decode_polyline(route["geometry"]),
                    osrm_code=data["code"],
                )

        except httpx.TimeoutException as e:
            raise OSRMTimeoutError(f"Request timed out after {self.timeout}s") from e
        except httpx.NetworkError as e:
            raise OSRMServiceError(f"Network error: {e}") from e

    def get_route_sync(
        self, origin: tuple[float, float], destination: tuple[float, float]
    ) -> RouteResponse:
        """Synchronous route fetching for use in SimPy thread.

        Uses the requests library instead of httpx to avoid blocking the asyncio event loop.
        This is intended for use in SimPy processes where asyncio.run() would block.
        """
        origin_lat, origin_lon = origin
        dest_lat, dest_lon = destination

        url = (
            f"{self.base_url}/route/v1/driving/"
            f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        )
        params = {"overview": "full", "geometries": "polyline"}

        start_time = time.perf_counter()
        collector = get_metrics_collector()
        try:
            response = requests.get(url, params=params, timeout=self.timeout)

            if response.status_code >= 500:
                collector.record_error("osrm", f"server_error_{response.status_code}")
                raise OSRMServiceError(f"OSRM server error: {response.status_code}")

            data = response.json()

            if data.get("code") == "NoRoute":
                collector.record_error("osrm", "no_route")
                raise NoRouteFoundError("No route found between coordinates")

            route = data["routes"][0]
            result = RouteResponse(
                distance_meters=float(route["distance"]),
                duration_seconds=float(route["duration"]),
                geometry=decode_polyline(route["geometry"]),
                osrm_code=data["code"],
            )

            # Record successful latency
            latency_ms = (time.perf_counter() - start_time) * 1000
            collector.record_latency("osrm", latency_ms)

            return result

        except requests.Timeout as e:
            collector.record_error("osrm", "timeout")
            raise OSRMTimeoutError(f"Request timed out after {self.timeout}s") from e
        except requests.RequestException as e:
            collector.record_error("osrm", "network_error")
            raise OSRMServiceError(f"Network error: {e}") from e

    def _generate_cache_key(
        self, origin: tuple[float, float], destination: tuple[float, float]
    ) -> str:
        """Generate cache key for route request."""
        origin_lat, origin_lon = origin
        dest_lat, dest_lon = destination
        return f"{origin_lat:.6f},{origin_lon:.6f}-{dest_lat:.6f},{dest_lon:.6f}"
