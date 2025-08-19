from confluent_kafka import Producer
from engine import SimulationEngine
from engine.agent_factory import AgentFactory
from redis.asyncio import Redis

from src.main import app


def get_engine() -> SimulationEngine:
    """Retrieve SimulationEngine from app state."""
    return app.state.engine


def get_kafka_producer() -> Producer:
    """Retrieve Kafka producer from app state."""
    return app.state.kafka_producer


def get_redis_client() -> Redis:
    """Retrieve Redis client from app state."""
    return app.state.redis_client


def get_agent_factory() -> AgentFactory:
    """Retrieve AgentFactory from app state."""
    return app.state.agent_factory
