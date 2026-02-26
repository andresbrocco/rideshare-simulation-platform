"""Stress test scenario: spawn agents until resource threshold reached."""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterator

from rich.console import Console

from ..analysis.statistics import BaselineCalibration
from .base import BaseScenario

console = Console()


@dataclass
class RollingStats:
    """Rolling statistics for a single metric over a time window."""

    values: deque[float] = field(default_factory=deque)

    @classmethod
    def with_window(cls, max_samples: int) -> "RollingStats":
        """Create RollingStats with a specific window size.

        Args:
            max_samples: Maximum number of samples in the rolling window.

        Returns:
            RollingStats instance with the specified window size.
        """
        return cls(values=deque(maxlen=max_samples))

    @property
    def average(self) -> float:
        """Calculate rolling average."""
        if not self.values:
            return 0.0
        return sum(self.values) / len(self.values)

    def add(self, value: float) -> None:
        """Add a new value to the rolling window."""
        self.values.append(value)


@dataclass
class ContainerRollingStats:
    """Rolling statistics for both CPU and memory for a container."""

    memory_percent: RollingStats = field(default_factory=RollingStats)
    cpu_percent: RollingStats = field(default_factory=RollingStats)

    @classmethod
    def with_window(cls, max_samples: int) -> "ContainerRollingStats":
        """Create ContainerRollingStats with a specific window size.

        Args:
            max_samples: Maximum number of samples in the rolling window.

        Returns:
            ContainerRollingStats instance with the specified window size.
        """
        return cls(
            memory_percent=RollingStats.with_window(max_samples),
            cpu_percent=RollingStats.with_window(max_samples),
        )


@dataclass
class HealthRollingStats:
    """Rolling statistics for health latency of a service."""

    latency_ms: RollingStats = field(default_factory=RollingStats)

    @classmethod
    def with_window(cls, max_samples: int) -> "HealthRollingStats":
        """Create HealthRollingStats with a specific window size."""
        return cls(latency_ms=RollingStats.with_window(max_samples))


@dataclass
class ThresholdTrigger:
    """Records which container/metric triggered the threshold stop."""

    container: str
    metric: str  # "memory", "cpu", "health_latency"
    value: float
    threshold: float


