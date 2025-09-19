from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from settings import get_settings

router = APIRouter()


def extract_api_key(websocket: WebSocket) -> str | None:
    """Extract API key from Sec-WebSocket-Protocol header.

    Expected format: apikey.<key>
    """
    protocol_header = websocket.headers.get("sec-websocket-protocol")
    if protocol_header:
        protocols = [p.strip() for p in protocol_header.split(",")]
        for protocol in protocols:
            if protocol.startswith("apikey."):
                return protocol.split(".", 1)[1]
    return None


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def send_message(self, websocket: WebSocket, message: dict):
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await self.send_message(connection, message)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    api_key = extract_api_key(websocket)
    settings = get_settings()

    if not api_key or api_key != settings.api.key:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket)

    try:
        snapshot_manager = websocket.app.state.snapshot_manager
        engine = websocket.app.state.engine
        snapshot = await snapshot_manager.get_snapshot(engine=engine)

        await manager.send_message(websocket, {"type": "snapshot", "data": snapshot})

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(websocket)
