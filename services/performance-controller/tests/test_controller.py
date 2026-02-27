"""Tests for performance controller mode switching, speed snapping, and decide_speed."""

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


# ------------------------------------------------------------------
# decide_speed — continuous asymmetric proportional controller
# ------------------------------------------------------------------


def _make_controller_with_speed(
    current_speed: float = 10.0,
    max_speed: float = 32.0,
    min_speed: float = 0.125,
    target: float = 0.70,
    k_up: float = 0.3,
    k_down: float = 5.0,
    smoothness: float = 12.0,
) -> PerformanceController:
    """Create a controller seeded at a specific speed for decide_speed tests."""
    settings = Settings(
        controller={
            "max_speed": max_speed,
            "min_speed": min_speed,
            "target": target,
            "k_up": k_up,
            "k_down": k_down,
            "smoothness": smoothness,
        },
        simulation={"api_key": "test-key"},
    )
    with patch("src.controller.PrometheusClient"):
        ctrl = PerformanceController(settings)
    ctrl._current_speed = current_speed
    return ctrl


class TestDecideSpeed:
    """Verify continuous asymmetric proportional controller behavior."""

    def test_at_target_speed_unchanged(self) -> None:
        """At exactly the target index, factor ≈ 1 so speed stays the same."""
        ctrl = _make_controller_with_speed(current_speed=10.0)
        new_speed = ctrl.decide_speed(0.70)
        assert abs(new_speed - 10.0) < 0.01

    def test_above_target_speed_increases(self) -> None:
        """Index above target → speed should increase."""
        ctrl = _make_controller_with_speed(current_speed=10.0)
        new_speed = ctrl.decide_speed(0.90)
        assert new_speed > 10.0

    def test_below_target_speed_decreases(self) -> None:
        """Index below target → speed should decrease."""
        ctrl = _make_controller_with_speed(current_speed=10.0)
        new_speed = ctrl.decide_speed(0.50)
        assert new_speed < 10.0

    def test_asymmetry_decrease_larger_than_increase(self) -> None:
        """For symmetric |error|, decrease magnitude >> increase magnitude."""
        ctrl_up = _make_controller_with_speed(current_speed=10.0)
        ctrl_down = _make_controller_with_speed(current_speed=10.0)

        speed_up = ctrl_up.decide_speed(0.90)  # +0.20 above target
        speed_down = ctrl_down.decide_speed(0.50)  # -0.20 below target

        increase = speed_up - 10.0
        decrease = 10.0 - speed_down
        assert (
            decrease > increase * 2
        ), f"decrease ({decrease:.3f}) should be much larger than increase ({increase:.3f})"

    def test_clamped_to_max_speed(self) -> None:
        """Speed cannot exceed max_speed even with very high index."""
        ctrl = _make_controller_with_speed(current_speed=30.0, max_speed=32.0)
        new_speed = ctrl.decide_speed(1.0)
        assert new_speed <= 32.0

    def test_clamped_to_min_speed(self) -> None:
        """Speed cannot go below min_speed even with very low index."""
        ctrl = _make_controller_with_speed(current_speed=0.5, min_speed=0.125)
        new_speed = ctrl.decide_speed(0.10)
        assert new_speed >= 0.125

    def test_severely_degraded_aggressive_cut(self) -> None:
        """Index=0.10 → >90% speed reduction (aggressive emergency cut)."""
        ctrl = _make_controller_with_speed(current_speed=16.0)
        new_speed = ctrl.decide_speed(0.10)
        reduction_pct = (16.0 - new_speed) / 16.0
        assert reduction_pct > 0.90, (
            f"Expected >90% reduction, got {reduction_pct * 100:.1f}% " f"(speed: {new_speed:.3f})"
        )

    def test_continuous_near_target_small_adjustments(self) -> None:
        """Small deviations near target produce small speed adjustments.

        Note: asymmetry means below-target adjustments are intentionally larger
        than above-target ones, so the tolerance is wider below target.
        """
        ctrl_above = _make_controller_with_speed(current_speed=10.0)
        ctrl_below = _make_controller_with_speed(current_speed=10.0)
        speed_slightly_above = ctrl_above.decide_speed(0.72)
        speed_slightly_below = ctrl_below.decide_speed(0.68)

        # Above target: gentle ramp — within 5%
        assert abs(speed_slightly_above - 10.0) / 10.0 < 0.05
        # Below target: asymmetric response is larger — within 10%
        assert abs(speed_slightly_below - 10.0) / 10.0 < 0.10
        # But still clearly smaller than a large deviation (e.g. index=0.30)
        ctrl_large = _make_controller_with_speed(current_speed=10.0)
        speed_large_drop = ctrl_large.decide_speed(0.30)
        assert (10.0 - speed_slightly_below) < (10.0 - speed_large_drop)
