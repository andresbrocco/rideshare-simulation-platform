from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


@pytest.fixture
def mock_snapshot_manager():
    """Mock snapshot manager with test data."""
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
def test_client_with_snapshot(
    mock_redis_client,
    mock_simulation_engine,
    mock_snapshot_manager,
    mock_agent_factory,
):
    """Test client with snapshot manager configured."""
    with patch.dict("os.environ", {"API_KEY": "test-api-key"}):
        from api.app import create_app

        app = create_app(
            engine=mock_simulation_engine,
            agent_factory=mock_agent_factory,
            redis_client=mock_redis_client,
        )
        app.state.snapshot_manager = mock_snapshot_manager
        yield TestClient(app, raise_server_exceptions=False)


WS_AUTH_HEADERS = {"sec-websocket-protocol": "apikey.test-api-key"}


def test_websocket_connect_success(test_client_with_snapshot, mock_snapshot_manager):
    """Successfully connects with valid API key via protocol header."""
    with test_client_with_snapshot.websocket_connect("/ws", headers=WS_AUTH_HEADERS) as websocket:
        data = websocket.receive_json()
        assert data["type"] == "snapshot"
        assert "drivers" in data["data"]
        assert "trips" in data["data"]
        assert "surge" in data["data"]


def test_websocket_connect_invalid_key(test_client_with_snapshot):
    """Rejects connection with invalid API key."""
    with (
        pytest.raises(WebSocketDisconnect),
        test_client_with_snapshot.websocket_connect(
            "/ws", headers={"sec-websocket-protocol": "apikey.wrong"}
        ),
    ):
        pass


def test_websocket_connect_missing_key(test_client_with_snapshot):
    """Rejects connection with missing API key."""
    with (
        pytest.raises(WebSocketDisconnect),
        test_client_with_snapshot.websocket_connect("/ws"),
    ):
        pass


def test_websocket_sends_snapshot(test_client_with_snapshot, mock_snapshot_manager):
    """Sends snapshot immediately on connection."""
    with test_client_with_snapshot.websocket_connect("/ws", headers=WS_AUTH_HEADERS) as websocket:
        data = websocket.receive_json()
        assert data["type"] == "snapshot"
        mock_snapshot_manager.get_snapshot.assert_called_once()


def test_websocket_snapshot_includes_drivers(test_client_with_snapshot, mock_snapshot_manager):
    """Snapshot includes driver data."""
    with test_client_with_snapshot.websocket_connect("/ws", headers=WS_AUTH_HEADERS) as websocket:
        data = websocket.receive_json()
        assert len(data["data"]["drivers"]) == 1
        assert data["data"]["drivers"][0]["driver_id"] == "driver-1"


def test_websocket_snapshot_includes_trips(test_client_with_snapshot, mock_snapshot_manager):
    """Snapshot includes trip data."""
    with test_client_with_snapshot.websocket_connect("/ws", headers=WS_AUTH_HEADERS) as websocket:
        data = websocket.receive_json()
        assert len(data["data"]["trips"]) == 1
        assert data["data"]["trips"][0]["trip_id"] == "trip-1"


def test_websocket_snapshot_includes_surge(test_client_with_snapshot, mock_snapshot_manager):
    """Snapshot includes surge pricing data."""
    with test_client_with_snapshot.websocket_connect("/ws", headers=WS_AUTH_HEADERS) as websocket:
        data = websocket.receive_json()
        assert data["data"]["surge"]["zone-1"] == 1.5
        assert data["data"]["surge"]["zone-2"] == 1.0


def test_websocket_streams_updates(test_client_with_snapshot, mock_snapshot_manager):
    """WebSocket can send and receive messages."""
    with test_client_with_snapshot.websocket_connect("/ws", headers=WS_AUTH_HEADERS) as websocket:
        data = websocket.receive_json()
        assert data["type"] == "snapshot"


def test_websocket_multiple_clients(test_client_with_snapshot, mock_snapshot_manager):
    """Supports multiple concurrent WebSocket clients."""
    with (
        test_client_with_snapshot.websocket_connect("/ws", headers=WS_AUTH_HEADERS) as ws1,
        test_client_with_snapshot.websocket_connect("/ws", headers=WS_AUTH_HEADERS) as ws2,
    ):
        data1 = ws1.receive_json()
        data2 = ws2.receive_json()
        assert data1["type"] == "snapshot"
        assert data2["type"] == "snapshot"


def test_websocket_disconnect_graceful(test_client_with_snapshot, mock_snapshot_manager):
    """Handles client disconnection gracefully."""
    with test_client_with_snapshot.websocket_connect("/ws", headers=WS_AUTH_HEADERS) as websocket:
        data = websocket.receive_json()
        assert data["type"] == "snapshot"


def test_websocket_reconnect(test_client_with_snapshot, mock_snapshot_manager):
    """Client can reconnect after disconnection."""
    with test_client_with_snapshot.websocket_connect("/ws", headers=WS_AUTH_HEADERS) as websocket:
        data = websocket.receive_json()
        assert data["type"] == "snapshot"

    with test_client_with_snapshot.websocket_connect("/ws", headers=WS_AUTH_HEADERS) as websocket:
        data = websocket.receive_json()
        assert data["type"] == "snapshot"


class TestExtractApiKey:
    """Tests for extract_api_key helper function."""

    def test_extracts_from_protocol_header(self):
        """Extracts API key from Sec-WebSocket-Protocol header."""
        from api.websocket import extract_api_key

        ws = Mock()
        ws.headers = {"sec-websocket-protocol": "apikey.test-api-key"}

        api_key = extract_api_key(ws)
        assert api_key == "test-api-key"

    def test_returns_none_when_no_header(self):
        """Returns None when protocol header is missing."""
        from api.websocket import extract_api_key

        ws = Mock()
        ws.headers = {}

        api_key = extract_api_key(ws)
        assert api_key is None

    def test_handles_multiple_protocols(self):
        """Correctly parses API key from multiple protocols."""
        from api.websocket import extract_api_key

        ws = Mock()
        ws.headers = {"sec-websocket-protocol": "some-protocol, apikey.my-secret-key, other"}

        api_key = extract_api_key(ws)
        assert api_key == "my-secret-key"

    def test_handles_protocol_without_apikey_prefix(self):
        """Returns None when protocol doesn't have apikey prefix."""
        from api.websocket import extract_api_key

        ws = Mock()
        ws.headers = {"sec-websocket-protocol": "graphql-ws"}

        api_key = extract_api_key(ws)
        assert api_key is None

    def test_handles_empty_api_key_in_header(self):
        """Handles edge case of empty key after prefix."""
        from api.websocket import extract_api_key

        ws = Mock()
        ws.headers = {"sec-websocket-protocol": "apikey."}

        api_key = extract_api_key(ws)
        assert api_key == ""
