"""Performance controller — reads index from Prometheus, throttle logic."""

from __future__ import annotations

import logging
import time

import httpx

from .metrics_exporter import record_adjustment, update_mode, update_snapshot
from .prometheus_client import PrometheusClient
from .settings import Settings

logger = logging.getLogger(__name__)

_VALID_MANUAL_SPEEDS: list[float] = [0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0]


def _snap_to_floor_power_of_two(speed: float) -> float:
    """Return the largest value from _VALID_MANUAL_SPEEDS that is <= speed."""
    result = _VALID_MANUAL_SPEEDS[0]
    for v in _VALID_MANUAL_SPEEDS:
        if v <= speed:
            result = v
        else:
            break
    return result


class PerformanceController:
    """Monitors Prometheus recording rules and auto-throttles simulation speed."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._prom = PrometheusClient(settings.prometheus.url)
        self._sim_client = httpx.Client(
            base_url=settings.simulation.base_url,
            timeout=5.0,
        )
        self._api_key = settings.simulation.api_key

        self._running = False
        self._mode: str = "off"
        self._consecutive_healthy = 0
        self._current_speed: float = settings.controller.max_speed
        self._performance_index: float = 1.0

    # ------------------------------------------------------------------
    # Public state accessors (used by api.py)
    # ------------------------------------------------------------------

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        if mode not in ("on", "off"):
            raise ValueError(f"Invalid mode: {mode!r}, must be 'on' or 'off'")
        old = self._mode
        self._mode = mode
        update_mode(mode == "on")
        if old != mode:
            logger.info("Controller mode changed: %s → %s", old, mode)
            if mode == "on":
                live_speed = self._fetch_current_speed()
                if live_speed is not None:
                    self._current_speed = live_speed
                    logger.info(
                        "Seeded controller speed from simulation: %.2f",
                        live_speed,
                    )
            elif mode == "off":
                self._consecutive_healthy = 0
                snapped = _snap_to_floor_power_of_two(self._current_speed)
                if abs(snapped - self._current_speed) > 0.001:
                    logger.info(
                        "Snapped speed from %.2f to %.2f",
                        self._current_speed,
                        snapped,
                    )
                    if self.actuate_speed(snapped):
                        self._current_speed = snapped

    def _fetch_current_speed(self) -> float | None:
        """Fetch the simulation's current speed multiplier via GET /simulation/status."""
        try:
            resp = self._sim_client.get(
                "/simulation/status",
                headers={"X-API-Key": self._api_key},
            )
            resp.raise_for_status()
            return float(resp.json()["speed_multiplier"])
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            logger.warning("Failed to fetch simulation speed: %s", exc)
            return None

    @property
    def current_speed(self) -> float:
        return self._current_speed

    @property
    def performance_index(self) -> float:
        return self._performance_index

    @property
    def consecutive_healthy(self) -> int:
        return self._consecutive_healthy

    # ------------------------------------------------------------------
    # Throttle decision
    # ------------------------------------------------------------------

    def decide_speed(self, index: float) -> float:
        """Decide the speed based on the performance index using geometric ramping."""
        cfg = self._settings.controller

        if index < cfg.critical_threshold:
            # Critical — aggressive reduction (divide by ramp_factor²)
            new_speed = max(cfg.min_speed, self._current_speed / (cfg.ramp_factor**2))
            self._consecutive_healthy = 0
            logger.warning(
                "CRITICAL: index=%.2f < %.2f → reducing speed %.2f → %.2f",
                index,
                cfg.critical_threshold,
                self._current_speed,
                new_speed,
            )
            return new_speed

        if index < cfg.warning_threshold:
            # Warning — moderate reduction (divide by ramp_factor)
            new_speed = max(cfg.min_speed, self._current_speed / cfg.ramp_factor)
            self._consecutive_healthy = 0
            logger.warning(
                "WARNING: index=%.2f < %.2f → reducing speed %.2f → %.2f",
                index,
                cfg.warning_threshold,
                self._current_speed,
                new_speed,
            )
            return new_speed

        if index >= cfg.healthy_threshold:
            self._consecutive_healthy += 1
            if self._consecutive_healthy >= cfg.healthy_cycles_required:
                # Healthy for long enough — ramp up (multiply by ramp_factor, capped at max)
                new_speed = min(self._current_speed * cfg.ramp_factor, cfg.max_speed)
                if new_speed > self._current_speed:
                    logger.info(
                        "HEALTHY: index=%.2f for %d cycles → increasing speed %.2f → %.2f",
                        index,
                        self._consecutive_healthy,
                        self._current_speed,
                        new_speed,
                    )
                    self._consecutive_healthy = 0
                    return new_speed
            return self._current_speed

        # Between warning and healthy thresholds — hold steady
        self._consecutive_healthy = 0
        return self._current_speed

    # ------------------------------------------------------------------
    # Actuation
    # ------------------------------------------------------------------

    def actuate_speed(self, new_speed: float) -> bool:
        """Call PUT /simulation/speed to change the simulation speed."""
        try:
            resp = self._sim_client.put(
                "/simulation/speed",
                json={"multiplier": new_speed},
                headers={"X-API-Key": self._api_key},
            )
            resp.raise_for_status()
            logger.info("Speed actuated: %.2f (response: %s)", new_speed, resp.json())
            return True
        except httpx.HTTPError as exc:
            logger.error("Failed to actuate speed %.2f: %s", new_speed, exc)
            return False

    # ------------------------------------------------------------------
    # Main control loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Enter the control loop (no baseline calibration)."""
        self._running = True
        cfg = self._settings.controller

        if cfg.max_speed < 4:
            logger.warning(
                "max_speed=%.2f — throttle has limited headroom below 4x",
                cfg.max_speed,
            )

        # Wait for Prometheus to be reachable
        while self._running and not self._prom.is_available():
            logger.info("Waiting for Prometheus at %s...", self._settings.prometheus.url)
            time.sleep(cfg.poll_interval_seconds)

        if not self._running:
            return

        logger.info("Entering control loop (poll every %.1fs)", cfg.poll_interval_seconds)

        while self._running:
            index = self._prom.get_performance_index()
            if index is None:
                logger.debug("No performance index available, skipping cycle")
                time.sleep(cfg.poll_interval_seconds)
                continue

            self._performance_index = index
            update_snapshot(index, float(self._current_speed))

            if self._mode == "on":
                new_speed = self.decide_speed(index)
                if abs(new_speed - self._current_speed) > 0.001:
                    if self.actuate_speed(new_speed):
                        self._current_speed = new_speed
                        record_adjustment()
                        update_snapshot(index, float(self._current_speed))

            time.sleep(cfg.poll_interval_seconds)

    def stop(self) -> None:
        """Signal the control loop to exit and clean up resources."""
        logger.info("Stopping performance controller...")
        self._running = False
        self._prom.close()
        self._sim_client.close()
