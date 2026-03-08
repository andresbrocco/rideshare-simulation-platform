"""Tests for role-based endpoint protection.

Verifies that:
- Viewers receive HTTP 403 on all admin-only endpoints.
- Viewers receive non-403 responses on viewer-accessible endpoints.
- Admins pass role checks on all endpoints (may still receive other errors
  such as 400/503 from business logic, but not 403).

The approach is to override ``verify_api_key`` on the FastAPI app so that
every test controls what :class:`~api.auth.AuthContext` the dependency
injects, without touching Redis or any other infrastructure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from fastapi import FastAPI

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockSimulationState:
    """Minimal stand-in for the engine state enum."""

    STOPPED = "stopped"
    RUNNING = "running"
    DRAINING = "draining"
    PAUSED = "paused"


def _make_engine() -> Mock:
    engine = Mock()
    engine.state = Mock()
    engine.state.value = "stopped"
    engine.speed_multiplier = 1
    engine._active_drivers = {}
    engine._active_riders = {}
    engine._get_in_flight_trips = Mock(return_value=[])
    engine.start = Mock()
    engine.stop = Mock()
    engine.pause = Mock()
    engine.resume = Mock()
    engine.set_speed = Mock()
    engine.reset = Mock()
    engine.real_time_ratio = Mock(return_value=1.0)
    engine.current_time = Mock(return_value=None)
    engine._env = Mock()
    engine._env.now = 0.0
    matching = Mock()
    matching.get_trip_stats = Mock(
        return_value={
            "completed_count": 0,
            "cancelled_count": 0,
            "avg_fare": 0.0,
            "avg_duration_minutes": 0.0,
            "avg_match_seconds": 0.0,
            "avg_pickup_seconds": 0.0,
            "active_count": 0,
        }
    )
    matching.get_matching_stats = Mock(
        return_value={
            "offers_sent": 0,
            "offers_accepted": 0,
            "offers_rejected": 0,
            "offers_expired": 0,
        }
    )
    matching.get_active_trips = Mock(return_value=[])
    matching._surge_calculator = None
    engine._matching_server = matching
    return engine


def _make_agent_factory() -> Mock:
    factory = Mock()
    factory.queue_drivers = Mock(return_value=5)
    factory.queue_riders = Mock(return_value=5)
    factory.create_puppet_driver = Mock(return_value="puppet-driver-1")
    factory.create_puppet_rider = Mock(return_value="puppet-rider-1")
    factory.get_spawn_queue_status = Mock(return_value={"drivers": 0, "riders": 0})
    return factory


def _build_app(role: str) -> FastAPI:
    """Return a configured FastAPI app whose auth always grants *role*."""
    import sys

    # Patch engine modules before importing api.app so that heavy imports
    # (SimPy, etc.) are never executed during unit tests.
    mock_engine_mod = MagicMock()
    mock_engine_mod.SimulationState = MockSimulationState
    mock_agent_factory_mod = MagicMock()

    modules_to_patch = {
        "engine": mock_engine_mod,
        "engine.agent_factory": mock_agent_factory_mod,
    }

    # Clear any previously cached api modules so each call gets a fresh app.
    for mod in list(sys.modules):
        if mod.startswith("api.") or mod in (
            "api",
            "api.routes.simulation",
            "api.routes.agents",
            "api.routes.puppet",
            "api.routes.controller",
            "api.routes.metrics",
            "api.app",
            "api.rate_limit",
            "api.websocket",
        ):
            sys.modules.pop(mod, None)

    with (
        patch.dict(sys.modules, modules_to_patch),
        patch.dict("os.environ", {"API_KEY": "test-api-key"}),
    ):
        from api.app import create_app
        from api.auth import AuthContext, verify_api_key

        redis_client: AsyncMock = AsyncMock()
        redis_client.close = AsyncMock()
        redis_client.hgetall = AsyncMock(return_value={})

        engine = _make_engine()
        agent_factory = _make_agent_factory()

        app = create_app(
            engine=engine,
            agent_factory=agent_factory,
            redis_client=redis_client,
        )

        # Override verify_api_key so the dependency always returns
        # an AuthContext with the desired role.
        ctx = AuthContext(role=role, email=f"{role}@example.com")

        async def _override() -> AuthContext:
            return ctx

        app.dependency_overrides[verify_api_key] = _override

    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def viewer_client() -> TestClient:
    """TestClient whose auth context has role='viewer'."""
    app = _build_app("viewer")
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def admin_client() -> TestClient:
    """TestClient whose auth context has role='admin'."""
    app = _build_app("admin")
    return TestClient(app, raise_server_exceptions=False)


# Any valid X-API-Key value — the override ignores it but the header is
# still required by the router-level dependency (header extraction).
_KEY = {"X-API-Key": "test-api-key"}

# Minimal valid body for puppet driver creation
_PUPPET_DRIVER_BODY: dict[str, Any] = {"location": [-23.5505, -46.6388], "ephemeral": True}
_PUPPET_RIDER_BODY: dict[str, Any] = {"location": [-23.5505, -46.6388], "ephemeral": True}


# ---------------------------------------------------------------------------
# Viewer blocked from simulation admin routes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_viewer_blocked_from_simulation_start(viewer_client: TestClient) -> None:
    """Viewer cannot start the simulation."""
    response = viewer_client.post("/simulation/start", headers=_KEY)
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required"


@pytest.mark.unit
def test_viewer_blocked_from_simulation_pause(viewer_client: TestClient) -> None:
    """Viewer cannot pause the simulation."""
    response = viewer_client.post("/simulation/pause", headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_simulation_resume(viewer_client: TestClient) -> None:
    """Viewer cannot resume the simulation."""
    response = viewer_client.post("/simulation/resume", headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_simulation_stop(viewer_client: TestClient) -> None:
    """Viewer cannot stop the simulation."""
    response = viewer_client.post("/simulation/stop", headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_simulation_reset(viewer_client: TestClient) -> None:
    """Viewer cannot reset the simulation."""
    response = viewer_client.post("/simulation/reset", headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_speed_change(viewer_client: TestClient) -> None:
    """Viewer cannot change the speed multiplier."""
    response = viewer_client.put("/simulation/speed", json={"multiplier": 2.0}, headers=_KEY)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Viewer allowed on simulation viewer routes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_viewer_can_get_simulation_status(viewer_client: TestClient) -> None:
    """Viewer can read simulation status."""
    response = viewer_client.get("/simulation/status", headers=_KEY)
    assert response.status_code != 403


# ---------------------------------------------------------------------------
# Viewer blocked from agent admin routes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_viewer_blocked_from_create_drivers(viewer_client: TestClient) -> None:
    """Viewer cannot spawn drivers."""
    response = viewer_client.post("/agents/drivers", json={"count": 1}, headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_create_riders(viewer_client: TestClient) -> None:
    """Viewer cannot spawn riders."""
    response = viewer_client.post("/agents/riders", json={"count": 1}, headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_driver_status_toggle(viewer_client: TestClient) -> None:
    """Viewer cannot toggle driver online/offline status."""
    response = viewer_client.put(
        "/agents/drivers/d1/status", json={"go_online": True}, headers=_KEY
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Viewer allowed on agent viewer routes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_viewer_can_get_spawn_status(viewer_client: TestClient) -> None:
    """Viewer can read the spawn queue status."""
    response = viewer_client.get("/agents/spawn-status", headers=_KEY)
    assert response.status_code != 403


# ---------------------------------------------------------------------------
# Viewer blocked from puppet routes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_viewer_blocked_from_puppet_driver_create(viewer_client: TestClient) -> None:
    """Viewer cannot create a puppet driver."""
    response = viewer_client.post("/agents/puppet/drivers", json=_PUPPET_DRIVER_BODY, headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_go_online(viewer_client: TestClient) -> None:
    """Viewer cannot put a puppet driver online."""
    response = viewer_client.put("/agents/puppet/drivers/d1/go-online", headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_go_offline(viewer_client: TestClient) -> None:
    """Viewer cannot put a puppet driver offline."""
    response = viewer_client.put("/agents/puppet/drivers/d1/go-offline", headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_accept_offer(viewer_client: TestClient) -> None:
    """Viewer cannot accept an offer for a puppet driver."""
    response = viewer_client.post("/agents/puppet/drivers/d1/accept-offer", headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_reject_offer(viewer_client: TestClient) -> None:
    """Viewer cannot reject an offer for a puppet driver."""
    response = viewer_client.post("/agents/puppet/drivers/d1/reject-offer", headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_drive_to_pickup(viewer_client: TestClient) -> None:
    """Viewer cannot start a puppet driver driving to pickup."""
    response = viewer_client.post("/agents/puppet/drivers/d1/drive-to-pickup", headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_drive_to_destination(viewer_client: TestClient) -> None:
    """Viewer cannot start a puppet driver driving to destination."""
    response = viewer_client.post("/agents/puppet/drivers/d1/drive-to-destination", headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_arrive_pickup(viewer_client: TestClient) -> None:
    """Viewer cannot signal driver arrived at pickup."""
    response = viewer_client.post("/agents/puppet/drivers/d1/arrive-pickup", headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_start_trip(viewer_client: TestClient) -> None:
    """Viewer cannot signal trip start for a puppet driver."""
    response = viewer_client.post("/agents/puppet/drivers/d1/start-trip", headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_complete_trip(viewer_client: TestClient) -> None:
    """Viewer cannot signal trip completion for a puppet driver."""
    response = viewer_client.post("/agents/puppet/drivers/d1/complete-trip", headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_cancel_driver_trip(viewer_client: TestClient) -> None:
    """Viewer cannot cancel a puppet driver's trip."""
    response = viewer_client.post("/agents/puppet/drivers/d1/cancel-trip", headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_rider_request_trip(viewer_client: TestClient) -> None:
    """Viewer cannot request a trip for a puppet rider."""
    response = viewer_client.post(
        "/agents/puppet/riders/r1/request-trip",
        json={"destination": [-23.56, -46.64]},
        headers=_KEY,
    )
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_cancel_rider_trip(viewer_client: TestClient) -> None:
    """Viewer cannot cancel a puppet rider's trip."""
    response = viewer_client.post("/agents/puppet/riders/r1/cancel-trip", headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_driver_rating(viewer_client: TestClient) -> None:
    """Viewer cannot update a puppet driver's rating."""
    response = viewer_client.put(
        "/agents/puppet/drivers/d1/rating", json={"rating": 4.5}, headers=_KEY
    )
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_rider_rating(viewer_client: TestClient) -> None:
    """Viewer cannot update a puppet rider's rating."""
    response = viewer_client.put(
        "/agents/puppet/riders/r1/rating", json={"rating": 4.0}, headers=_KEY
    )
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_teleport_driver(viewer_client: TestClient) -> None:
    """Viewer cannot teleport a puppet driver."""
    response = viewer_client.put(
        "/agents/puppet/drivers/d1/location",
        json={"location": [-23.56, -46.64]},
        headers=_KEY,
    )
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_teleport_rider(viewer_client: TestClient) -> None:
    """Viewer cannot teleport a puppet rider."""
    response = viewer_client.put(
        "/agents/puppet/riders/r1/location",
        json={"location": [-23.56, -46.64]},
        headers=_KEY,
    )
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_force_offer_timeout(viewer_client: TestClient) -> None:
    """Viewer cannot force-expire a pending offer."""
    response = viewer_client.post("/agents/puppet/drivers/d1/force-offer-timeout", headers=_KEY)
    assert response.status_code == 403


@pytest.mark.unit
def test_viewer_blocked_from_puppet_force_patience_timeout(viewer_client: TestClient) -> None:
    """Viewer cannot force a rider patience timeout."""
    response = viewer_client.post("/agents/puppet/riders/r1/force-patience-timeout", headers=_KEY)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Viewer blocked from controller admin routes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_viewer_blocked_from_controller_mode(viewer_client: TestClient) -> None:
    """Viewer cannot change the performance controller mode."""
    response = viewer_client.put("/controller/mode", json={"mode": "manual"}, headers=_KEY)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Viewer allowed on controller viewer routes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_viewer_can_get_controller_status(viewer_client: TestClient) -> None:
    """Viewer can read the controller status (may be 503 if controller unreachable)."""
    response = viewer_client.get("/controller/status", headers=_KEY)
    assert response.status_code != 403


# ---------------------------------------------------------------------------
# Viewer allowed on metrics routes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_viewer_can_get_metrics_overview(viewer_client: TestClient) -> None:
    """Viewer can read the overview metrics."""
    response = viewer_client.get("/metrics/overview", headers=_KEY)
    assert response.status_code != 403


# ---------------------------------------------------------------------------
# 403 response body is correctly structured
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_viewer_403_response_body(viewer_client: TestClient) -> None:
    """The 403 response carries the expected detail message."""
    response = viewer_client.post("/simulation/start", headers=_KEY)
    assert response.status_code == 403
    assert response.json() == {"detail": "Admin role required"}


# ---------------------------------------------------------------------------
# Admin passes role checks
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_admin_can_start_simulation(admin_client: TestClient) -> None:
    """Admin role is not rejected by the role check on POST /simulation/start."""
    response = admin_client.post("/simulation/start", headers=_KEY)
    assert response.status_code != 403


@pytest.mark.unit
def test_admin_can_create_drivers(admin_client: TestClient) -> None:
    """Admin role is not rejected by the role check on POST /agents/drivers."""
    response = admin_client.post("/agents/drivers", json={"count": 1}, headers=_KEY)
    assert response.status_code != 403


@pytest.mark.unit
def test_admin_can_create_puppet_driver(admin_client: TestClient) -> None:
    """Admin role is not rejected by the role check on POST /agents/puppet/drivers."""
    response = admin_client.post("/agents/puppet/drivers", json=_PUPPET_DRIVER_BODY, headers=_KEY)
    assert response.status_code != 403
