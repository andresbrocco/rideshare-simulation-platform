from collections import OrderedDict

import h3

from src.geo.osrm_client import OSRMClient, RouteResponse


class RouteCacheService:
    def __init__(self, osrm_client: OSRMClient, maxsize: int = 10000):
        self.osrm_client = osrm_client
        self.maxsize = maxsize
        self.cache: OrderedDict[str, RouteResponse] = OrderedDict()
        self.requests = 0
        self.hits = 0
        self.misses = 0

    def _generate_cache_key(
        self, origin: tuple[float, float], destination: tuple[float, float]
    ) -> str:
        origin_lat, origin_lon = origin
        dest_lat, dest_lon = destination

        origin_h3 = h3.latlng_to_cell(origin_lat, origin_lon, 9)
        dest_h3 = h3.latlng_to_cell(dest_lat, dest_lon, 9)

        return f"{origin_h3}|{dest_h3}"

    async def get_route(
        self, origin: tuple[float, float], destination: tuple[float, float]
    ) -> RouteResponse:
        self.requests += 1
        cache_key = self._generate_cache_key(origin, destination)

        if cache_key in self.cache:
            self.hits += 1
            self.cache.move_to_end(cache_key)
            return self.cache[cache_key]

        self.misses += 1
        route = await self.osrm_client.get_route(origin, destination)

        self.cache[cache_key] = route

        if len(self.cache) > self.maxsize:
            self.cache.popitem(last=False)

        return route

    def get_cache_stats(self) -> dict[str, float | int]:
        hit_rate = self.hits / self.requests if self.requests > 0 else 0.0
        return {
            "requests": self.requests,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "cache_size": len(self.cache),
        }

    def clear_cache(self) -> None:
        self.cache.clear()
        self.requests = 0
        self.hits = 0
        self.misses = 0
