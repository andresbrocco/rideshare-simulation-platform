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


def _make_controller(max_speed: float = 128.0) -> PerformanceController:
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
            (128.0, 128.0),
            (6.75, 4.0),
            (3.375, 2.0),
            (0.4, 0.5),
            (31.9, 16.0),
            (1.0, 1.0),
            (0.5, 0.5),
            (15.999, 8.0),
            (256.0, 128.0),
        ],
    )
    def test_snaps_correctly(self, speed: float, expected: float) -> None:
        assert _snap_to_floor_power_of_two(speed) == expected

    def test_below_minimum_returns_minimum(self) -> None:
        # 0.1 < 0.5 but function still returns 0.5 (floor within list)
        assert _snap_to_floor_power_of_two(0.01) == 0.5


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
    max_speed: float = 128.0,
    min_speed: float = 0.5,
    target: float = 0.66,
    k_up: float = 0.15,
    k_down: float = 1.5,
    smoothness: float = 12.0,
    ki: float = 0.0,
    kd: float = 0.0,
    integral_max: float = 5.0,
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
            "ki": ki,
            "kd": kd,
            "integral_max": integral_max,
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
        new_speed = ctrl.decide_speed(0.66)
        assert abs(new_speed - 10.0) < 0.01

    def test_above_target_speed_increases(self) -> None:
        """Index above target → speed should increase."""
        ctrl = _make_controller_with_speed(current_speed=10.0)
        new_speed = ctrl.decide_speed(0.86)
        assert new_speed > 10.0

    def test_below_target_speed_decreases(self) -> None:
        """Index below target → speed should decrease."""
        ctrl = _make_controller_with_speed(current_speed=10.0)
        new_speed = ctrl.decide_speed(0.46)
        assert new_speed < 10.0

    def test_asymmetry_decrease_larger_than_increase(self) -> None:
        """For symmetric |error|, decrease magnitude >> increase magnitude."""
        ctrl_up = _make_controller_with_speed(current_speed=10.0)
        ctrl_down = _make_controller_with_speed(current_speed=10.0)

        speed_up = ctrl_up.decide_speed(0.86)  # +0.20 above target
        speed_down = ctrl_down.decide_speed(0.46)  # -0.20 below target

        increase = speed_up - 10.0
        decrease = 10.0 - speed_down
        assert (
            decrease > increase * 2
        ), f"decrease ({decrease:.3f}) should be much larger than increase ({increase:.3f})"

    def test_clamped_to_max_speed(self) -> None:
        """Speed cannot exceed max_speed even with very high index."""
        ctrl = _make_controller_with_speed(current_speed=30.0, max_speed=128.0)
        new_speed = ctrl.decide_speed(1.0)
        assert new_speed <= 128.0

    def test_clamped_to_min_speed(self) -> None:
        """Speed cannot go below min_speed even with very low index."""
        ctrl = _make_controller_with_speed(current_speed=1.0, min_speed=0.5)
        new_speed = ctrl.decide_speed(0.10)
        assert new_speed >= 0.5

    def test_severely_degraded_aggressive_cut(self) -> None:
        """Index=0.10 → >50% speed reduction (aggressive emergency cut)."""
        ctrl = _make_controller_with_speed(current_speed=16.0)
        new_speed = ctrl.decide_speed(0.10)
        reduction_pct = (16.0 - new_speed) / 16.0
        assert reduction_pct > 0.50, (
            f"Expected >50% reduction, got {reduction_pct * 100:.1f}% " f"(speed: {new_speed:.3f})"
        )

    def test_continuous_near_target_small_adjustments(self) -> None:
        """Small deviations near target produce small speed adjustments.

        Note: asymmetry means below-target adjustments are intentionally larger
        than above-target ones, so the tolerance is wider below target.
        """
        ctrl_above = _make_controller_with_speed(current_speed=10.0)
        ctrl_below = _make_controller_with_speed(current_speed=10.0)
        speed_slightly_above = ctrl_above.decide_speed(0.68)
        speed_slightly_below = ctrl_below.decide_speed(0.64)

        # Above target: gentle ramp — within 5%
        assert abs(speed_slightly_above - 10.0) / 10.0 < 0.05
        # Below target: asymmetric response is larger — within 10%
        assert abs(speed_slightly_below - 10.0) / 10.0 < 0.10
        # But still clearly smaller than a large deviation (e.g. index=0.46)
        ctrl_large = _make_controller_with_speed(current_speed=10.0)
        speed_large_drop = ctrl_large.decide_speed(0.46)
        assert (10.0 - speed_slightly_below) < (10.0 - speed_large_drop)


# ------------------------------------------------------------------
# PID-specific decide_speed tests
# ------------------------------------------------------------------


