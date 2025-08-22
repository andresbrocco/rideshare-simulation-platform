from contextlib import asynccontextmanager
from datetime import UTC, datetime

from confluent_kafka import Producer
from engine import SimulationEngine
from engine.agent_factory import AgentFactory
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from src.auth import verify_api_key
from src.redis_subscriber import RedisSubscriber
from src.routes import agents, metrics, simulation
from src.settings import get_settings
from src.snapshots import StateSnapshotManager
from src.websocket import manager as connection_manager
from src.websocket import router as websocket_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    settings = get_settings()

    kafka_config = {
        "bootstrap.servers": settings.kafka.bootstrap_servers,
        "security.protocol": settings.kafka.security_protocol,
    }

    if settings.kafka.sasl_username:
        kafka_config["sasl.mechanisms"] = settings.kafka.sasl_mechanisms
        kafka_config["sasl.username"] = settings.kafka.sasl_username
        kafka_config["sasl.password"] = settings.kafka.sasl_password

    kafka_producer = Producer(kafka_config)

    redis_client = Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        password=settings.redis.password,
        decode_responses=True,
    )

    simulation_start_time = datetime.now(UTC)

    engine = SimulationEngine(
        matching_server=None,
        kafka_producer=kafka_producer,
        redis_client=redis_client,
        osrm_client=None,
        sqlite_db=None,
        simulation_start_time=simulation_start_time,
    )

    agent_factory = AgentFactory(
        simulation_engine=engine,
        sqlite_db=None,
        kafka_producer=kafka_producer,
    )

    snapshot_manager = StateSnapshotManager(redis_client)
    subscriber = RedisSubscriber(redis_client, connection_manager)

    app.state.engine = engine
    app.state.kafka_producer = kafka_producer
    app.state.redis_client = redis_client
    app.state.agent_factory = agent_factory
    app.state.snapshot_manager = snapshot_manager
    app.state.subscriber = subscriber

    await subscriber.start()

    yield

    await subscriber.stop()

    if engine.state.value == "running":
        engine.stop()

    kafka_producer.flush()
    await redis_client.close()


app = FastAPI(
    title="Rideshare Simulation Control Panel API",
    version="1.0.0",
    description="REST API for controlling simulation and streaming real-time updates",
    lifespan=lifespan,
)

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


@app.get("/health", dependencies=[Depends(verify_api_key)])
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "ok"}
