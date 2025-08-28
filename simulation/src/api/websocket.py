from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from settings import get_settings

router = APIRouter()


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
    api_key = websocket.query_params.get("api_key")
    settings = get_settings()

    if not api_key or api_key != settings.api.key:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket)

    try:
        snapshot_manager = websocket.app.state.snapshot_manager
        snapshot = await snapshot_manager.get_snapshot()

        await manager.send_message(websocket, {"type": "snapshot", "data": snapshot})

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(websocket)