class TestPIDDecideSpeed:
    """Verify PID integral and derivative behavior."""

    def test_integral_accumulates_over_multiple_calls(self) -> None:
        """Repeated below-target calls produce progressively larger cuts."""
        ctrl = _make_controller_with_speed(current_speed=10.0, ki=0.02)
        cuts: list[float] = []
        for _ in range(5):
            new_speed = ctrl.decide_speed(0.46)
            cuts.append(10.0 - new_speed)
            # Reset speed for fair comparison of the factor
            ctrl._current_speed = 10.0

        # Each cut should be larger than the previous (integral accumulates)
        for i in range(1, len(cuts)):
            assert (
                cuts[i] > cuts[i - 1]
            ), f"Cut {i} ({cuts[i]:.4f}) should be larger than cut {i - 1} ({cuts[i - 1]:.4f})"

    def test_integral_anti_windup_clamps(self) -> None:
        """Negative integral clamped at -integral_max."""
        ctrl = _make_controller_with_speed(current_speed=10.0, ki=0.02, integral_max=2.0)
        # Drive integral deeply negative with many below-target calls
        for _ in range(100):
            ctrl.decide_speed(0.10)
            ctrl._current_speed = 10.0

        assert ctrl._error_integral == pytest.approx(-2.0)

    def test_integral_anti_windup_clamps_positive(self) -> None:
        """Positive integral clamped at +integral_max."""
        ctrl = _make_controller_with_speed(current_speed=10.0, ki=0.02, integral_max=2.0)
        # Drive integral positive with many above-target calls
        for _ in range(100):
            ctrl.decide_speed(0.96)
            ctrl._current_speed = 10.0

        assert ctrl._error_integral == pytest.approx(2.0)

    def test_derivative_dampens_improving_error(self) -> None:
        """D-term resists cutting when error is improving (compare to P-only)."""
        # P-only controller
        ctrl_p = _make_controller_with_speed(current_speed=10.0, kd=0.0)
        ctrl_p.decide_speed(0.46)  # First call to set previous_error
        ctrl_p._current_speed = 10.0
        speed_p = ctrl_p.decide_speed(0.56)  # Error improving toward target

        # PID controller with derivative
        ctrl_pid = _make_controller_with_speed(current_speed=10.0, kd=0.5)
        ctrl_pid.decide_speed(0.46)  # First call to set previous_error
        ctrl_pid._current_speed = 10.0
        speed_pid = ctrl_pid.decide_speed(0.56)  # Error improving toward target

        # D-term should resist cutting (speed higher with derivative dampening)
        assert speed_pid > speed_p, (
            f"PID speed ({speed_pid:.4f}) should be higher than P-only ({speed_p:.4f}) "
            "when error is improving"
        )

    def test_derivative_skipped_on_first_cycle(self) -> None:
        """First call with kd=10.0 matches kd=0.0 (no previous error)."""
        ctrl_no_d = _make_controller_with_speed(current_speed=10.0, kd=0.0)
        ctrl_with_d = _make_controller_with_speed(current_speed=10.0, kd=10.0)

        speed_no_d = ctrl_no_d.decide_speed(0.46)
        speed_with_d = ctrl_with_d.decide_speed(0.46)

        assert speed_no_d == pytest.approx(speed_with_d, rel=1e-9)

    @patch("src.controller.update_mode")
    def test_mode_toggle_resets_pid_state(self, _mock_mode: MagicMock) -> None:
        """set_mode('on') zeroes integral and clears previous_error."""
        ctrl = _make_controller_with_speed(current_speed=10.0, ki=0.02)
        # Accumulate some PID state
        ctrl.decide_speed(0.46)
        ctrl.decide_speed(0.46)
        assert ctrl._error_integral != 0.0
        assert ctrl._previous_error is not None

        # Mock the simulation fetch
        mock_response = MagicMock()
        mock_response.json.return_value = {"speed_multiplier": 10.0}
        mock_response.raise_for_status = MagicMock()
        ctrl._sim_client = MagicMock()
        ctrl._sim_client.get.return_value = mock_response

        # Toggle mode on — should reset PID state
        ctrl._mode = "off"  # Ensure transition happens
        ctrl.set_mode("on")

        assert ctrl._error_integral == 0.0
        assert ctrl._previous_error is None
        assert ctrl._last_derivative == 0.0

    def test_pure_p_mode_when_ki_kd_zero(self) -> None:
        """With ki=0, kd=0, output matches P-only identically."""
        ctrl_pid_zero = _make_controller_with_speed(current_speed=10.0, ki=0.0, kd=0.0)
        ctrl_default = _make_controller_with_speed(current_speed=10.0)

        for index in [0.10, 0.46, 0.66, 0.86, 0.96]:
            ctrl_pid_zero._current_speed = 10.0
            ctrl_default._current_speed = 10.0
            # Reset PID state for fair comparison
            ctrl_pid_zero._reset_pid_state()
            ctrl_default._reset_pid_state()
            speed_pid = ctrl_pid_zero.decide_speed(index)
            speed_default = ctrl_default.decide_speed(index)
            assert speed_pid == pytest.approx(
                speed_default, rel=1e-9
            ), f"At index={index}: PID({speed_pid:.6f}) != P-only({speed_default:.6f})"
