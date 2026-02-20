import json
import subprocess
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openapi_spec_validator import validate
from openapi_spec_validator.readers import read_from_filename
from pytest import MonkeyPatch


@pytest.fixture
def test_app(monkeypatch: MonkeyPatch) -> FastAPI:
    """Create FastAPI test app with minimal dependencies for contract testing."""
    import asyncio
    import os
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock, Mock

    from api.app import create_app

    monkeypatch.setenv("API_KEY", "dev-api-key-change-in-production")

    mock_engine = Mock()
    mock_engine.state = Mock(value="stopped")
    mock_engine.speed_multiplier = 1
    mock_engine.current_time = Mock(return_value=datetime.now(UTC))
    mock_engine._get_in_flight_trips = Mock(return_value=[])
    mock_engine._active_drivers = {}
    mock_engine._active_riders = {}
    mock_engine.set_event_loop = Mock()

    mock_agent_factory = Mock()

    async def mock_listen() -> AsyncGenerator[dict[str, Any]]:
        while True:
            await asyncio.sleep(10)
            yield {}

    mock_pubsub = Mock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()
    mock_pubsub.listen = Mock(return_value=mock_listen())

    mock_redis_client = AsyncMock()
    mock_redis_client.ping = AsyncMock(return_value=True)
    mock_redis_client.pubsub = Mock(return_value=mock_pubsub)

    mock_driver_registry = Mock()
    mock_driver_registry.get_all_status_counts = Mock(
        return_value={
            "online": 0,
            "offline": 0,
            "en_route_pickup": 0,
            "en_route_destination": 0,
        }
    )

    app = create_app(
        engine=mock_engine,
        agent_factory=mock_agent_factory,
        redis_client=mock_redis_client,
        zone_loader=None,
        matching_server=None,
    )

    app.state.driver_registry = mock_driver_registry

    return app


@pytest.fixture
def test_client(test_app: FastAPI) -> Generator[TestClient]:
    """Create test client with API key authentication."""
    with TestClient(test_app) as client:
        client.headers["X-API-Key"] = "dev-api-key-change-in-production"
        yield client


@pytest.fixture
def openapi_spec_path() -> Path:
    """Path to the exported OpenAPI spec."""
    return Path(__file__).parent.parent.parent.parent / "schemas" / "api" / "openapi.json"


def test_openapi_spec_is_valid(openapi_spec_path: Path) -> None:
    """Validate that the exported OpenAPI spec is valid against JSON schema."""
    spec_dict, spec_url = read_from_filename(str(openapi_spec_path))
    validate(spec_dict)


def test_openapi_spec_export(test_client: TestClient) -> None:
    """Verify that /openapi.json endpoint returns valid OpenAPI 3.0 JSON."""
    response = test_client.get("/openapi.json")

    assert response.status_code == 200
    spec = response.json()

    assert "openapi" in spec
    assert spec["openapi"].startswith("3.")
    assert "info" in spec
    assert spec["info"]["title"] == "Rideshare Simulation Control Panel API"
    assert "paths" in spec
    assert isinstance(spec["paths"], dict)


def test_simulation_status_matches_schema(test_client: TestClient) -> None:
    """Verify that /simulation/status response matches SimulationStatus schema."""
    response = test_client.get("/simulation/status")

    assert response.status_code == 200
    data = response.json()

    required_fields = [
        "state",
        "speed_multiplier",
        "current_time",
        "drivers_total",
        "drivers_offline",
        "drivers_online",
        "drivers_en_route_pickup",
        "drivers_en_route_destination",
        "riders_total",
        "riders_offline",
        "riders_waiting",
        "riders_in_trip",
        "active_trips_count",
        "uptime_seconds",
    ]

    for field in required_fields:
        assert field in data, f"Missing required field: {field}"

    assert data["state"] in ["stopped", "running", "draining", "paused"]
    assert isinstance(data["speed_multiplier"], int)
    assert isinstance(data["drivers_total"], int)
    assert isinstance(data["uptime_seconds"], int | float)


def test_health_response_matches_schema(test_client: TestClient) -> None:
    """Verify that /health/detailed response matches DetailedHealthResponse schema."""
    with patch("httpx.AsyncClient") as mock_httpx:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "message": "OK",
            "kafka_connected": True,
            "redis_connected": True,
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__.return_value = mock_client_instance
        mock_client_instance.__aexit__.return_value = None
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_httpx.return_value = mock_client_instance

        response = test_client.get("/health/detailed")

    assert response.status_code == 200
    data = response.json()

    required_fields = [
        "overall_status",
        "redis",
        "osrm",
        "kafka",
        "simulation_engine",
        "stream_processor",
        "timestamp",
    ]

    for field in required_fields:
        assert field in data, f"Missing required field: {field}"

    assert data["overall_status"] in ["healthy", "degraded", "unhealthy"]

    for service in ["redis", "osrm", "kafka", "simulation_engine"]:
        assert data[service]["status"] in ["healthy", "degraded", "unhealthy"]
        assert "latency_ms" in data[service]
        assert "message" in data[service]

    assert data["stream_processor"]["status"] in ["healthy", "degraded", "unhealthy"]
    assert "kafka_connected" in data["stream_processor"]
    assert "redis_connected" in data["stream_processor"]


def test_typescript_types_generated(openapi_spec_path: Path) -> None:
    """Verify that npm run generate-types successfully creates TypeScript types."""
    frontend_dir = Path(__file__).parent.parent.parent.parent / "services" / "control-panel"
    generated_types_path = frontend_dir / "src" / "types" / "api.generated.ts"

    result = subprocess.run(
        ["npm", "run", "generate-types"],
        cwd=str(frontend_dir),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Type generation failed: {result.stderr}"
    assert generated_types_path.exists(), "Generated types file not created"

    content = generated_types_path.read_text()
    assert len(content) > 0, "Generated types file is empty"
    assert "SimulationStatusResponse" in content or "export" in content


def test_typescript_types_match_openapi(openapi_spec_path: Path) -> None:
    """Verify that generated TypeScript types match the committed version."""
    frontend_dir = Path(__file__).parent.parent.parent.parent / "services" / "control-panel"
    generated_types_path = frontend_dir / "src" / "types" / "api.generated.ts"

    if not generated_types_path.exists():
        pytest.skip("Generated types file does not exist yet")

    original_content = generated_types_path.read_text()

    subprocess.run(
        ["npm", "run", "generate-types"],
        cwd=str(frontend_dir),
        capture_output=True,
        text=True,
    )

    regenerated_content = generated_types_path.read_text()

    assert (
        original_content == regenerated_content
    ), "Generated types differ from committed version. Run 'npm run generate-types' and commit changes."
