"""Stress test scenario: spawn agents until resource threshold reached."""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterator

from rich.console import Console

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
class ThresholdTrigger:
    """Records which container/metric triggered the threshold stop."""

    container: str
    metric: str  # "memory" or "cpu"
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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
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
            f"or {self.params['rtr_threshold']}x RTR reached"
        )

    @property
    def params(self) -> dict[str, Any]:
        return {
            "global_cpu_threshold_percent": self.config.scenarios.stress_global_cpu_threshold_percent,
            "memory_threshold_percent": self.config.scenarios.stress_memory_threshold_percent,
            "rtr_threshold": self.config.scenarios.stress_rtr_threshold,
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
        self._metadata["rtr_peak"] = (
            round(max(self._rtr_rolling.values), 4) if self._rtr_rolling.values else None
        )
        self._metadata["duration_seconds"] = elapsed
        self._metadata["batch_count"] = batch_count
        self._metadata["available_cores"] = self._available_cores
        self._metadata["global_cpu_threshold"] = (
            (self.config.scenarios.stress_global_cpu_threshold_percent / 100)
            * self._available_cores
            * 100
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
                self._peak_values[container_name] = {"memory_percent": 0.0, "cpu_percent": 0.0}

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

        # Augment sample with rolling averages and agent count
        sample["rolling_averages"] = rolling_averages
        sample["agents_queued"] = {
            "drivers": self._total_drivers_queued,
            "riders": self._total_riders_queued,
            "total": self._total_drivers_queued + self._total_riders_queued,
        }

        return sample

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
                return ThresholdTrigger(
                    container=container_name,
                    metric="memory",
                    value=memory_avg,
                    threshold=memory_threshold,
                )

        # Check global CPU threshold
        global_threshold_pct = self.config.scenarios.stress_global_cpu_threshold_percent
        global_cpu_limit = (global_threshold_pct / 100) * self._available_cores * 100
        global_cpu_avg = self._global_cpu_rolling.average
        if global_cpu_avg >= global_cpu_limit:
            return ThresholdTrigger(
                container="__global__",
                metric="global_cpu",
                value=global_cpu_avg,
                threshold=global_cpu_limit,
            )

        # Check RTR (simulation lag) threshold
        rtr_threshold = self.config.scenarios.stress_rtr_threshold
        if self._rtr_rolling.values:
            rtr_avg = self._rtr_rolling.average
            if rtr_avg >= rtr_threshold:
                return ThresholdTrigger(
                    container="__simulation__",
                    metric="rtr",
                    value=rtr_avg,
                    threshold=rtr_threshold,
                )

        return None
