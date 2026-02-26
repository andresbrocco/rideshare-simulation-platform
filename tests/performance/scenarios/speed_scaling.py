"""Speed scaling scenario: increase speed multiplier until threshold reached."""

import time
from typing import Any, Iterator

from rich.console import Console

from ..analysis.statistics import BaselineCalibration
from .base import BaseScenario
from .stress_test import (
    ContainerRollingStats,
    HealthRollingStats,
    RollingStats,
    ThresholdTrigger,
)

console = Console()


class SpeedScalingScenario(BaseScenario):
    """Speed scaling test: double speed multiplier each step until threshold hit.

    Each step resets the simulation, sets a new speed multiplier, spawns
    a fixed number of agents, and collects metrics. The agent count stays
    constant across all steps to isolate the effect of speed on system load.

    Protocol:
    1. Step 0: Clean environment (down -v, up -d, wait healthy)
    2. For each speed step (2, 4, 8, ..., max_multiplier):
       a. Reset simulation
       b. Set speed multiplier
       c. Start simulation
       d. Queue agents (fixed count across all steps)
       e. Wait spawn, settle
       f. Collect samples for step duration
       g. Check thresholds
       h. Stop simulation
       i. Break if threshold hit
    3. Store step results in metadata
    """

    def __init__(
        self,
        agent_count: int,
        *args: Any,
        baseline_calibration: BaselineCalibration | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize speed scaling scenario.

        Args:
            agent_count: Total agent count (split equally between drivers and riders).
            *args: Positional arguments passed to BaseScenario.
            baseline_calibration: Dynamic thresholds from baseline (None = use config).
            **kwargs: Keyword arguments passed to BaseScenario.
        """
        super().__init__(*args, **kwargs)
        self._baseline_calibration = baseline_calibration
        # Compute effective RTR threshold: prefer baseline-derived, else config fallback
        if baseline_calibration is not None and baseline_calibration.rtr_threshold is not None:
            self._effective_rtr_threshold = baseline_calibration.rtr_threshold
            self._rtr_threshold_source = baseline_calibration.rtr_threshold_source
        else:
            self._effective_rtr_threshold = self.config.scenarios.stress_rtr_threshold
            self._rtr_threshold_source = "config-fallback"
        self.base_agent_count = agent_count
        self.step_duration_minutes = self.config.scenarios.speed_scaling_step_duration_minutes
        self.max_multiplier = self.config.scenarios.speed_scaling_max_multiplier
        self._step_results: list[dict[str, Any]] = []
        self._stopped_by_threshold = False

    @property
    def name(self) -> str:
        return "speed_scaling"

    @property
    def requires_clean_restart(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return (
            f"Speed scaling: double multiplier from 2x to {self.max_multiplier}x, "
            f"{self.step_duration_minutes}m per step, "
            f"{self.base_agent_count} agents (fixed)"
        )

    @property
    def params(self) -> dict[str, Any]:
        return {
            "agent_count": self.base_agent_count,
            "step_duration_minutes": self.step_duration_minutes,
            "max_multiplier": self.max_multiplier,
        }

    def execute(self) -> Iterator[dict[str, Any]]:
        """Execute speed scaling test."""
        multiplier = 2
        step_number = 0

        while multiplier <= self.max_multiplier:
            if self._aborted:
                console.print(f"[red]Test aborted: {self._abort_reason}[/red]")
                break

            step_number += 1
            agent_count = self.base_agent_count

            console.print(
                f"\n[bold cyan]Speed Step {step_number}: "
                f"{multiplier}x speed, {agent_count} agents[/bold cyan]"
            )

            step_result = self._run_step(step_number, multiplier, agent_count)
            self._step_results.append(step_result)

            yield {
                "phase": "step_complete",
                "step": step_number,
                "multiplier": multiplier,
                "threshold_hit": step_result["threshold_hit"],
            }

            if step_result["threshold_hit"] or self._aborted:
                self._stopped_by_threshold = step_result["threshold_hit"]
                break

            multiplier *= 2

        # Store metadata
        max_speed = self._step_results[-1]["multiplier"] if self._step_results else 1
        self._metadata["saturation_curve_data"] = True
        self._metadata["step_results"] = self._step_results
        self._metadata["total_steps"] = len(self._step_results)
        self._metadata["max_speed_achieved"] = max_speed
        self._metadata["stopped_by_threshold"] = self._stopped_by_threshold
        self._metadata["rtr_threshold_used"] = self._effective_rtr_threshold
        self._metadata["rtr_threshold_source"] = self._rtr_threshold_source
        self._metadata["health_threshold_source"] = (
            self._baseline_calibration.health_threshold_source
            if self._baseline_calibration is not None
            else "api-reported"
        )

        console.print(
            f"\n[green]Speed scaling complete: {len(self._step_results)} steps, "
            f"max speed {max_speed}x"
            f"{' (threshold hit)' if self._stopped_by_threshold else ''}[/green]"
        )

    def _run_step(self, step_number: int, multiplier: int, agent_count: int) -> dict[str, Any]:
        """Run a single speed step.

        Args:
            step_number: Step index (1-based).
            multiplier: Speed multiplier for this step.
            agent_count: Number of drivers/riders to spawn.

        Returns:
            Dict with step results including speed, agent_count, threshold info.
        """
        step_start = time.time()
        trigger: ThresholdTrigger | None = None

        # Reset simulation for clean state
        console.print("[cyan]Resetting simulation...[/cyan]")
        try:
            self.api_client.reset()
        except Exception as e:
            console.print(f"[yellow]Reset response: {e}[/yellow]")

        # Set speed multiplier
        console.print(f"[cyan]Setting speed to {multiplier}x...[/cyan]")
        try:
            self.api_client.set_speed(multiplier)
        except Exception as e:
            console.print(f"[yellow]Set speed response: {e}[/yellow]")

        # Start simulation
        console.print("[cyan]Starting simulation...[/cyan]")
        try:
            self.api_client.start()
        except Exception as e:
            console.print(f"[yellow]Start response: {e}[/yellow]")

        # Queue agents (agent_count is total; split equally between drivers and riders)
        per_type = agent_count // 2
        console.print(
            f"[cyan]Queuing {per_type} drivers + {per_type} riders "
            f"({agent_count} total)...[/cyan]"
        )
        remaining = per_type
        while remaining > 0:
            batch = min(remaining, 100)
            try:
                self.api_client.queue_drivers(batch)
            except Exception as e:
                console.print(f"[yellow]Driver queue failed: {e}[/yellow]")
            remaining -= batch

        remaining = per_type
        while remaining > 0:
            batch = min(remaining, 2000)
            try:
                self.api_client.queue_riders(batch)
            except Exception as e:
                console.print(f"[yellow]Rider queue failed: {e}[/yellow]")
            remaining -= batch

        # Wait for spawn
        console.print("[cyan]Waiting for spawn...[/cyan]")
        self.api_client.wait_for_spawn_complete(timeout=120.0)

        # Settle
        self._wait_for_steady_state(self.config.sampling.settle_seconds)

        # Collect samples for step duration
        step_duration_seconds = self.step_duration_minutes * 60
        console.print(f"[cyan]Collecting samples for {self.step_duration_minutes}m...[/cyan]")
        step_samples = self._collect_samples(step_duration_seconds)

        # Check thresholds using rolling window
        trigger = self._check_step_thresholds(step_samples)

        if trigger:
            console.print(
                f"[red bold]THRESHOLD REACHED: {trigger.container} "
                f"{trigger.metric}={trigger.value:.1f}% >= {trigger.threshold}%[/red bold]"
            )

        # Stop simulation
        console.print("[cyan]Stopping simulation...[/cyan]")
        try:
            self.api_client.stop()
        except Exception as e:
            console.print(f"[yellow]Stop response: {e}[/yellow]")

        step_duration = time.time() - step_start

        # Compute RTR stats from step samples
        rtr_values = [
            s["rtr"]["rtr"] for s in step_samples if s.get("rtr") is not None and "rtr" in s["rtr"]
        ]
        rtr_peak = min(rtr_values) if rtr_values else None
        rtr_mean = (sum(rtr_values) / len(rtr_values)) if rtr_values else None

        # Compute active_trips stats for saturation analysis
        active_trips_values = [
            s["rtr"]["active_trips"]
            for s in step_samples
            if s.get("rtr") is not None and "active_trips" in s.get("rtr", {})
        ]
        active_trips_mean = (
            round(sum(active_trips_values) / len(active_trips_values), 2)
            if active_trips_values
            else None
        )
        active_trips_max = max(active_trips_values) if active_trips_values else None

        # Compute throughput stats from Prometheus data for saturation analysis
        throughput_values = [
            s["throughput_events_per_sec"] for s in step_samples if "throughput_events_per_sec" in s
        ]
        throughput_mean = (
            round(sum(throughput_values) / len(throughput_values), 2) if throughput_values else None
        )
        throughput_max = round(max(throughput_values), 2) if throughput_values else None

        return {
            "step": step_number,
            "multiplier": multiplier,
            "agent_count": agent_count,
            "sample_count": len(step_samples),
            "duration_seconds": round(step_duration, 2),
            "threshold_hit": trigger is not None,
            "trigger": (
                {
                    "container": trigger.container,
                    "metric": trigger.metric,
                    "value": round(trigger.value, 2),
                    "threshold": round(trigger.threshold, 2),
                }
                if trigger
                else None
            ),
            "failure_snapshot": (
                self._capture_step_failure_snapshot(trigger, step_samples)
                if trigger is not None
                else None
            ),
            "rtr_peak": round(rtr_peak, 4) if rtr_peak is not None else None,
            "rtr_mean": round(rtr_mean, 4) if rtr_mean is not None else None,
            "active_trips_mean": active_trips_mean,
            "active_trips_max": active_trips_max,
            "throughput_mean_events_per_sec": throughput_mean,
            "throughput_max_events_per_sec": throughput_max,
        }

    def _capture_step_failure_snapshot(
        self, trigger: ThresholdTrigger, step_samples: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Build a snapshot dict of current metrics at the point of step threshold failure.

        Args:
            trigger: The threshold trigger that caused the step to stop.
            step_samples: Samples collected during this step.

        Returns:
            Dict containing Kafka lag, SimPy queue size, worst-container resource
            usage, and trigger details.
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

        if step_samples:
            last_sample = step_samples[-1]
            snapshot["kafka_consumer_lag"] = last_sample.get("kafka_consumer_lag")
            snapshot["simpy_event_queue"] = last_sample.get("simpy_event_queue")

            containers = last_sample.get("containers", {})
            if containers:
                cpu_values = [c.get("cpu_percent", 0.0) for c in containers.values()]
                mem_values = [c.get("memory_percent", 0.0) for c in containers.values()]
                snapshot["worst_container_cpu_percent"] = max(cpu_values)
                snapshot["worst_container_memory_percent"] = max(mem_values)

        return snapshot

    def _check_step_thresholds(self, step_samples: list[dict[str, Any]]) -> ThresholdTrigger | None:
        """Check if global CPU or any container's memory exceeded thresholds.

        Uses rolling stats from step samples. Global CPU threshold stops when
        the sum of all container CPU reaches threshold_pct% of available cores.
        Per-container memory threshold remains unchanged.

        Args:
            step_samples: Samples collected during this step.

        Returns:
            ThresholdTrigger if threshold exceeded, None otherwise.
        """
        if not step_samples:
            return None

        memory_threshold = self.config.scenarios.stress_memory_threshold_percent

        rolling_window_samples = int(
            self.config.scenarios.stress_rolling_window_seconds
            / self.config.sampling.interval_seconds
        )

        # Build rolling stats from step samples (memory per-container + global CPU)
        container_stats: dict[str, ContainerRollingStats] = {}
        global_cpu_rolling = RollingStats.with_window(rolling_window_samples)

        for sample in step_samples:
            # Per-container memory rolling stats
            for container_name, container_data in sample.get("containers", {}).items():
                if container_name not in container_stats:
                    container_stats[container_name] = ContainerRollingStats(
                        memory_percent=RollingStats.with_window(rolling_window_samples),
                        cpu_percent=RollingStats.with_window(rolling_window_samples),
                    )

                stats = container_stats[container_name]
                stats.memory_percent.add(container_data.get("memory_percent", 0.0))
                stats.cpu_percent.add(container_data.get("cpu_percent", 0.0))

            # Global CPU rolling stats
            global_cpu = sample.get("global_cpu_percent", 0.0)
            global_cpu_rolling.add(global_cpu)

        # Check per-container memory thresholds
        for container_name, stats in container_stats.items():
            memory_avg = stats.memory_percent.average
            if memory_avg >= memory_threshold:
                return ThresholdTrigger(
                    container=container_name,
                    metric="memory",
                    value=memory_avg,
                    threshold=memory_threshold,
                )

        # Check global CPU threshold
        global_threshold_pct = self.config.scenarios.stress_global_cpu_threshold_percent
        global_cpu_limit = (global_threshold_pct / 100) * self._available_cores * 100
        global_cpu_avg = global_cpu_rolling.average
        if global_cpu_avg >= global_cpu_limit:
            return ThresholdTrigger(
                container="__global__",
                metric="global_cpu",
                value=global_cpu_avg,
                threshold=global_cpu_limit,
            )

        # Check RTR (simulation lag) threshold
        rtr_rolling = RollingStats.with_window(rolling_window_samples)
        for sample in step_samples:
            rtr_data = sample.get("rtr")
            if rtr_data is not None and "rtr" in rtr_data:
                rtr_rolling.add(rtr_data["rtr"])

        if rtr_rolling.values:
            rtr_avg = rtr_rolling.average
            if rtr_avg <= self._effective_rtr_threshold:
                return ThresholdTrigger(
                    container="__simulation__",
                    metric="rtr",
                    value=rtr_avg,
                    threshold=self._effective_rtr_threshold,
                )

        # Check health latency thresholds for critical services
        if self.config.scenarios.health_check_enabled:
            health_stats: dict[str, HealthRollingStats] = {}
            for sample in step_samples:
                for svc_name, svc_data in sample.get("health", {}).items():
                    latency = svc_data.get("latency_ms")
                    if latency is not None and isinstance(latency, (int, float)):
                        if svc_name not in health_stats:
                            health_stats[svc_name] = HealthRollingStats.with_window(
                                rolling_window_samples
                            )
                        health_stats[svc_name].latency_ms.add(latency)

            # Get threshold values from the last sample that has health data
            last_health: dict[str, dict[str, Any]] = {}
            for sample in reversed(step_samples):
                if "health" in sample:
                    last_health = sample["health"]
                    break

            for svc_name in self.config.scenarios.health_critical_services:
                if svc_name not in health_stats:
                    continue
                rolling_avg = health_stats[svc_name].latency_ms.average
                # Prefer baseline-derived threshold, fall back to API-reported value
                threshold_unhealthy: float | None = None
                if self._baseline_calibration is not None:
                    threshold_unhealthy = self._baseline_calibration.health_thresholds.get(
                        svc_name, {}
                    ).get("unhealthy")
                if threshold_unhealthy is None:
                    svc_health = last_health.get(svc_name, {})
                    threshold_unhealthy = svc_health.get("threshold_unhealthy")
                if threshold_unhealthy is not None and rolling_avg >= threshold_unhealthy:
                    return ThresholdTrigger(
                        container=svc_name,
                        metric="health_latency",
                        value=rolling_avg,
                        threshold=threshold_unhealthy,
                    )

        return None
