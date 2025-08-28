import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_connection_manager():
    """Mock WebSocket connection manager."""
    manager = AsyncMock()
    manager.broadcast = AsyncMock()
    manager.active_connections = set()
    return manager


@pytest.fixture
def mock_redis_client_for_pubsub():
    """Mock Redis client for pubsub tests."""
    return MagicMock()


def create_pubsub_mock(messages):
    """Helper to create a pubsub mock with given messages."""
    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()
    idx = [0]

    async def mock_listen():
        while idx[0] < len(messages):
            yield messages[idx[0]]
            idx[0] += 1
        while True:
            await asyncio.sleep(1)

    pubsub.listen = mock_listen
    return pubsub


@pytest.mark.asyncio
async def test_redis_subscribe_on_startup(mock_redis_client_for_pubsub, mock_connection_manager):
    """Subscribes to all channels on startup."""
    pubsub = create_pubsub_mock([])
    mock_redis_client_for_pubsub.pubsub.return_value = pubsub

    from api.redis_subscriber import RedisSubscriber

    subscriber = RedisSubscriber(mock_redis_client_for_pubsub, mock_connection_manager)

    await subscriber.start()
    await asyncio.sleep(0.02)

    pubsub.subscribe.assert_called_once_with(
        "driver-updates", "rider-updates", "trip-updates", "surge-updates"
    )

    await subscriber.stop()


@pytest.mark.asyncio
async def test_fanout_driver_update(mock_redis_client_for_pubsub, mock_connection_manager):
    """Fans out driver update to all clients."""
    messages = [{"type": "message", "data": '{"driver_id": "d123", "status": "online"}'}]
    pubsub = create_pubsub_mock(messages)
    mock_redis_client_for_pubsub.pubsub.return_value = pubsub

    from api.redis_subscriber import RedisSubscriber

    subscriber = RedisSubscriber(mock_redis_client_for_pubsub, mock_connection_manager)

    await subscriber.start()
    await asyncio.sleep(0.02)

    mock_connection_manager.broadcast.assert_called_with({"driver_id": "d123", "status": "online"})

    await subscriber.stop()


@pytest.mark.asyncio
async def test_fanout_trip_update(mock_redis_client_for_pubsub, mock_connection_manager):
    """Fans out trip update to all clients."""
    messages = [{"type": "message", "data": '{"trip_id": "t456", "state": "STARTED"}'}]
    pubsub = create_pubsub_mock(messages)
    mock_redis_client_for_pubsub.pubsub.return_value = pubsub

    from api.redis_subscriber import RedisSubscriber

    subscriber = RedisSubscriber(mock_redis_client_for_pubsub, mock_connection_manager)

    await subscriber.start()
    await asyncio.sleep(0.02)

    mock_connection_manager.broadcast.assert_called_with({"trip_id": "t456", "state": "STARTED"})

    await subscriber.stop()


@pytest.mark.asyncio
async def test_fanout_surge_update(mock_redis_client_for_pubsub, mock_connection_manager):
    """Fans out surge update to all clients."""
    messages = [{"type": "message", "data": '{"zone_id": "z1", "multiplier": 1.5}'}]
    pubsub = create_pubsub_mock(messages)
    mock_redis_client_for_pubsub.pubsub.return_value = pubsub

    from api.redis_subscriber import RedisSubscriber

    subscriber = RedisSubscriber(mock_redis_client_for_pubsub, mock_connection_manager)

    await subscriber.start()
    await asyncio.sleep(0.02)

    mock_connection_manager.broadcast.assert_called_with({"zone_id": "z1", "multiplier": 1.5})

    await subscriber.stop()


@pytest.mark.asyncio
async def test_fanout_multiple_clients(mock_redis_client_for_pubsub, mock_connection_manager):
    """Broadcasts to all connected clients."""
    ws1, ws2, ws3 = AsyncMock(), AsyncMock(), AsyncMock()
    mock_connection_manager.active_connections = {ws1, ws2, ws3}

    messages = [{"type": "message", "data": '{"test": "data"}'}]
    pubsub = create_pubsub_mock(messages)
    mock_redis_client_for_pubsub.pubsub.return_value = pubsub

    from api.redis_subscriber import RedisSubscriber

    subscriber = RedisSubscriber(mock_redis_client_for_pubsub, mock_connection_manager)

    await subscriber.start()
    await asyncio.sleep(0.02)

    mock_connection_manager.broadcast.assert_called_once_with({"test": "data"})

    await subscriber.stop()


