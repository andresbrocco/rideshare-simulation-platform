"""Tests for performance controller mode switching and speed snapping."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.controller import PerformanceController, _snap_to_floor_power_of_two
from src.settings import Settings


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_controller(max_speed: float = 32.0) -> PerformanceController:
    """Create a controller with mocked external dependencies."""
    settings = Settings(
        controller={"max_speed": max_speed},
        simulation={"api_key": "test-key"},
    )
    with patch("src.controller.PrometheusClient"):
        ctrl = PerformanceController(settings)
    return ctrl


# ------------------------------------------------------------------
# _snap_to_floor_power_of_two
# ------------------------------------------------------------------


class TestSnapToFloorPowerOfTwo:
    """Verify snapping to the largest valid speed <= the input."""

    @pytest.mark.parametrize(
        ("speed", "expected"),
        [
            (32.0, 32.0),
            (6.75, 4.0),
            (3.375, 2.0),
            (0.1, 0.125),
            (31.9, 16.0),
            (1.0, 1.0),
            (0.125, 0.125),
            (0.5, 0.5),
            (15.999, 8.0),
            (64.0, 32.0),
        ],
    )
    def test_snaps_correctly(self, speed: float, expected: float) -> None:
        assert _snap_to_floor_power_of_two(speed) == expected

    def test_below_minimum_returns_minimum(self) -> None:
        # 0.1 < 0.125 but function still returns 0.125 (floor within list)
        assert _snap_to_floor_power_of_two(0.01) == 0.125


# ------------------------------------------------------------------
# set_mode("on") — seed speed from simulation
# ------------------------------------------------------------------


class TestSetModeOn:
    """Verify that turning auto-control ON seeds speed from simulation."""

    @patch("src.controller.update_mode")
    def test_seeds_speed_from_simulation(self, _mock_mode: MagicMock) -> None:
        ctrl = _make_controller()
        mock_response = MagicMock()
        mock_response.json.return_value = {"speed_multiplier": 2.0}
        mock_response.raise_for_status = MagicMock()
        ctrl._sim_client = MagicMock()
        ctrl._sim_client.get.return_value = mock_response

        ctrl.set_mode("on")

        assert ctrl.current_speed == 2.0
        ctrl._sim_client.get.assert_called_once_with(
            "/simulation/status",
            headers={"X-API-Key": "test-key"},
        )

    @patch("src.controller.update_mode")
    def test_keeps_current_speed_when_fetch_fails(self, _mock_mode: MagicMock) -> None:
        ctrl = _make_controller()
        original_speed = ctrl.current_speed
        ctrl._sim_client = MagicMock()
        ctrl._sim_client.get.side_effect = httpx.ConnectError("unreachable")

        ctrl.set_mode("on")

        assert ctrl.current_speed == original_speed

    @patch("src.controller.update_mode")
    def test_idempotent_when_already_on(self, _mock_mode: MagicMock) -> None:
        ctrl = _make_controller()
        ctrl._sim_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"speed_multiplier": 4.0}
        mock_response.raise_for_status = MagicMock()
        ctrl._sim_client.get.return_value = mock_response

        ctrl.set_mode("on")
        assert ctrl.current_speed == 4.0

        # Second call — already on, should not re-fetch
        ctrl._sim_client.get.reset_mock()
        ctrl.set_mode("on")
        ctrl._sim_client.get.assert_not_called()


# ------------------------------------------------------------------
# set_mode("off") — snap to power-of-2
# ------------------------------------------------------------------


class TestSetModeOff:
    """Verify that turning auto-control OFF snaps speed to a valid dropdown value."""

    @patch("src.controller.update_mode")
    def test_snaps_and_actuates(self, _mock_mode: MagicMock) -> None:
        ctrl = _make_controller()
        ctrl._mode = "on"
        ctrl._current_speed = 6.75

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"multiplier": 4.0}
        ctrl._sim_client = MagicMock()
        ctrl._sim_client.put.return_value = mock_response

        ctrl.set_mode("off")

        assert ctrl.current_speed == 4.0
        ctrl._sim_client.put.assert_called_once_with(
            "/simulation/speed",
            json={"multiplier": 4.0},
            headers={"X-API-Key": "test-key"},
        )

    @patch("src.controller.update_mode")
    def test_skips_actuation_when_already_power_of_two(self, _mock_mode: MagicMock) -> None:
        ctrl = _make_controller()
        ctrl._mode = "on"
        ctrl._current_speed = 8.0
        ctrl._sim_client = MagicMock()

        ctrl.set_mode("off")

        assert ctrl.current_speed == 8.0
        ctrl._sim_client.put.assert_not_called()

    @patch("src.controller.update_mode")
    def test_preserves_speed_on_actuation_failure(self, _mock_mode: MagicMock) -> None:
        ctrl = _make_controller()
        ctrl._mode = "on"
        ctrl._current_speed = 3.0
        ctrl._sim_client = MagicMock()
        ctrl._sim_client.put.side_effect = httpx.ConnectError("unreachable")

        ctrl.set_mode("off")

        # Speed stays at 3.0 because actuation failed
        assert ctrl.current_speed == 3.0

    @patch("src.controller.update_mode")
    def test_idempotent_when_already_off(self, _mock_mode: MagicMock) -> None:
        ctrl = _make_controller()
        ctrl._mode = "off"
        ctrl._current_speed = 6.75
        ctrl._sim_client = MagicMock()

        ctrl.set_mode("off")

        # No mode transition → no snapping
        assert ctrl.current_speed == 6.75
        ctrl._sim_client.put.assert_not_called()
