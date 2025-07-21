import httpx
import polyline
from pydantic import BaseModel


class RouteResponse(BaseModel):
    distance_meters: float
    duration_seconds: float
    geometry: list[tuple[float, float]]
    osrm_code: str


class NoRouteFoundError(Exception):
    pass


class OSRMServiceError(Exception):
    pass


class OSRMTimeoutError(Exception):
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
            f"{self.base_url}/route/v1/driving/" f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
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

    def _generate_cache_key(
        self, origin: tuple[float, float], destination: tuple[float, float]
    ) -> str:
        """Generate cache key for route request."""
        origin_lat, origin_lon = origin
        dest_lat, dest_lon = destination
        return f"{origin_lat:.6f},{origin_lon:.6f}-{dest_lat:.6f},{dest_lon:.6f}"
