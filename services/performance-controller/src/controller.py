"""Performance controller — reads index from Prometheus, throttle logic."""

from __future__ import annotations

import logging
import math
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
        self._current_speed: float = settings.controller.max_speed
        self._infrastructure_headroom: float = 1.0

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
    def infrastructure_headroom(self) -> float:
        return self._infrastructure_headroom

    # ------------------------------------------------------------------
    # Throttle decision
    # ------------------------------------------------------------------

    def decide_speed(self, index: float) -> float:
        """Decide the speed using a continuous asymmetric proportional controller.

        A sigmoid blends between k_down (aggressive cut) and k_up (gentle ramp),
        producing smooth increases but fast emergency reductions around a target
        setpoint — all without discrete thresholds.
        """
        cfg = self._settings.controller

        error = index - cfg.target
        blend = 1.0 / (1.0 + math.exp(-cfg.smoothness * error))
        effective_k = cfg.k_down + (cfg.k_up - cfg.k_down) * blend
        factor = math.exp(effective_k * error)
        new_speed = max(cfg.min_speed, min(self._current_speed * factor, cfg.max_speed))

        if new_speed > self._current_speed:
            logger.info(
                "INCREASE: index=%.2f (target=%.2f) → speed %.3f → %.3f (factor=%.4f)",
                index,
                cfg.target,
                self._current_speed,
                new_speed,
                factor,
            )
        elif new_speed < self._current_speed:
            logger.info(
                "DECREASE: index=%.2f (target=%.2f) → speed %.3f → %.3f (factor=%.4f)",
                index,
                cfg.target,
                self._current_speed,
                new_speed,
                factor,
            )

        return new_speed

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
            index = self._prom.get_infrastructure_headroom()
            if index is None:
                logger.debug("No infrastructure headroom available, skipping cycle")
                time.sleep(cfg.poll_interval_seconds)
                continue

            self._infrastructure_headroom = index
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
