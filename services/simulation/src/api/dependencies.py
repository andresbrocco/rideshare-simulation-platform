"""FastAPI dependency injection providers."""

from fastapi import Request


def get_engine(request: Request):
    """Retrieve SimulationEngine from app state."""
    return request.app.state.engine


def get_redis_client(request: Request):
    """Retrieve Redis client from app state."""
    return request.app.state.redis_client


def get_agent_factory(request: Request):
    """Retrieve AgentFactory from app state."""
    return request.app.state.agent_factory
