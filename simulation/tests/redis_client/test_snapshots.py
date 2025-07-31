import json
from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as aioredis

from redis_client.snapshots import SNAPSHOT_TTL, StateSnapshotManager


@pytest.fixture
def mock_redis():
    mock = AsyncMock(spec=aioredis.Redis)
    mock.setex = AsyncMock()
    mock.get = AsyncMock()
    mock.delete = AsyncMock()
    mock.scan_iter = AsyncMock()
    mock.ttl = AsyncMock(return_value=1800)
    return mock


@pytest.fixture
def snapshot_manager(mock_redis):
    with patch("redis.asyncio.Redis", return_value=mock_redis):
        return StateSnapshotManager(mock_redis)


@pytest.mark.asyncio
async def test_snapshot_store_driver(snapshot_manager, mock_redis):
    driver_data = {
        "driver_id": "D123",
        "location": [-23.5505, -46.6333],
        "heading": 45.0,
        "status": "available",
        "trip_id": None,
        "recent_path": [[-23.5505, -46.6333]],
    }

    await snapshot_manager.store_driver(driver_data)

    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert call_args[0][0] == "snapshot:drivers:D123"
    assert call_args[0][1] == SNAPSHOT_TTL
    stored_data = json.loads(call_args[0][2])
    assert stored_data["driver_id"] == "D123"
    assert stored_data["status"] == "available"


@pytest.mark.asyncio
async def test_snapshot_store_trip(snapshot_manager, mock_redis):
    trip_data = {
        "trip_id": "T456",
        "state": "STARTED",
        "pickup": [-23.5505, -46.6333],
        "dropoff": [-23.5800, -46.6500],
        "driver_id": "D123",
        "rider_id": "R789",
        "fare": 25.50,
        "surge_multiplier": 1.5,
    }

    await snapshot_manager.store_trip(trip_data)

    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert call_args[0][0] == "snapshot:trips:T456"
    assert call_args[0][1] == SNAPSHOT_TTL
    stored_data = json.loads(call_args[0][2])
    assert stored_data["trip_id"] == "T456"
    assert stored_data["state"] == "STARTED"


@pytest.mark.asyncio
async def test_snapshot_store_surge(snapshot_manager, mock_redis):
    surge_data = {
        "zone_id": "zone_1",
        "multiplier": 1.8,
        "updated_at": "2025-07-31T10:00:00Z",
    }

    await snapshot_manager.store_surge(surge_data)

    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert call_args[0][0] == "snapshot:surge:zone_1"
    assert call_args[0][1] == SNAPSHOT_TTL
    stored_data = json.loads(call_args[0][2])
    assert stored_data["zone_id"] == "zone_1"
    assert stored_data["multiplier"] == 1.8


@pytest.mark.asyncio
async def test_snapshot_get_all_drivers(snapshot_manager, mock_redis):
    driver1 = {"driver_id": "D1", "status": "available"}
    driver2 = {"driver_id": "D2", "status": "busy"}

    async def scan_mock(*args, **kwargs):
        for key in ["snapshot:drivers:D1", "snapshot:drivers:D2"]:
            yield key

    mock_redis.scan_iter = scan_mock
    mock_redis.get = AsyncMock(side_effect=[json.dumps(driver1), json.dumps(driver2)])

    drivers = await snapshot_manager.get_all_drivers()

    assert len(drivers) == 2
    assert any(d["driver_id"] == "D1" for d in drivers)
    assert any(d["driver_id"] == "D2" for d in drivers)


@pytest.mark.asyncio
async def test_snapshot_get_all_trips(snapshot_manager, mock_redis):
    trip1 = {"trip_id": "T1", "state": "STARTED"}
    trip2 = {"trip_id": "T2", "state": "DRIVER_EN_ROUTE"}

    async def scan_mock(*args, **kwargs):
        for key in ["snapshot:trips:T1", "snapshot:trips:T2"]:
            yield key

    mock_redis.scan_iter = scan_mock
    mock_redis.get = AsyncMock(side_effect=[json.dumps(trip1), json.dumps(trip2)])

    trips = await snapshot_manager.get_all_trips()

    assert len(trips) == 2
    assert any(t["trip_id"] == "T1" for t in trips)
    assert any(t["trip_id"] == "T2" for t in trips)


