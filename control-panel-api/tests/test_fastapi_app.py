import sys
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from fastapi.testclient import TestClient

sys.modules["engine"] = MagicMock()
sys.modules["engine.agent_factory"] = MagicMock()


@pytest.fixture
def mock_kafka_producer():
    producer = Mock()
    producer.flush = Mock()
    return producer


@pytest.fixture
def mock_redis_client():
    client = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_simulation_state():
    state = Mock()
    state.value = "stopped"
    return state


@pytest.fixture
def mock_simulation_engine(mock_simulation_state):
    engine = Mock()
    engine.state = mock_simulation_state
    engine.stop = Mock()
    return engine


def test_app_initialization():
    """Creates FastAPI app instance."""
    from src.main import app

    assert app is not None
    assert app.title == "Rideshare Simulation Control Panel API"
    assert app.version == "1.0.0"


@pytest.mark.asyncio
async def test_lifespan_startup(
    mock_kafka_producer, mock_redis_client, mock_simulation_engine
):
    """Initializes engine on startup."""
    with patch("src.main.Producer", return_value=mock_kafka_producer):
        with patch("src.main.Redis", return_value=mock_redis_client):
            with patch(
                "src.main.SimulationEngine", return_value=mock_simulation_engine
            ):
                from src.main import app, lifespan

                async with lifespan(app):
                    assert hasattr(app.state, "engine")
                    assert hasattr(app.state, "kafka_producer")
                    assert hasattr(app.state, "redis_client")
                    assert app.state.engine.state.value == "stopped"


@pytest.mark.asyncio
async def test_lifespan_shutdown(
    mock_kafka_producer, mock_redis_client, mock_simulation_engine
):
    """Cleans up resources on shutdown."""
    with patch("src.main.Producer", return_value=mock_kafka_producer):
        with patch("src.main.Redis", return_value=mock_redis_client):
            with patch(
                "src.main.SimulationEngine", return_value=mock_simulation_engine
            ):
                from src.main import app, lifespan

                async with lifespan(app):
                    pass

                mock_kafka_producer.flush.assert_called_once()
                mock_redis_client.close.assert_called_once()


def test_health_endpoint_returns_ok():
    """Health check returns 200 OK."""
    from src.main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_configured():
    """CORS allows frontend origin."""
    from src.main import app

    client = TestClient(app)
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" in response.headers


@pytest.mark.asyncio
async def test_engine_dependency(
    mock_kafka_producer, mock_redis_client, mock_simulation_engine
):
    """Dependency injection provides engine."""
    with patch("src.main.Producer", return_value=mock_kafka_producer):
        with patch("src.main.Redis", return_value=mock_redis_client):
            with patch(
                "src.main.SimulationEngine", return_value=mock_simulation_engine
            ):
                from src.main import app, lifespan
                from src.dependencies import get_engine

                async with lifespan(app):
                    engine = get_engine()
                    assert engine is mock_simulation_engine


def test_health_endpoint_no_auth():
    """Health endpoint bypasses auth."""
    from src.main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_kafka_producer_initialized(
    mock_kafka_producer, mock_redis_client, mock_simulation_engine
):
    """Kafka producer ready at startup."""
    with patch("src.main.Producer", return_value=mock_kafka_producer):
        with patch("src.main.Redis", return_value=mock_redis_client):
            with patch(
                "src.main.SimulationEngine", return_value=mock_simulation_engine
            ):
                from src.main import app, lifespan

                async with lifespan(app):
                    assert hasattr(app.state, "kafka_producer")
                    assert app.state.kafka_producer is mock_kafka_producer


@pytest.mark.asyncio
async def test_redis_client_initialized(
    mock_redis_client, mock_kafka_producer, mock_simulation_engine
):
    """Redis client ready at startup."""
    with patch("src.main.Producer", return_value=mock_kafka_producer):
        with patch("src.main.Redis", return_value=mock_redis_client):
            with patch(
                "src.main.SimulationEngine", return_value=mock_simulation_engine
            ):
                from src.main import app, lifespan

                async with lifespan(app):
                    assert hasattr(app.state, "redis_client")
                    assert app.state.redis_client is mock_redis_client
