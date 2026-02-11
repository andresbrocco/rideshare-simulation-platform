#!/usr/bin/env python3
"""Export OpenAPI spec from FastAPI app to schemas/api/openapi.json."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

# Add src to path so we can import from api
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.app import create_app

# Create mock dependencies
mock_engine = Mock()
mock_engine.state = Mock(value="stopped")
mock_engine.speed_multiplier = 1
mock_engine.set_event_loop = Mock()

mock_agent_factory = Mock()
mock_redis_client = AsyncMock()
mock_redis_client.ping = AsyncMock(return_value=True)

# Create app with mocks
app = create_app(
    engine=mock_engine,
    agent_factory=mock_agent_factory,
    redis_client=mock_redis_client,
    zone_loader=None,
    matching_server=None,
)

# Get OpenAPI schema
openapi_schema = app.openapi()

# Write to schemas/api/openapi.json
output_path = Path(__file__).parent.parent.parent.parent / "schemas" / "api" / "openapi.json"
output_path.parent.mkdir(parents=True, exist_ok=True)

with output_path.open("w") as f:
    json.dump(openapi_schema, f, indent=2)

print(f"OpenAPI spec exported to {output_path}")
