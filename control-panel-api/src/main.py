import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from confluent_kafka import Producer
from engine import SimulationEngine
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    kafka_config = {
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "security.protocol": os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),
    }

    if os.getenv("KAFKA_SASL_USERNAME"):
        kafka_config["sasl.mechanisms"] = "PLAIN"
        kafka_config["sasl.username"] = os.getenv("KAFKA_SASL_USERNAME")
        kafka_config["sasl.password"] = os.getenv("KAFKA_SASL_PASSWORD")

    kafka_producer = Producer(kafka_config)

    redis_client = Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD"),
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

    app.state.engine = engine
    app.state.kafka_producer = kafka_producer
    app.state.redis_client = redis_client

    yield

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

origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "ok"}
