"""Security headers middleware for HTTP responses."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all HTTP responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Content Security Policy - allows same-origin, WebSocket, inline styles, and data URIs
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "connect-src 'self' ws: wss:; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "script-src 'self'"
        )

        # HSTS - enforce HTTPS for 1 year including subdomains
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # X-Frame-Options - prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # X-Content-Type-Options - prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Referrer-Policy - control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy - restrict browser features
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        return response
