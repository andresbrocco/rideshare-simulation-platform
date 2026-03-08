"""Authentication and authorisation dependencies for the simulation API.

Provides two authentication paths:
- Session keys (prefix ``sess_``) are looked up in Redis via :func:`api.session_store.get_session`.
- All other keys are compared against the static admin API key from settings.

Both paths return an :class:`AuthContext` dataclass on success, or raise
:exc:`fastapi.HTTPException` with status 401 on failure.

Role enforcement is handled by the :func:`require_admin` dependency, which
reads the :class:`AuthContext` produced by :func:`verify_api_key` and raises
HTTP 403 when the caller's role is not ``"admin"``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Header, HTTPException, Request

from api.session_store import SessionData
from api.session_store import get_session as _store_get_session
from settings import get_settings

if TYPE_CHECKING:
    from redis.asyncio import Redis


@dataclass(frozen=True)
class AuthContext:
    """Immutable authentication context returned by :func:`verify_api_key`."""

    role: str
    email: str


async def get_session(api_key: str, request: Request) -> SessionData | None:
    """Look up a session key by extracting the Redis client from the request state.

    This thin wrapper around :func:`api.session_store.get_session` is a stable
    indirection point that test patches target via ``api.auth.get_session``. The
    wrapper extracts ``redis_client`` from ``request.app.state`` so that tests
    calling :func:`verify_api_key` directly with ``request=None`` only need to
    patch *this* function — they never have to construct a real
    :class:`fastapi.Request`.
    """
    redis_client: Redis[str] = request.app.state.redis_client
    return await _store_get_session(api_key, redis_client)


async def verify_api_key(
    x_api_key: Annotated[str, Header()],
    request: Request,
) -> AuthContext:
    """FastAPI dependency that validates the ``X-API-Key`` header.

    Two validation paths:
    1. **Session key** (``sess_`` prefix): looks up the key in Redis via
       :func:`get_session` and returns the stored role/email.
    2. **Static admin key**: compares against ``settings.api.key`` and returns
       ``role="admin"`` with ``email="admin"``.

    Raises:
        HTTPException: 401 if the key is invalid or the session has expired.
    """
    settings = get_settings()

    if x_api_key.startswith("sess_"):
        # Session key path — delegate to get_session which handles redis extraction.
        # Tests that call this dependency directly with request=None must patch
        # ``api.auth.get_session`` so redis is never accessed.
        session = await get_session(x_api_key, request)
        if session is None:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return AuthContext(role=session.role, email=session.email)

    # Static admin key path
    if x_api_key != settings.api.key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return AuthContext(role="admin", email="admin")


AuthContextDep = Annotated[AuthContext, Depends(verify_api_key)]


async def require_admin(
    auth: Annotated[AuthContext, Depends(verify_api_key)],
) -> None:
    """FastAPI dependency that enforces admin-only access.

    Reads the :class:`AuthContext` returned by :func:`verify_api_key` and
    raises HTTP 403 when the caller's role is not ``"admin"``.  Attach this
    as an additional parameter on route functions that must be restricted to
    administrators:

    .. code-block:: python

        @router.post("/start")
        def start_simulation(
            _: Annotated[None, Depends(require_admin)],
            ...
        ) -> ...:
            ...

    The leading underscore signals that the parameter is used only for its
    side-effect (the role check) and carries no meaningful value.

    Raises:
        HTTPException: 403 when ``auth.role != "admin"``.
    """
    if auth.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