@pytest.mark.asyncio
async def test_snapshot_get_all_surges(snapshot_manager, mock_redis):
    surge1 = {"zone_id": "zone_1", "multiplier": 1.5}
    surge2 = {"zone_id": "zone_2", "multiplier": 2.0}

    async def scan_mock(*args, **kwargs):
        for key in ["snapshot:surge:zone_1", "snapshot:surge:zone_2"]:
            yield key

    mock_redis.scan_iter = scan_mock
    mock_redis.get = AsyncMock(side_effect=[json.dumps(surge1), json.dumps(surge2)])

    surges = await snapshot_manager.get_all_surges()

    assert surges["zone_1"] == 1.5
    assert surges["zone_2"] == 2.0


@pytest.mark.asyncio
async def test_snapshot_recent_path_limited(snapshot_manager, mock_redis):
    positions = [[-23.55 + i * 0.001, -46.63 + i * 0.001] for i in range(15)]

    driver_data = {
        "driver_id": "D123",
        "location": positions[-1],
        "heading": 90.0,
        "status": "busy",
        "trip_id": "T100",
        "recent_path": positions,
    }

    await snapshot_manager.store_driver(driver_data)

    call_args = mock_redis.setex.call_args
    stored_data = json.loads(call_args[0][2])
    assert len(stored_data["recent_path"]) == 10
    assert stored_data["recent_path"] == positions[-10:]


@pytest.mark.asyncio
async def test_snapshot_ttl_expiration(snapshot_manager, mock_redis):
    assert SNAPSHOT_TTL == 1800

    driver_data = {
        "driver_id": "D123",
        "location": [-23.5505, -46.6333],
        "heading": 0.0,
        "status": "available",
        "trip_id": None,
        "recent_path": [],
    }

    await snapshot_manager.store_driver(driver_data)

    call_args = mock_redis.setex.call_args
    assert call_args[0][1] == 1800


@pytest.mark.asyncio
async def test_snapshot_remove_driver(snapshot_manager, mock_redis):
    await snapshot_manager.remove_driver("D123")

    mock_redis.delete.assert_called_once_with("snapshot:drivers:D123")


@pytest.mark.asyncio
async def test_snapshot_remove_trip(snapshot_manager, mock_redis):
    await snapshot_manager.remove_trip("T456")

    mock_redis.delete.assert_called_once_with("snapshot:trips:T456")


@pytest.mark.asyncio
async def test_snapshot_json_serialization(snapshot_manager, mock_redis):
    driver_data = {
        "driver_id": "D123",
        "location": [-23.5505, -46.6333],
        "heading": 180.5,
        "status": "available",
        "trip_id": None,
        "recent_path": [[-23.5505, -46.6333], [-23.5510, -46.6340]],
    }

    await snapshot_manager.store_driver(driver_data)

    call_args = mock_redis.setex.call_args
    stored_json = call_args[0][2]

    parsed = json.loads(stored_json)
    assert isinstance(parsed, dict)
    assert parsed["driver_id"] == "D123"
    assert parsed["location"] == [-23.5505, -46.6333]


@pytest.mark.asyncio
async def test_get_snapshot_returns_full_state(snapshot_manager, mock_redis):
    driver = {"driver_id": "D1", "status": "available"}
    trip = {"trip_id": "T1", "state": "STARTED"}
    surge = {"zone_id": "zone_1", "multiplier": 1.5}

    async def scan_mock(match, *args, **kwargs):
        if "drivers" in match:
            yield "snapshot:drivers:D1"
        elif "trips" in match:
            yield "snapshot:trips:T1"
        elif "surge" in match:
            yield "snapshot:surge:zone_1"

    mock_redis.scan_iter = scan_mock

    async def get_mock(key):
        if "drivers" in key:
            return json.dumps(driver)
        elif "trips" in key:
            return json.dumps(trip)
        elif "surge" in key:
            return json.dumps(surge)

    mock_redis.get = get_mock

    snapshot = await snapshot_manager.get_snapshot()

    assert "drivers" in snapshot
    assert "trips" in snapshot
    assert "surge" in snapshot
    assert len(snapshot["drivers"]) == 1
    assert len(snapshot["trips"]) == 1
    assert "zone_1" in snapshot["surge"]
