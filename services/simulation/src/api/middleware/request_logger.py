"""HTTP access logging middleware for the simulation API.

Logs every non-health-check request with timing, user identity, and response status.
User identity is resolved from the X-API-Key header:

- Session keys (``sess_`` prefix) are looked up in Redis to retrieve email and role.
- The static admin key resolves to identity ``"admin"`` with role ``"admin"``.
- Missing or unrecognised keys resolve to ``"anonymous"`` with role ``"anonymous"``.

Logs are emitted under logger name ``api.access`` at INFO level using structured
``extra`` fields so they appear as top-level keys in the JSON formatter output.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

from api.session_store import get_session
from settings import get_settings

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from starlette.middleware.base import RequestResponseEndpoint
    from starlette.requests import Request
    from starlette.responses import Response

_SKIP_PATHS = frozenset({"/health", "/health/detailed"})

logger = logging.getLogger("api.access")


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Log every non-health-check HTTP request with user identity and timing.

    Each log record carries the following extra fields that the JSON formatter
    promotes to top-level keys:

    - ``method`` — HTTP verb (GET, POST, …)
    - ``path`` — Request path without query string
    - ``status_code`` — Response status code
    - ``duration_ms`` — Elapsed time in milliseconds (rounded to 2 decimal places)
    - ``user_identity`` — Email address for session keys, ``"admin"`` for the static
      key, or ``"anonymous"`` for unauthenticated requests
    - ``user_role`` — Role string from the session, or ``"admin"`` / ``"anonymous"``
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        user_identity, user_role = await _resolve_identity(request)

        logger.info(
            "%s %s %d",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "user_identity": user_identity,
                "user_role": user_role,
            },
        )

        return response


async def _resolve_identity(request: Request) -> tuple[str, str]:
    """Resolve user identity from the X-API-Key header.

    Returns a ``(user_identity, user_role)`` tuple. Never raises — any
    lookup failure falls back to ``("anonymous", "anonymous")``.
    """
    api_key = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
    if not api_key:
        return ("anonymous", "anonymous")

    if api_key.startswith("sess_"):
        try:
            redis_client: Redis[str] = request.app.state.redis_client
            session = await get_session(api_key, redis_client)
            if session is not None:
                return (session.email, session.role)
        except Exception:
            logger.debug("Redis session lookup failed during access logging", exc_info=True)
        return ("anonymous", "anonymous")

    settings = get_settings()
    if api_key == settings.api.key:
        return ("admin", "admin")

    return ("anonymous", "anonymous")
