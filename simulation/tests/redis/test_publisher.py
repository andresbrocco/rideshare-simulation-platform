import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError
from simulation.src.pubsub.channels import ALL_CHANNELS
from simulation.src.redis.publisher import RedisPublisher


@pytest.fixture
def redis_config():
    return {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "password": None,
    }


@pytest.fixture
def mock_redis():
    mock = AsyncMock(spec=aioredis.Redis)
    mock.publish = AsyncMock(return_value=1)
    mock.close = AsyncMock()
    return mock


@pytest.mark.asyncio
async def test_publisher_init(redis_config):
    with patch("redis.asyncio.Redis") as mock_redis_cls:
        publisher = RedisPublisher(redis_config)

        assert publisher is not None
        mock_redis_cls.assert_called_once_with(
            host="localhost",
            port=6379,
            db=0,
            password=None,
            decode_responses=True,
        )


@pytest.mark.asyncio
async def test_publisher_publish_success(redis_config, mock_redis):
    with patch("redis.asyncio.Redis", return_value=mock_redis):
        publisher = RedisPublisher(redis_config)

        message = {"driver_id": "D123", "status": "available"}
        await publisher.publish("driver-updates", message)

        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == "driver-updates"
        assert json.loads(call_args[0][1]) == message


@pytest.mark.asyncio
async def test_publisher_publish_json_serialization(redis_config, mock_redis):
    with patch("redis.asyncio.Redis", return_value=mock_redis):
        publisher = RedisPublisher(redis_config)

        message = {
            "trip_id": "T456",
            "state": "STARTED",
            "fare": 15.50,
            "surge_multiplier": 1.5,
        }

        await publisher.publish("trip-updates", message)

        call_args = mock_redis.publish.call_args
        published_json = call_args[0][1]

        assert isinstance(published_json, str)
        assert json.loads(published_json) == message


@pytest.mark.asyncio
async def test_publisher_connection_error(redis_config, mock_redis, caplog):
    mock_redis.publish.side_effect = ConnectionError("Connection refused")

    with patch("redis.asyncio.Redis", return_value=mock_redis):
        publisher = RedisPublisher(redis_config)

        await publisher.publish("driver-updates", {"driver_id": "D123"})

        assert "Failed to publish to channel driver-updates" in caplog.text
        assert "Connection refused" in caplog.text


@pytest.mark.asyncio
async def test_publisher_reconnect_on_failure(redis_config, mock_redis):
    mock_redis.publish.side_effect = [
        ConnectionError("Connection lost"),
        1,
    ]

    with patch("redis.asyncio.Redis", return_value=mock_redis):
        publisher = RedisPublisher(redis_config)

        await publisher.publish("driver-updates", {"driver_id": "D123"})

        await publisher.publish("driver-updates", {"driver_id": "D456"})

        assert mock_redis.publish.call_count == 2


@pytest.mark.asyncio
async def test_publisher_close(redis_config, mock_redis):
    with patch("redis.asyncio.Redis", return_value=mock_redis):
        publisher = RedisPublisher(redis_config)

        await publisher.close()

        mock_redis.close.assert_called_once()


@pytest.mark.asyncio
async def test_publisher_valid_channels(redis_config, mock_redis):
    with patch("redis.asyncio.Redis", return_value=mock_redis):
        publisher = RedisPublisher(redis_config)

        for channel in ALL_CHANNELS:
            await publisher.publish(channel, {"test": "data"})

        assert mock_redis.publish.call_count == len(ALL_CHANNELS)


@pytest.mark.asyncio
async def test_publisher_invalid_channel(redis_config, mock_redis):
    with patch("redis.asyncio.Redis", return_value=mock_redis):
        publisher = RedisPublisher(redis_config)

        with pytest.raises(ValueError) as exc_info:
            await publisher.publish("invalid-channel", {"test": "data"})

        assert "invalid-channel" in str(exc_info.value)
        assert "not a valid channel" in str(exc_info.value).lower()
        mock_redis.publish.assert_not_called()