@pytest.mark.asyncio
async def test_redis_reconnect_on_disconnect(mock_redis_client_for_pubsub, mock_connection_manager):
    """Reconnects after connection loss."""
    import redis.asyncio as redis

    pubsub_call_count = [0]

    def create_pubsub():
        pubsub_call_count[0] += 1
        pubsub = MagicMock()
        pubsub.subscribe = AsyncMock()

        async def mock_listen():
            if pubsub_call_count[0] == 1:
                raise redis.ConnectionError("Connection lost")
            yield {"type": "message", "data": '{"reconnected": true}'}
            while True:
                await asyncio.sleep(1)

        pubsub.listen = mock_listen
        return pubsub

    mock_redis_client_for_pubsub.pubsub = create_pubsub

    from api.redis_subscriber import RedisSubscriber

    subscriber = RedisSubscriber(mock_redis_client_for_pubsub, mock_connection_manager)
    subscriber.reconnect_delay = 0.01

    await subscriber.start()
    await asyncio.sleep(0.1)

    assert pubsub_call_count[0] >= 2

    await subscriber.stop()


@pytest.mark.asyncio
async def test_parse_redis_message(mock_redis_client_for_pubsub, mock_connection_manager):
    """Parses JSON from Redis message."""
    messages = [
        {
            "type": "message",
            "data": '{"driver_id": "d1", "location": [1.0, 2.0], "status": "online"}',
        }
    ]
    pubsub = create_pubsub_mock(messages)
    mock_redis_client_for_pubsub.pubsub.return_value = pubsub

    from api.redis_subscriber import RedisSubscriber

    subscriber = RedisSubscriber(mock_redis_client_for_pubsub, mock_connection_manager)

    await subscriber.start()
    await asyncio.sleep(0.02)

    expected = {"driver_id": "d1", "location": [1.0, 2.0], "status": "online"}
    mock_connection_manager.broadcast.assert_called_with(expected)

    await subscriber.stop()


@pytest.mark.asyncio
async def test_subscription_task_lifecycle(mock_redis_client_for_pubsub, mock_connection_manager):
    """Task starts on startup and stops on shutdown."""
    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()
    mock_redis_client_for_pubsub.pubsub.return_value = pubsub

    async def mock_listen():
        while True:
            await asyncio.sleep(0.1)
            yield {"type": "subscribe"}

    pubsub.listen = mock_listen

    from api.redis_subscriber import RedisSubscriber

    subscriber = RedisSubscriber(mock_redis_client_for_pubsub, mock_connection_manager)

    assert subscriber.task is None

    await subscriber.start()
    assert subscriber.task is not None
    assert not subscriber.task.done()

    await subscriber.stop()
    assert subscriber.task.done()


@pytest.mark.asyncio
async def test_ignore_malformed_messages(mock_redis_client_for_pubsub, mock_connection_manager):
    """Ignores invalid JSON without crashing."""
    messages = [
        {"type": "message", "data": "not valid json"},
        {"type": "message", "data": '{"valid": "json"}'},
    ]
    pubsub = create_pubsub_mock(messages)
    mock_redis_client_for_pubsub.pubsub.return_value = pubsub

    from api.redis_subscriber import RedisSubscriber

    subscriber = RedisSubscriber(mock_redis_client_for_pubsub, mock_connection_manager)

    await subscriber.start()
    await asyncio.sleep(0.02)

    mock_connection_manager.broadcast.assert_called_once_with({"valid": "json"})

    await subscriber.stop()


@pytest.mark.asyncio
async def test_client_disconnect_during_fanout(
    mock_redis_client_for_pubsub, mock_connection_manager
):
    """Handles client disconnect during send gracefully."""
    broadcast_calls = [0]

    async def broadcast_with_error(msg):
        broadcast_calls[0] += 1
        if broadcast_calls[0] == 1:
            raise Exception("Client disconnected")

    mock_connection_manager.broadcast = broadcast_with_error

    messages = [
        {"type": "message", "data": '{"test": "data"}'},
        {"type": "message", "data": '{"after": "error"}'},
    ]
    pubsub = create_pubsub_mock(messages)
    mock_redis_client_for_pubsub.pubsub.return_value = pubsub

    from api.redis_subscriber import RedisSubscriber

    subscriber = RedisSubscriber(mock_redis_client_for_pubsub, mock_connection_manager)

    await subscriber.start()
    await asyncio.sleep(0.05)

    assert broadcast_calls[0] >= 1

    await subscriber.stop()
