"""Performance controller — baseline calibration, index computation, throttle logic."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from .metrics_exporter import record_adjustment, update_baseline, update_snapshot
from .prometheus_client import PrometheusClient, SaturationMetrics
from .settings import Settings

logger = logging.getLogger(__name__)

# Sensible floors so we never divide by zero when baseline observes zeros
_MIN_LAG_CAPACITY = 100.0
_MIN_QUEUE_CAPACITY = 50.0
_MIN_THROUGHPUT = 0.1
_MIN_RTR = 0.1


@dataclass(frozen=True)
class BaselineCalibration:
    """Derived capacity limits from the baseline observation window."""

    lag_capacity: float
    queue_capacity: float
    steady_throughput: float
    steady_rtr: float


class PerformanceController:
    """Monitors Prometheus metrics and auto-throttles simulation speed."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._prom = PrometheusClient(settings.prometheus.url)
        self._sim_client = httpx.Client(
            base_url=settings.simulation.base_url,
            timeout=5.0,
        )
        self._api_key = settings.simulation.api_key

        self._running = False
        self._baseline: BaselineCalibration | None = None
        self._consecutive_healthy = 0
        self._current_speed: int = settings.controller.target_speed
        self._performance_index: float = 1.0

    # ------------------------------------------------------------------
    # Public state accessors (used by api.py)
    # ------------------------------------------------------------------

    @property
    def baseline(self) -> BaselineCalibration | None:
        return self._baseline

    @property
    def baseline_complete(self) -> bool:
        return self._baseline is not None

    @property
    def current_speed(self) -> int:
        return self._current_speed

    @property
    def performance_index(self) -> float:
        return self._performance_index

    @property
    def consecutive_healthy(self) -> int:
        return self._consecutive_healthy

    # ------------------------------------------------------------------
    # Baseline calibration
    # ------------------------------------------------------------------

    def run_baseline_calibration(self) -> BaselineCalibration:
        """Collect metric samples over the baseline window and derive capacities."""
        cfg = self._settings.controller
        logger.info(
            "Starting baseline calibration (%.0fs window)...",
            cfg.baseline_duration_seconds,
        )

        max_lag = 0.0
        max_queue = 0.0
        throughput_samples: list[float] = []
        rtr_samples: list[float] = []

        deadline = time.monotonic() + cfg.baseline_duration_seconds
        while time.monotonic() < deadline and self._running:
            metrics = self._prom.get_saturation_metrics()
            if metrics is not None:
                if metrics.kafka_lag is not None:
                    max_lag = max(max_lag, metrics.kafka_lag)
                if metrics.simpy_queue is not None:
                    max_queue = max(max_queue, metrics.simpy_queue)
                if metrics.produced_rate is not None:
                    throughput_samples.append(metrics.produced_rate)
                if metrics.real_time_ratio is not None:
                    rtr_samples.append(metrics.real_time_ratio)
            time.sleep(cfg.poll_interval_seconds)

        lag_capacity = max(max_lag * cfg.lag_capacity_multiplier, _MIN_LAG_CAPACITY)
        queue_capacity = max(max_queue * cfg.queue_capacity_multiplier, _MIN_QUEUE_CAPACITY)
        steady_throughput = (
            sum(throughput_samples) / len(throughput_samples)
            if throughput_samples
            else _MIN_THROUGHPUT
        )
        steady_rtr = sum(rtr_samples) / len(rtr_samples) if rtr_samples else _MIN_RTR

        baseline = BaselineCalibration(
            lag_capacity=lag_capacity,
            queue_capacity=queue_capacity,
            steady_throughput=steady_throughput,
            steady_rtr=steady_rtr,
        )

        logger.info(
            "Baseline calibration complete: lag_cap=%.0f queue_cap=%.0f "
            "throughput=%.1f rtr=%.2f",
            baseline.lag_capacity,
            baseline.queue_capacity,
            baseline.steady_throughput,
            baseline.steady_rtr,
        )
        update_baseline(baseline.lag_capacity, baseline.queue_capacity)
        return baseline

    # ------------------------------------------------------------------
    # Performance index computation
    # ------------------------------------------------------------------

    def compute_performance_index(self, metrics: SaturationMetrics) -> float:
        """Compute composite performance index (0–1). Lower = more saturated."""
        assert self._baseline is not None
        bl = self._baseline

        components: list[float] = []

        # Kafka lag headroom
        if metrics.kafka_lag is not None:
            components.append(1.0 - metrics.kafka_lag / bl.lag_capacity)

        # SimPy queue headroom
        if metrics.simpy_queue is not None:
            components.append(1.0 - metrics.simpy_queue / bl.queue_capacity)

        # CPU headroom
        if metrics.cpu_percent is not None:
            components.append(1.0 - metrics.cpu_percent / 100.0)

        # Memory headroom
        if metrics.memory_percent is not None:
            components.append(1.0 - metrics.memory_percent / 100.0)

        # Throughput ratio (consumed / produced)
        if metrics.consumed_rate is not None and metrics.produced_rate is not None:
            produced = max(metrics.produced_rate, _MIN_THROUGHPUT)
            components.append(metrics.consumed_rate / produced)

        # RTR ratio (current / baseline)
        if metrics.real_time_ratio is not None:
            baseline_rtr = max(bl.steady_rtr, _MIN_RTR)
            components.append(metrics.real_time_ratio / baseline_rtr)

        if not components:
            # No data at all — assume healthy to avoid unnecessary throttle
            return 1.0

        # Clamp to [0, 1]
        return max(0.0, min(1.0, min(components)))

    # ------------------------------------------------------------------
    # Throttle decision
    # ------------------------------------------------------------------

    def decide_speed(self, index: float) -> int:
        """Decide the target speed based on the performance index."""
        cfg = self._settings.controller

        if index < cfg.critical_threshold:
            # Critical — aggressive reduction
            new_speed = max(1, int(self._current_speed * 0.25))
            self._consecutive_healthy = 0
            logger.warning(
                "CRITICAL: index=%.2f < %.2f → reducing speed %d → %d",
                index,
                cfg.critical_threshold,
                self._current_speed,
                new_speed,
            )
            return new_speed

        if index < cfg.warning_threshold:
            # Warning — moderate reduction
            new_speed = max(1, int(self._current_speed * 0.5))
            self._consecutive_healthy = 0
            logger.warning(
                "WARNING: index=%.2f < %.2f → reducing speed %d → %d",
                index,
                cfg.warning_threshold,
                self._current_speed,
                new_speed,
            )
            return new_speed

        if index >= cfg.healthy_threshold:
            self._consecutive_healthy += 1
            if self._consecutive_healthy >= cfg.healthy_cycles_required:
                # Healthy for long enough — double speed (capped at target)
                new_speed = min(self._current_speed * 2, cfg.target_speed)
                if new_speed > self._current_speed:
                    logger.info(
                        "HEALTHY: index=%.2f for %d cycles → increasing speed %d → %d",
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

    def actuate_speed(self, new_speed: int) -> bool:
        """Call PUT /simulation/speed to change the simulation speed."""
        try:
            resp = self._sim_client.put(
                "/simulation/speed",
                json={"multiplier": new_speed},
                headers={"X-API-Key": self._api_key},
            )
            resp.raise_for_status()
            logger.info("Speed actuated: %d (response: %s)", new_speed, resp.json())
            return True
        except httpx.HTTPError as exc:
            logger.error("Failed to actuate speed %d: %s", new_speed, exc)
            return False

    # ------------------------------------------------------------------
    # Main control loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Run baseline calibration then enter the control loop."""
        self._running = True
        cfg = self._settings.controller

        if cfg.target_speed < 4:
            logger.warning(
                "target_speed=%d — throttle has limited headroom below 4x",
                cfg.target_speed,
            )

        # Wait for Prometheus to be reachable
        while self._running and not self._prom.is_available():
            logger.info("Waiting for Prometheus at %s...", self._settings.prometheus.url)
            time.sleep(cfg.poll_interval_seconds)

        if not self._running:
            return

        # Baseline calibration
        self._baseline = self.run_baseline_calibration()
        if not self._running:
            return

        logger.info("Entering control loop (poll every %.1fs)", cfg.poll_interval_seconds)

        while self._running:
            metrics = self._prom.get_saturation_metrics()
            if metrics is None:
                logger.debug("No metrics available, skipping cycle")
                time.sleep(cfg.poll_interval_seconds)
                continue

            index = self.compute_performance_index(metrics)
            self._performance_index = index

            new_speed = self.decide_speed(index)
            update_snapshot(index, float(new_speed))

            if new_speed != self._current_speed:
                if self.actuate_speed(new_speed):
                    self._current_speed = new_speed
                    record_adjustment()

            time.sleep(cfg.poll_interval_seconds)

    def stop(self) -> None:
        """Signal the control loop to exit and clean up resources."""
        logger.info("Stopping performance controller...")
        self._running = False
        self._prom.close()
        self._sim_client.close()
