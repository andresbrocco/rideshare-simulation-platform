"""Unit tests for the session store module."""

from unittest.mock import AsyncMock, call

import pytest
from pydantic import ValidationError

from src.api.session_store import SessionData, create_session, delete_session, get_session

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Async Redis client mock with hset, expire, hgetall, and delete stubs."""
    client = AsyncMock()
    client.hset = AsyncMock(return_value=1)
    client.expire = AsyncMock(return_value=True)
    client.hgetall = AsyncMock(return_value={})
    client.delete = AsyncMock(return_value=1)
    return client


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_session_returns_sess_prefixed_key(mock_redis: AsyncMock) -> None:
    """create_session generates a key that starts with 'sess_'."""
    result = await create_session("a@b.com", "viewer", mock_redis)
    assert result.api_key.startswith("sess_")


@pytest.mark.asyncio
async def test_create_session_returns_session_data(mock_redis: AsyncMock) -> None:
    """Return value is a SessionData with the supplied email and role."""
    result = await create_session("a@b.com", "admin", mock_redis)
    assert isinstance(result, SessionData)
    assert result.email == "a@b.com"
    assert result.role == "admin"


@pytest.mark.asyncio
async def test_create_session_stores_in_redis(mock_redis: AsyncMock) -> None:
    """create_session calls hset with the correct hash key and fields."""
    result = await create_session("a@b.com", "viewer", mock_redis)

    expected_key = f"session:{result.api_key}"
    mock_redis.hset.assert_called_once()
    call_kwargs = mock_redis.hset.call_args
    assert call_kwargs[0][0] == expected_key
    mapping: dict[str, str] = call_kwargs[1]["mapping"]
    assert mapping["email"] == "a@b.com"
    assert mapping["role"] == "viewer"
    assert "expires_at" in mapping


@pytest.mark.asyncio
async def test_create_session_sets_ttl(mock_redis: AsyncMock) -> None:
    """create_session calls expire on the hash key with ttl_seconds."""
    result = await create_session("a@b.com", "viewer", mock_redis, ttl_seconds=3600)
    expected_key = f"session:{result.api_key}"
    mock_redis.expire.assert_called_once_with(expected_key, 3600)


@pytest.mark.asyncio
async def test_create_session_default_ttl_is_one_day(mock_redis: AsyncMock) -> None:
    """Default TTL is 86400 seconds (24 hours)."""
    result = await create_session("a@b.com", "viewer", mock_redis)
    expected_key = f"session:{result.api_key}"
    mock_redis.expire.assert_called_once_with(expected_key, 86400)


@pytest.mark.asyncio
async def test_create_session_keys_are_unique(mock_redis: AsyncMock) -> None:
    """Two consecutive calls produce different keys."""
    first = await create_session("a@b.com", "viewer", mock_redis)
    second = await create_session("a@b.com", "viewer", mock_redis)
    assert first.api_key != second.api_key


# ---------------------------------------------------------------------------
# get_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_session_returns_data(mock_redis: AsyncMock) -> None:
    """get_session returns a populated SessionData for a valid sess_ key."""
    from datetime import UTC, datetime, timedelta

    expires_at = datetime.now(UTC) + timedelta(hours=1)
    mock_redis.hgetall.return_value = {
        "email": "a@b.com",
        "role": "viewer",
        "expires_at": expires_at.isoformat(),
    }

    result = await get_session("sess_test", mock_redis)

    assert result is not None
    assert result.api_key == "sess_test"
    assert result.email == "a@b.com"
    assert result.role == "viewer"
    mock_redis.hgetall.assert_called_once_with("session:sess_test")


@pytest.mark.asyncio
async def test_get_session_missing_returns_none(mock_redis: AsyncMock) -> None:
    """get_session returns None when the Redis hash is absent (cache miss)."""
    mock_redis.hgetall.return_value = {}

    result = await get_session("sess_missingkey", mock_redis)

    assert result is None
    mock_redis.hgetall.assert_called_once_with("session:sess_missingkey")


@pytest.mark.asyncio
async def test_get_session_non_sess_prefix_returns_none(mock_redis: AsyncMock) -> None:
    """get_session returns None for non-sess_ keys without querying Redis."""
    result = await get_session("admin-key-abc", mock_redis)

    assert result is None
    mock_redis.hgetall.assert_not_called()


@pytest.mark.asyncio
async def test_get_session_static_key_skipped(mock_redis: AsyncMock) -> None:
    """A plain API_KEY value (no sess_ prefix) is skipped without a Redis round-trip."""
    result = await get_session("test-api-key", mock_redis)

    assert result is None
    mock_redis.hgetall.assert_not_called()


@pytest.mark.asyncio
async def test_get_session_admin_role_round_trips(mock_redis: AsyncMock) -> None:
    """get_session correctly deserialises the 'admin' role literal."""
    from datetime import UTC, datetime, timedelta

    expires_at = datetime.now(UTC) + timedelta(hours=8)
    mock_redis.hgetall.return_value = {
        "email": "admin@b.com",
        "role": "admin",
        "expires_at": expires_at.isoformat(),
    }

    result = await get_session("sess_adminkey", mock_redis)

    assert result is not None
    assert result.role == "admin"


# ---------------------------------------------------------------------------
# delete_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_session_calls_redis_delete(mock_redis: AsyncMock) -> None:
    """delete_session calls redis.delete with the correct hash key."""
    await delete_session("sess_abc", mock_redis)
    mock_redis.delete.assert_called_once_with("session:sess_abc")


@pytest.mark.asyncio
async def test_delete_session_non_sess_key_still_deletes(mock_redis: AsyncMock) -> None:
    """delete_session issues the delete regardless of key prefix (caller's responsibility)."""
    await delete_session("some-other-key", mock_redis)
    mock_redis.delete.assert_called_once_with("session:some-other-key")


# ---------------------------------------------------------------------------
# SessionData model
# ---------------------------------------------------------------------------


def test_session_data_is_frozen() -> None:
    """SessionData instances are immutable (frozen Pydantic model)."""
    from datetime import UTC, datetime

    data = SessionData(
        api_key="sess_abc",
        email="a@b.com",
        role="viewer",
        expires_at=datetime.now(UTC),
    )
    with pytest.raises(ValidationError):
        data.email = "changed@b.com"  # type: ignore[misc]
