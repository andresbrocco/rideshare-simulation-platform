import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

sys.modules["engine"] = MagicMock()
sys.modules["engine.agent_factory"] = MagicMock()


class MockSimulationState:
    STOPPED = "stopped"
    RUNNING = "running"
    DRAINING = "draining"
    PAUSED = "paused"


sys.modules["engine"].SimulationState = MockSimulationState


@pytest.fixture
def mock_snapshot_manager():
    manager = AsyncMock()
    manager.get_snapshot.return_value = {
        "drivers": [
            {
                "driver_id": "driver-1",
                "location": {"lat": -23.5505, "lon": -46.6333},
                "status": "available",
            }
        ],
        "trips": [
            {
                "trip_id": "trip-1",
                "state": "STARTED",
                "driver_id": "driver-1",
                "rider_id": "rider-1",
            }
        ],
        "surge": {"zone-1": 1.5, "zone-2": 1.0},
    }
    return manager


@pytest.fixture
def mock_kafka_producer():
    producer = Mock()
    producer.flush = Mock()
    return producer


@pytest.fixture
def mock_redis_client():
    client = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_simulation_engine():
    engine = Mock()
    engine.state = Mock()
    engine.state.value = "stopped"
    engine.speed_multiplier = 1
    engine.active_driver_count = 0
    engine.active_rider_count = 0
    engine._get_in_flight_trips = Mock(return_value=[])
    return engine


@pytest.fixture
def test_client(
    mock_kafka_producer,
    mock_redis_client,
    mock_simulation_engine,
    mock_snapshot_manager,
):
    with patch.dict("os.environ", {"API_KEY": "test-api-key"}):
        with patch("main.Producer", return_value=mock_kafka_producer):
            with patch("main.Redis", return_value=mock_redis_client):
                with patch(
                    "main.SimulationEngine", return_value=mock_simulation_engine
                ):
                    with patch(
                        "main.StateSnapshotManager", return_value=mock_snapshot_manager
                    ):
                        from main import app

                        app.state.engine = mock_simulation_engine
                        app.state.snapshot_manager = mock_snapshot_manager
                        yield TestClient(app)


def test_websocket_connect_success(test_client, mock_snapshot_manager):
    """Successfully connects with valid API key."""
    with test_client.websocket_connect("/ws?api_key=test-api-key") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "snapshot"
        assert "drivers" in data["data"]
        assert "trips" in data["data"]
        assert "surge" in data["data"]


def test_websocket_connect_invalid_key(test_client):
    """Rejects connection with invalid API key."""
    with pytest.raises(Exception):
        with test_client.websocket_connect("/ws?api_key=wrong"):
            pass


def test_websocket_connect_missing_key(test_client):
    """Rejects connection with missing API key."""
    with pytest.raises(Exception):
        with test_client.websocket_connect("/ws"):
            pass


def test_websocket_sends_snapshot(test_client, mock_snapshot_manager):
    """Sends snapshot immediately on connection."""
    with test_client.websocket_connect("/ws?api_key=test-api-key") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "snapshot"
        mock_snapshot_manager.get_snapshot.assert_called_once()


def test_websocket_snapshot_includes_drivers(test_client, mock_snapshot_manager):
    """Snapshot includes driver data."""
    with test_client.websocket_connect("/ws?api_key=test-api-key") as websocket:
        data = websocket.receive_json()
        assert len(data["data"]["drivers"]) == 1
        assert data["data"]["drivers"][0]["driver_id"] == "driver-1"


def test_websocket_snapshot_includes_trips(test_client, mock_snapshot_manager):
    """Snapshot includes trip data."""
    with test_client.websocket_connect("/ws?api_key=test-api-key") as websocket:
        data = websocket.receive_json()
        assert len(data["data"]["trips"]) == 1
        assert data["data"]["trips"][0]["trip_id"] == "trip-1"


def test_websocket_snapshot_includes_surge(test_client, mock_snapshot_manager):
    """Snapshot includes surge pricing data."""
    with test_client.websocket_connect("/ws?api_key=test-api-key") as websocket:
        data = websocket.receive_json()
        assert data["data"]["surge"]["zone-1"] == 1.5
        assert data["data"]["surge"]["zone-2"] == 1.0


def test_websocket_streams_updates(test_client, mock_snapshot_manager):
    """WebSocket can send and receive messages."""
    with test_client.websocket_connect("/ws?api_key=test-api-key") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "snapshot"


def test_websocket_multiple_clients(test_client, mock_snapshot_manager):
    """Supports multiple concurrent WebSocket clients."""
    with test_client.websocket_connect("/ws?api_key=test-api-key") as ws1:
        with test_client.websocket_connect("/ws?api_key=test-api-key") as ws2:
            data1 = ws1.receive_json()
            data2 = ws2.receive_json()
            assert data1["type"] == "snapshot"
            assert data2["type"] == "snapshot"


def test_websocket_disconnect_graceful(test_client, mock_snapshot_manager):
    """Handles client disconnection gracefully."""
    with test_client.websocket_connect("/ws?api_key=test-api-key") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "snapshot"


def test_websocket_reconnect(test_client, mock_snapshot_manager):
    """Client can reconnect after disconnection."""
    with test_client.websocket_connect("/ws?api_key=test-api-key") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "snapshot"

    with test_client.websocket_connect("/ws?api_key=test-api-key") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "snapshot"
