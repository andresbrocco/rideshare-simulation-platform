"""Simulation API client for performance testing."""

import time
from dataclasses import dataclass
from typing import Any

import httpx

from ..config import TestConfig


@dataclass
class SpawnStatus:
    """Status of agent spawn queues."""

    drivers_pending: int
    riders_pending: int
    drivers_spawned: int
    riders_spawned: int


@dataclass
class SimulationStatus:
    """Current simulation status."""

    state: str
    speed_multiplier: int
    current_time: str
    drivers_total: int
    riders_total: int
    active_trips_count: int
    uptime_seconds: float


class SimulationAPIClient:
    """Client for interacting with the Simulation API.

    Provides methods for controlling the simulation and spawning agents.
    All agent spawning uses mode=immediate as specified in the test protocol.
    """

    def __init__(self, config: TestConfig) -> None:
        self.config = config
        self.base_url = config.api.base_url
        self.api_key = config.api.api_key
        self.timeout = config.api.timeout

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with API key."""
        return {"X-API-Key": self.api_key}

    def _get(self, path: str) -> dict[str, Any]:
        """Make a GET request."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}{path}",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result

    def _post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a POST request."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}{path}",
                headers=self._get_headers(),
                json=json or {},
            )
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result

    def _put(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a PUT request."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.put(
                f"{self.base_url}{path}",
                headers=self._get_headers(),
                json=json or {},
            )
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result

    def health_check(self) -> bool:
        """Check if the simulation API is healthy.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False

    def get_simulation_status(self) -> SimulationStatus:
        """Get current simulation status.

        Returns:
            SimulationStatus with current state.
        """
        data = self._get("/simulation/status")
        return SimulationStatus(
            state=data["state"],
            speed_multiplier=data["speed_multiplier"],
            current_time=data["current_time"],
            drivers_total=data["drivers_total"],
            riders_total=data["riders_total"],
            active_trips_count=data["active_trips_count"],
            uptime_seconds=data.get("uptime_seconds", 0.0),
        )

    def start(self) -> dict[str, Any]:
        """Start the simulation.

        Returns:
            Response from the API.
        """
        return self._post("/simulation/start")

    def stop(self) -> dict[str, Any]:
        """Stop the simulation.

        Returns:
            Response from the API.
        """
        return self._post("/simulation/stop")

    def pause(self) -> dict[str, Any]:
        """Pause simulation (triggers RUNNING -> DRAINING -> PAUSED).

        Returns:
            Response from the API.
        """
        return self._post("/simulation/pause")

    def set_speed(self, multiplier: int) -> dict[str, Any]:
        """Set simulation speed multiplier.

        Args:
            multiplier: Speed multiplier value.

        Returns:
            Response from the API.
        """
        return self._put("/simulation/speed", json={"multiplier": multiplier})

    def reset(self) -> dict[str, Any]:
        """Reset the simulation to initial state.

        Returns:
            Response from the API.
        """
        return self._post("/simulation/reset")

    def queue_drivers(self, count: int) -> dict[str, Any]:
        """Queue drivers for spawning with immediate mode.

        Args:
            count: Number of drivers to queue.

        Returns:
            Response with queue status.
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/agents/drivers",
                headers=self._get_headers(),
                params={"mode": "immediate"},
                json={"count": count},
            )
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result

    def queue_riders(self, count: int) -> dict[str, Any]:
        """Queue riders for spawning with immediate mode.

        Args:
            count: Number of riders to queue.

        Returns:
            Response with queue status.
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/agents/riders",
                headers=self._get_headers(),
                params={"mode": "immediate"},
                json={"count": count},
            )
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result

    def get_spawn_status(self) -> SpawnStatus:
        """Get current spawn queue status.

        Returns:
            SpawnStatus with queue depths.
        """
        data = self._get("/agents/spawn-status")
        return SpawnStatus(
            drivers_pending=data.get("drivers_pending", 0),
            riders_pending=data.get("riders_pending", 0),
            drivers_spawned=data.get("drivers_spawned", 0),
            riders_spawned=data.get("riders_spawned", 0),
        )

    def wait_for_spawn_complete(
        self,
        timeout: float = 120.0,
        check_interval: float = 1.0,
    ) -> bool:
        """Wait for all spawn queues to be empty.

        Args:
            timeout: Maximum time to wait.
            check_interval: Time between checks.

        Returns:
            True if queues emptied, False if timeout.
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self.get_spawn_status()
            if status.drivers_pending == 0 and status.riders_pending == 0:
                return True
            time.sleep(check_interval)

        return False

    def wait_for_state(
        self,
        target_state: str,
        timeout: float = 120.0,
        check_interval: float = 2.0,
    ) -> bool:
        """Poll GET /simulation/status until state matches target_state.

        Args:
            target_state: The state to wait for.
            timeout: Maximum time to wait in seconds.
            check_interval: Time between checks in seconds.

        Returns:
            True if reached target state, False on timeout.
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                status = self.get_simulation_status()
                if status.state.lower() == target_state.lower():
                    return True
            except Exception:
                pass
            time.sleep(check_interval)

        return False

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get performance metrics from the simulation.

        Returns:
            Performance metrics data.
        """
        return self._get("/metrics/performance")

    def is_available(self) -> bool:
        """Check if the simulation API is available and ready.

        Returns:
            True if API is available, False otherwise.
        """
        try:
            if not self.health_check():
                return False
            # Also verify we can get status
            self.get_simulation_status()
            return True
        except Exception:
            return False
