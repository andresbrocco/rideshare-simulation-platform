from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from api.rate_limit import ws_limiter
from api.session_store import get_session
from settings import get_settings

router = APIRouter()


def extract_api_key_and_protocol(websocket: WebSocket) -> tuple[str | None, str | None]:
    """Extract API key and full protocol from Sec-WebSocket-Protocol header.

    Expected format: apikey.<key>
    Returns: (api_key, full_protocol) - both needed for proper handshake
    """
    protocol_header = websocket.headers.get("sec-websocket-protocol")
    if protocol_header:
        protocols = [p.strip() for p in protocol_header.split(",")]
        for protocol in protocols:
            if protocol.startswith("apikey."):
                return protocol.split(".", 1)[1], protocol
    return None, None


def extract_api_key(websocket: WebSocket) -> str | None:
    """Extract API key from Sec-WebSocket-Protocol header.

    Expected format: apikey.<key>
    Returns: api_key or None if not found
    """
    api_key, _ = extract_api_key_and_protocol(websocket)
    return api_key


async def _is_valid_key(api_key: str, websocket: WebSocket) -> bool:
    """Validate an API key against the static admin key or a Redis session.

    Returns True if the key is valid, False otherwise.
    """
    settings = get_settings()

    if api_key.startswith("sess_"):
        # Session key path — look up in Redis
        redis_client = websocket.app.state.redis_client
        session = await get_session(api_key, redis_client)
        return session is not None

    # Static admin key path
    return api_key == settings.api.key


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self) -> None:
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, subprotocol: str | None = None) -> None:
        await websocket.accept(subprotocol=subprotocol)
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    async def send_message(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.send_json(message)

    async def broadcast(self, message: dict[str, Any]) -> None:
        for connection in self.active_connections:
            await self.send_message(connection, message)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    api_key, subprotocol = extract_api_key_and_protocol(websocket)

    if not api_key or not await _is_valid_key(api_key, websocket):
        await websocket.close(code=1008)
        return

    # Rate limit WebSocket connections per client
    client_key = f"key:{api_key}"
    if ws_limiter.is_limited(client_key):
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, subprotocol=subprotocol)

    try:
        snapshot_manager = websocket.app.state.snapshot_manager
        engine = websocket.app.state.engine
        snapshot = await snapshot_manager.get_snapshot(engine=engine)

        await manager.send_message(websocket, {"type": "snapshot", "data": snapshot})

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(websocket)
