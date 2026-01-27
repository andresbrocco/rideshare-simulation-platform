"""Rate limiting configuration using slowapi."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


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
