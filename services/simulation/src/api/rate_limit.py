"""Rate limiting configuration using slowapi."""

import time
from collections import defaultdict

from opentelemetry import metrics
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

meter = metrics.get_meter("simulation")

rate_limit_hits = meter.create_counter(
    name="api_rate_limit_hits_total",
    description="Total API requests rejected by rate limiting",
    unit="1",
)


def get_api_key_or_ip(request: Request) -> str:
    """Rate limit by API key if present, otherwise by IP.

    This ensures each client (identified by their API key) gets their own
    rate limit quota. Falls back to IP address for unauthenticated requests.
    """
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"key:{api_key}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=get_api_key_or_ip)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Custom 429 handler with OTel tracking and Retry-After header.

    Builds the response manually instead of using slowapi's default handler
    because headers_enabled=True is incompatible with FastAPI's decorator
    approach (causes 500 on success responses without SlowAPIMiddleware).
    """
    rate_limit_hits.add(
        1,
        {"endpoint": request.url.path, "method": request.method},
    )

    # Extract retry-after from the exception detail (e.g. "Rate limit exceeded: 10 per 1 minute")
    retry_after = str(exc.detail)

    # slowapi stores parsed rate limit info on request state when available
    view_rate_limit = getattr(request.state, "view_rate_limit", None)
    if view_rate_limit:
        # view_rate_limit is a string like "10/minute" — extract the window
        window_map = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
        for unit, seconds in window_map.items():
            if unit in view_rate_limit:
                retry_after = str(seconds)
                break

    response = JSONResponse(
        status_code=429,
        content={"error": str(exc.detail)},
    )
    response.headers["retry-after"] = retry_after
    return response


class WebSocketRateLimiter:
    """Simple sliding-window rate limiter for WebSocket connections."""

    def __init__(self, max_connections: int, window_seconds: int) -> None:
        self.max_connections = max_connections
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def is_limited(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        self._attempts[key] = [t for t in self._attempts[key] if t > cutoff]
        if len(self._attempts[key]) >= self.max_connections:
            return True
        self._attempts[key].append(now)
        return False


ws_limiter = WebSocketRateLimiter(max_connections=5, window_seconds=60)