class StressTestScenario(BaseScenario):
    """Stress test: continuously spawn agents until resource threshold reached.

    Spawns agents in batches until any container's rolling average (window size
    determined by stress_rolling_window_seconds / interval_seconds) hits the
    configured CPU or memory threshold.

    Protocol:
    1. Step 0: Clean environment (down -v, up -d, wait healthy)
    2. Start simulation
    3. Warmup period (collect baseline samples)
    4. Loop:
       a. Queue batch of drivers and riders
       b. Collect sample and update rolling averages
       c. Check if any threshold exceeded
       d. Wait spawn interval
    5. Stop when threshold hit or max duration reached
    6. Store metadata (trigger info, peak values, total agents)
    """

    def __init__(
        self,
        *args: Any,
        baseline_calibration: BaselineCalibration | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._baseline_calibration = baseline_calibration
        # Compute effective RTR threshold: prefer baseline-derived, else config fallback
        if baseline_calibration is not None and baseline_calibration.rtr_threshold is not None:
            self._effective_rtr_threshold = baseline_calibration.rtr_threshold
            self._rtr_threshold_source = baseline_calibration.rtr_threshold_source
        else:
            self._effective_rtr_threshold = self.config.scenarios.stress_rtr_threshold
            self._rtr_threshold_source = "config-fallback"
        # Calculate rolling window sample count from config
        # e.g., 10s window / 2s interval = 5 samples
        self._rolling_window_samples = int(
            self.config.scenarios.stress_rolling_window_seconds
            / self.config.sampling.interval_seconds
        )
        # Initialize rolling stats per container and global CPU
        self._rolling_stats: dict[str, ContainerRollingStats] = {}
        self._global_cpu_rolling = RollingStats.with_window(self._rolling_window_samples)
        # RTR rolling window (separate from CPU/memory window since RTR samples are noisier)
        rtr_window_samples = max(
            1,
            int(
                self.config.scenarios.stress_rtr_rolling_window_seconds
                / self.config.sampling.interval_seconds
            ),
        )
        self._rtr_rolling = RollingStats.with_window(rtr_window_samples)
        self._total_drivers_queued = 0
        self._total_riders_queued = 0
        self._trigger: ThresholdTrigger | None = None
        self._peak_values: dict[str, dict[str, float]] = {}
        self._health_rolling_stats: dict[str, HealthRollingStats] = {}
        self._health_latency_peaks: dict[str, float] = {}
        self._saturation_sample_counter = 0

    @property
    def name(self) -> str:
        return "stress_test"

    @property
    def requires_clean_restart(self) -> bool:
        """Stress test reuses baseline's idle state (0 agents)."""
        return False

    @property
    def description(self) -> str:
        return (
            f"Stress test: spawn agents until {self.params['global_cpu_threshold_percent']}% "
            f"global CPU, {self.params['memory_threshold_percent']}% memory, "
            f"RTR <= {self.params['rtr_threshold']} [{self.params['rtr_threshold_source']}], "
            f"or health latency [{self.params['health_threshold_source']}] reached"
        )

    @property
    def params(self) -> dict[str, Any]:
        return {
            "global_cpu_threshold_percent": self.config.scenarios.stress_global_cpu_threshold_percent,
            "memory_threshold_percent": self.config.scenarios.stress_memory_threshold_percent,
            "rtr_threshold": self._effective_rtr_threshold,
            "rtr_threshold_source": self._rtr_threshold_source,
            "health_threshold_source": (
                self._baseline_calibration.health_threshold_source
                if self._baseline_calibration is not None
                else "api-reported"
            ),
            "rolling_window_seconds": self.config.scenarios.stress_rolling_window_seconds,
            "rolling_window_samples": self._rolling_window_samples,
            "spawn_batch_size": self.config.scenarios.stress_spawn_batch_size,
            "spawn_interval_seconds": self.config.scenarios.stress_spawn_interval_seconds,
            "max_duration_minutes": self.config.scenarios.stress_max_duration_minutes,
        }

    def execute(self) -> Iterator[dict[str, Any]]:
        """Execute stress test."""
        # Start simulation
        console.print("[cyan]Starting simulation...[/cyan]")
        try:
            self.api_client.start()
        except Exception as e:
            console.print(f"[yellow]Start response: {e}[/yellow]")
        yield {"phase": "simulation_started"}

        # Warmup period - collect baseline samples to fill rolling window
        warmup_samples = self._rolling_window_samples
        console.print(f"[cyan]Warmup: collecting {warmup_samples} baseline samples...[/cyan]")
        for i in range(warmup_samples):
            self._collect_sample_with_rolling()
            if i < warmup_samples - 1:
                time.sleep(self.config.sampling.interval_seconds)
        yield {"phase": "warmup_complete"}

        # Main stress loop
        batch_size = self.config.scenarios.stress_spawn_batch_size
        spawn_interval = self.config.scenarios.stress_spawn_interval_seconds
        max_duration = self.config.scenarios.stress_max_duration_minutes * 60
        start_time = time.time()
        batch_count = 0

        console.print(
            f"[cyan]Stress test: spawning {batch_size} agents every {spawn_interval}s "
            f"until threshold or {self.config.scenarios.stress_max_duration_minutes}m max[/cyan]"
        )

        while time.time() - start_time < max_duration:
            if self._aborted:
                console.print(f"[red]Test aborted: {self._abort_reason}[/red]")
                break

            # Queue batch of drivers
            console.print(
                f"[dim]Batch {batch_count + 1}: queuing {batch_size} drivers + "
                f"{batch_size} riders...[/dim]",
                end="\r",
            )
            try:
                self.api_client.queue_drivers(batch_size)
                self._total_drivers_queued += batch_size
            except Exception as e:
                console.print(f"\n[yellow]Driver queue failed: {e}[/yellow]")

            # Queue batch of riders
            try:
                self.api_client.queue_riders(batch_size)
                self._total_riders_queued += batch_size
            except Exception as e:
                console.print(f"\n[yellow]Rider queue failed: {e}[/yellow]")

            batch_count += 1

            # Collect sample and update rolling averages
            self._collect_sample_with_rolling()

            # Check thresholds
            trigger = self._check_thresholds()
            if trigger:
                console.print(
                    f"\n[red bold]THRESHOLD REACHED: {trigger.container} "
                    f"{trigger.metric}={trigger.value:.1f}% >= {trigger.threshold}%[/red bold]"
                )
                self._trigger = trigger
                break

            # Check USL saturation stop (never pre-empts safety stops)
            saturation_trigger = self._check_saturation_stop()
            if saturation_trigger:
                console.print(
                    f"\n[yellow bold]SATURATION KNEE EXCEEDED: "
                    f"active_trips={saturation_trigger.value:.0f} > "
                    f"N*×{self.config.scenarios.saturation_overshoot_factor} "
                    f"= {saturation_trigger.threshold:.0f}[/yellow bold]"
                )
                self._trigger = saturation_trigger
                break

            # Wait for next batch
            time.sleep(spawn_interval)

            yield {
                "phase": "batch_spawned",
                "batch": batch_count,
                "total_agents": self._total_drivers_queued + self._total_riders_queued,
            }

        # Final status
        total_agents = self._total_drivers_queued + self._total_riders_queued
        elapsed = time.time() - start_time

        if not self._trigger:
            console.print(
                f"\n[yellow]Max duration reached without hitting threshold "
                f"({elapsed:.1f}s, {total_agents} agents)[/yellow]"
            )

        yield {"phase": "stress_complete"}

        # Stop simulation
        console.print("[cyan]Stopping simulation...[/cyan]")
        try:
            self.api_client.stop()
        except Exception as e:
            console.print(f"[yellow]Stop response: {e}[/yellow]")
        yield {"phase": "simulation_stopped"}

        # Store metadata
        self._metadata["trigger"] = (
            {
                "container": self._trigger.container,
                "metric": self._trigger.metric,
                "value": round(self._trigger.value, 2),
                "threshold": self._trigger.threshold,
            }
            if self._trigger
            else None
        )
        self._metadata["total_agents_queued"] = total_agents
        self._metadata["drivers_queued"] = self._total_drivers_queued
        self._metadata["riders_queued"] = self._total_riders_queued
        self._metadata["peak_values"] = self._peak_values
        self._metadata["health_latency_peaks"] = self._health_latency_peaks
        self._metadata["rtr_peak"] = (
            round(min(self._rtr_rolling.values), 4) if self._rtr_rolling.values else None
        )
        self._metadata["duration_seconds"] = elapsed
        self._metadata["batch_count"] = batch_count
        self._metadata["available_cores"] = self._available_cores
        self._metadata["global_cpu_threshold"] = (
            (self.config.scenarios.stress_global_cpu_threshold_percent / 100)
            * self._available_cores
            * 100
        )
        self._metadata["saturation_curve_data"] = True
        # Active trips and throughput peaks from Prometheus data
        active_trips_values = [s["active_trips"] for s in self._samples if "active_trips" in s]
        throughput_values = [
            s["throughput_events_per_sec"]
            for s in self._samples
            if "throughput_events_per_sec" in s
        ]
        self._metadata["active_trips_peak"] = (
            max(active_trips_values) if active_trips_values else None
        )
        self._metadata["throughput_peak_events_per_sec"] = (
            max(throughput_values) if throughput_values else None
        )
        self._metadata["rtr_threshold_used"] = self._effective_rtr_threshold
        self._metadata["rtr_threshold_source"] = self._rtr_threshold_source
        self._metadata["health_threshold_source"] = (
            self._baseline_calibration.health_threshold_source
            if self._baseline_calibration is not None
            else "api-reported"
        )

        console.print(
            f"[green]Stress test complete: {batch_count} batches, "
            f"{total_agents} agents queued, {len(self._samples)} samples[/green]"
        )

    def _collect_sample_with_rolling(self) -> dict[str, Any]:
        """Collect a sample and update rolling averages.

        Returns:
            Sample dict with rolling_averages and agents_queued added.
        """
        # Use base class sample collection
        sample = self._collect_sample()

        # Update rolling stats and peak values for each container
        rolling_averages: dict[str, dict[str, float]] = {}

        for container_name, container_stats in sample.get("containers", {}).items():
            # Initialize rolling stats for new containers
            if container_name not in self._rolling_stats:
                self._rolling_stats[container_name] = ContainerRollingStats.with_window(
                    self._rolling_window_samples
                )

            stats = self._rolling_stats[container_name]

            # Add current values to rolling windows
            memory_pct = container_stats.get("memory_percent", 0.0)
            cpu_pct = container_stats.get("cpu_percent", 0.0)

            stats.memory_percent.add(memory_pct)
            stats.cpu_percent.add(cpu_pct)

            # Calculate rolling averages
            rolling_averages[container_name] = {
                "memory_percent": round(stats.memory_percent.average, 2),
                "cpu_percent": round(stats.cpu_percent.average, 2),
            }

            # Update peak values
            if container_name not in self._peak_values:
                self._peak_values[container_name] = {
                    "memory_percent": 0.0,
                    "cpu_percent": 0.0,
                }

            self._peak_values[container_name]["memory_percent"] = max(
                self._peak_values[container_name]["memory_percent"], memory_pct
            )
            self._peak_values[container_name]["cpu_percent"] = max(
                self._peak_values[container_name]["cpu_percent"], cpu_pct
            )

        # Track global CPU rolling average
        global_cpu = sum(
            container["cpu_percent"] for container in sample.get("containers", {}).values()
        )
        self._global_cpu_rolling.add(global_cpu)
        sample["global_cpu_rolling_avg"] = round(self._global_cpu_rolling.average, 2)

        # Track RTR rolling average
        rtr_data = sample.get("rtr")
        if rtr_data is not None and "rtr" in rtr_data:
            self._rtr_rolling.add(rtr_data["rtr"])
        if self._rtr_rolling.values:
            sample["rtr_rolling_avg"] = round(self._rtr_rolling.average, 4)

        # Update health latency rolling stats
        health_rolling_averages: dict[str, float] = {}
        for svc_name, svc_data in sample.get("health", {}).items():
            latency = svc_data.get("latency_ms")
            if latency is not None and isinstance(latency, (int, float)):
                if svc_name not in self._health_rolling_stats:
                    self._health_rolling_stats[svc_name] = HealthRollingStats.with_window(
                        self._rolling_window_samples
                    )
                self._health_rolling_stats[svc_name].latency_ms.add(latency)
                health_rolling_averages[svc_name] = round(
                    self._health_rolling_stats[svc_name].latency_ms.average, 2
                )
                # Track peak latency
                current_peak = self._health_latency_peaks.get(svc_name, 0.0)
                self._health_latency_peaks[svc_name] = max(current_peak, latency)

        if health_rolling_averages:
            sample["health_rolling_averages"] = health_rolling_averages

        # Augment sample with rolling averages and agent count
        sample["rolling_averages"] = rolling_averages
        sample["agents_queued"] = {
            "drivers": self._total_drivers_queued,
            "riders": self._total_riders_queued,
            "total": self._total_drivers_queued + self._total_riders_queued,
        }

        return sample

    def _capture_failure_snapshot(self, trigger: ThresholdTrigger) -> None:
        """Capture a snapshot of current metrics at the point of threshold failure.

        Reads the last collected sample and writes a snapshot dict into
        ``self._metadata["failure_snapshot"]`` containing Kafka lag, SimPy queue
        size, worst-container resource usage, and trigger details.

        Args:
            trigger: The threshold trigger that caused the stop.
        """
        snapshot: dict[str, Any] = {
            "kafka_consumer_lag": None,
            "simpy_event_queue": None,
            "worst_container_cpu_percent": None,
            "worst_container_memory_percent": None,
            "trigger_container": trigger.container,
            "trigger_metric": trigger.metric,
            "trigger_value": round(trigger.value, 2),
            "trigger_threshold": trigger.threshold,
        }

        if self._samples:
            last_sample = self._samples[-1]
            snapshot["kafka_consumer_lag"] = last_sample.get("kafka_consumer_lag")
            snapshot["simpy_event_queue"] = last_sample.get("simpy_event_queue")

            containers = last_sample.get("containers", {})
            if containers:
                cpu_values = [c.get("cpu_percent", 0.0) for c in containers.values()]
                mem_values = [c.get("memory_percent", 0.0) for c in containers.values()]
                snapshot["worst_container_cpu_percent"] = max(cpu_values)
                snapshot["worst_container_memory_percent"] = max(mem_values)

        self._metadata["failure_snapshot"] = snapshot

    def _check_thresholds(self) -> ThresholdTrigger | None:
        """Check if global CPU or any container's memory exceeds thresholds.

        Global CPU threshold: stops when the sum of all container CPU usage
        reaches threshold_pct% of total available cores (e.g., 90% of 7 cores
        = 630% aggregate CPU).

        Per-container memory threshold: unchanged (90% of container limit).

        Returns:
            ThresholdTrigger if threshold exceeded, None otherwise.
        """
        memory_threshold = self.config.scenarios.stress_memory_threshold_percent

        # Check per-container memory thresholds
        for container_name, stats in self._rolling_stats.items():
            memory_avg = stats.memory_percent.average
            if memory_avg >= memory_threshold:
                trigger = ThresholdTrigger(
                    container=container_name,
                    metric="memory",
                    value=memory_avg,
                    threshold=memory_threshold,
                )
                self._capture_failure_snapshot(trigger)
                return trigger

        # Check global CPU threshold
        global_threshold_pct = self.config.scenarios.stress_global_cpu_threshold_percent
        global_cpu_limit = (global_threshold_pct / 100) * self._available_cores * 100
        global_cpu_avg = self._global_cpu_rolling.average
        if global_cpu_avg >= global_cpu_limit:
            trigger = ThresholdTrigger(
                container="__global__",
                metric="global_cpu",
                value=global_cpu_avg,
                threshold=global_cpu_limit,
            )
            self._capture_failure_snapshot(trigger)
            return trigger

        # Check RTR (simulation lag) threshold
        if self._rtr_rolling.values:
            rtr_avg = self._rtr_rolling.average
            if rtr_avg <= self._effective_rtr_threshold:
                trigger = ThresholdTrigger(
                    container="__simulation__",
                    metric="rtr",
                    value=rtr_avg,
                    threshold=self._effective_rtr_threshold,
                )
                self._capture_failure_snapshot(trigger)
                return trigger

        # Check health latency thresholds for critical services (Priority 4)
        if self.config.scenarios.health_check_enabled and self._samples:
            last_sample = self._samples[-1]
            health_data = last_sample.get("health", {})
            for svc_name in self.config.scenarios.health_critical_services:
                if svc_name not in self._health_rolling_stats:
                    continue
                rolling_avg = self._health_rolling_stats[svc_name].latency_ms.average
                # Prefer baseline-derived threshold, fall back to API-reported value
                threshold_unhealthy: float | None = None
                if self._baseline_calibration is not None:
                    threshold_unhealthy = self._baseline_calibration.health_thresholds.get(
                        svc_name, {}
                    ).get("unhealthy")
                if threshold_unhealthy is None:
                    svc_health = health_data.get(svc_name, {})
                    threshold_unhealthy = svc_health.get("threshold_unhealthy")
                if threshold_unhealthy is not None and rolling_avg >= threshold_unhealthy:
                    trigger = ThresholdTrigger(
                        container=svc_name,
                        metric="health_latency",
                        value=rolling_avg,
                        threshold=threshold_unhealthy,
                    )
                    self._capture_failure_snapshot(trigger)
                    return trigger

        return None

    def _check_saturation_stop(self) -> ThresholdTrigger | None:
        """Check if active trips have exceeded the USL knee point.

        NOTE: USL-based saturation stopping is currently disabled.
        This method always returns None.

        Returns:
            None (saturation stop disabled).
        """
        return None
