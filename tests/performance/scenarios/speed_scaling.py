"""Speed scaling scenario: increase speed multiplier until threshold reached."""

import time
from typing import Any, Iterator

from rich.console import Console

from ..analysis.statistics import BaselineCalibration
from .base import BaseScenario
from .stress_test import (
    PeakTracker,
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
        # RTR collapse threshold — the only RTR-based stop condition
        self._rtr_collapse_threshold = self.config.scenarios.stress_rtr_collapse_threshold
        # Keep baseline RTR info for observability metadata
        if baseline_calibration is not None and baseline_calibration.rtr_threshold is not None:
            self._baseline_rtr_threshold = baseline_calibration.rtr_threshold
            self._baseline_rtr_source = baseline_calibration.rtr_threshold_source
        else:
            self._baseline_rtr_threshold = self.config.scenarios.stress_rtr_threshold
            self._baseline_rtr_source = "config-fallback"
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
        self._metadata["rtr_collapse_threshold"] = self._rtr_collapse_threshold
        self._metadata["baseline_rtr_threshold"] = self._baseline_rtr_threshold
        self._metadata["baseline_rtr_source"] = self._baseline_rtr_source

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
                f"[red bold]THRESHOLD REACHED: "
                f"{trigger.metric} = {trigger.value:.4f} "
                f"(<= {trigger.threshold})[/red bold]"
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
        """Build a snapshot dict using peak values from step samples.

        Uses PeakTracker to compute peaks across all step samples (not just
        the last sample) so that divisors reflect true saturation points.

        Args:
            trigger: The threshold trigger that caused the step to stop.
            step_samples: Samples collected during this step.

        Returns:
            Dict containing peak Kafka lag, SimPy queue size, global CPU sum,
            worst-container memory usage, and trigger details.
        """
        peak_tracker = PeakTracker()
        for sample in step_samples:
            peak_tracker.update_from_sample(sample)

        snapshot = peak_tracker.to_snapshot()
        snapshot["trigger_container"] = trigger.container
        snapshot["trigger_metric"] = trigger.metric
        snapshot["trigger_value"] = round(trigger.value, 2)
        snapshot["trigger_threshold"] = trigger.threshold
        return snapshot

    def _check_step_thresholds(self, step_samples: list[dict[str, Any]]) -> ThresholdTrigger | None:
        """Check if RTR collapsed during this step.

        OOM and container death are handled by the base class.

        Args:
            step_samples: Samples collected during this step.

        Returns:
            ThresholdTrigger if RTR collapsed, None otherwise.
        """
        if not step_samples:
            return None

        rolling_window_samples = int(
            self.config.scenarios.stress_rolling_window_seconds
            / self.config.sampling.interval_seconds
        )

        rtr_rolling = RollingStats.with_window(rolling_window_samples)
        for sample in step_samples:
            rtr_data = sample.get("rtr")
            if rtr_data is not None and "rtr" in rtr_data:
                rtr_rolling.add(rtr_data["rtr"])

        if rtr_rolling.values:
            rtr_avg = rtr_rolling.average
            if rtr_avg <= self._rtr_collapse_threshold:
                return ThresholdTrigger(
                    container="__simulation__",
                    metric="rtr_collapse",
                    value=rtr_avg,
                    threshold=self._rtr_collapse_threshold,
                )

        return None
