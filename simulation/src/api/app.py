"""FastAPI application factory for simulation control panel."""

import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from api.redis_subscriber import RedisSubscriber
from api.routes import agents, metrics, simulation
from api.snapshots import StateSnapshotManager
from api.websocket import manager as connection_manager
from api.websocket import router as websocket_router
from settings import get_settings

if TYPE_CHECKING:
    from engine import SimulationEngine
    from engine.agent_factory import AgentFactory


class StatusBroadcaster:
    """Periodically broadcasts simulation status to WebSocket clients."""

    def __init__(self, engine: "SimulationEngine", connection_manager, snapshot_manager):
        self._engine = engine
        self._connection_manager = connection_manager
        self._snapshot_manager = snapshot_manager
        self._task = None
        self._interval = 1.0  # seconds

    async def start(self):
        self._task = asyncio.create_task(self._broadcast_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _broadcast_loop(self):
        while True:
            try:
                await asyncio.sleep(self._interval)
                if self._connection_manager.active_connections:
                    snapshot = await self._snapshot_manager.get_snapshot(engine=self._engine)
                    await self._connection_manager.broadcast(
                        {
                            "type": "simulation_status",
                            "data": snapshot.get("simulation", {}),
                        }
                    )
            except asyncio.CancelledError:
                break
            except Exception:
                pass  # Silently continue on errors


def create_app(
    engine: "SimulationEngine",
    agent_factory: "AgentFactory",
    redis_client: Redis,
) -> FastAPI:
    """Create FastAPI application with injected dependencies."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage application startup and shutdown."""
        snapshot_manager = StateSnapshotManager(redis_client)
        subscriber = RedisSubscriber(redis_client, connection_manager)
        broadcaster = StatusBroadcaster(engine, connection_manager, snapshot_manager)

        app.state.snapshot_manager = snapshot_manager
        app.state.subscriber = subscriber
        app.state.broadcaster = broadcaster

        await subscriber.start()
        await broadcaster.start()
        yield
        await broadcaster.stop()
        await subscriber.stop()

    app = FastAPI(
        title="Rideshare Simulation Control Panel API",
        version="1.0.0",
        description="REST API for controlling simulation and streaming real-time updates",
        lifespan=lifespan,
    )

    # Set core dependencies immediately (not in lifespan) so they're available for testing
    app.state.engine = engine
    app.state.redis_client = redis_client
    app.state.agent_factory = agent_factory

    settings = get_settings()
    origins = settings.cors.origins.split(",")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(simulation.router, prefix="/simulation", tags=["simulation"])
    app.include_router(agents.router, prefix="/agents", tags=["agents"])
    app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
    app.include_router(websocket_router)

    @app.get("/health")
    async def health_check():
        """Health check endpoint for monitoring."""
        return {"status": "ok"}

    return app
