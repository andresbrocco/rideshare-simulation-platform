"""Session store for API key lifecycle — generates, validates, and invalidates session keys.

Session keys are stored as Redis hashes at ``session:{api_key}`` with a TTL for automatic
eviction. The module exposes three free functions that each accept a Redis async client as
an explicit parameter so they can be called from any request context without coupling to
app.state directly.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from redis.asyncio import Redis

_KEY_PREFIX = "sess_"
_REDIS_NAMESPACE = "session"


class SessionData(BaseModel):
    """Immutable snapshot of an active session."""

    model_config = ConfigDict(frozen=True)

    api_key: str
    email: str
    role: Literal["admin", "viewer"]
    expires_at: datetime


def _redis_key(api_key: str) -> str:
    """Return the Redis hash key for *api_key*."""
    return f"{_REDIS_NAMESPACE}:{api_key}"


async def create_session(
    email: str,
    role: Literal["admin", "viewer"],
    redis: Redis[str],
    *,
    ttl_seconds: int = 86400,
) -> SessionData:
    """Generate a new session key, persist it in Redis, and return the SessionData.

    The key is a ``sess_`` prefixed URL-safe random string. A Redis TTL is set so
    that the hash is evicted automatically when the session expires.
    """
    api_key = f"{_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)

    await redis.hset(
        _redis_key(api_key),
        mapping={
            "email": email,
            "role": role,
            "expires_at": expires_at.isoformat(),
        },
    )
    await redis.expire(_redis_key(api_key), ttl_seconds)

    return SessionData(api_key=api_key, email=email, role=role, expires_at=expires_at)


async def get_session(api_key: str, redis: Redis[str]) -> SessionData | None:
    """Look up an active session by *api_key*.

    Returns ``None`` immediately for keys that do not start with the ``sess_`` prefix
    (e.g. the static admin key) so Redis is never queried for those. Returns ``None``
    on a cache miss — the TTL-based eviction means an expired key is simply absent.
    """
    if not api_key.startswith(_KEY_PREFIX):
        return None

    data: dict[str, str] = await redis.hgetall(_redis_key(api_key))
    if not data:
        return None

    return SessionData.model_validate(
        {
            "api_key": api_key,
            "email": data["email"],
            "role": data["role"],
            "expires_at": data["expires_at"],
        }
    )


async def delete_session(api_key: str, redis: Redis[str]) -> None:
    """Explicitly invalidate *api_key* by removing its Redis hash."""
    await redis.delete(_redis_key(api_key))
