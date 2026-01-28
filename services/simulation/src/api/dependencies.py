"""FastAPI dependency injection providers."""

from typing import Any

from fastapi import Request


def get_engine(request: Request) -> Any:
    """Retrieve SimulationEngine from app state."""
    return request.app.state.engine


def get_redis_client(request: Request) -> Any:
    """Retrieve Redis client from app state."""
    return request.app.state.redis_client


def get_agent_factory(request: Request) -> Any:
    """Retrieve AgentFactory from app state."""
    return request.app.state.agent_factory
