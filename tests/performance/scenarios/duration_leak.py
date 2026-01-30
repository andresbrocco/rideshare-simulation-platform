"""Duration/leak detection scenario: measure memory over extended time."""

from typing import Any, Iterator

from rich.console import Console

from .base import BaseScenario

console = Console()


class DurationLeakScenario(BaseScenario):
    """Duration test for memory leak detection.

    Runs with a fixed number of agents for an extended period (default 8 minutes)
    with checkpoints at 1, 2, 4, 8 minutes to detect memory leaks.
    Slope > 1 MB/min flagged as potential leak.

    Protocol:
    1. Step 0: Clean environment (down -v, up -d, wait healthy)
    2. Start simulation
    3. Queue 40 drivers (mode=immediate)
    4. Queue 40 riders (mode=immediate)
    5. Wait for steady state
    6. Sample every 2s for full duration
    7. Record checkpoint snapshots at 1, 2, 4, 8 minutes
    8. Calculate memory trend (slope) overall and per-checkpoint
    9. Flag leak if any checkpoint slope > 1 MB/min
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.duration_minutes = self.config.scenarios.duration_total_minutes
        self.checkpoints = self.config.scenarios.duration_checkpoints
        self.agent_count = self.config.scenarios.duration_agent_count
        self._checkpoint_data: dict[int, dict[str, Any]] = {}

    @property
    def name(self) -> str:
        return "duration_leak"

    @property
    def description(self) -> str:
        return (
            f"Memory leak detection with {self.agent_count} agents "
            f"for {self.duration_minutes} minutes (checkpoints: {self.checkpoints})"
        )

    @property
    def params(self) -> dict[str, Any]:
        return {
            "duration_minutes": self.duration_minutes,
            "duration_seconds": self.duration_minutes * 60,
            "checkpoints": self.checkpoints,
            "drivers": self.agent_count,
            "riders": self.agent_count,
        }

    def execute(self) -> Iterator[dict[str, Any]]:
        """Execute duration/leak test."""
        # Start simulation
        console.print("[cyan]Starting simulation...[/cyan]")
        try:
            self.api_client.start()
        except Exception as e:
            console.print(f"[yellow]Start response: {e}[/yellow]")
        yield {"phase": "simulation_started"}

        # Queue drivers
        console.print(f"[cyan]Queuing {self.agent_count} drivers (mode=immediate)...[/cyan]")
        self.api_client.queue_drivers(self.agent_count)
        yield {"phase": "drivers_queued"}

        # Queue riders
        console.print(f"[cyan]Queuing {self.agent_count} riders (mode=immediate)...[/cyan]")
        self.api_client.queue_riders(self.agent_count)
        yield {"phase": "riders_queued"}

        # Wait for spawn queues to empty
        console.print("[cyan]Waiting for spawn queues to empty...[/cyan]")
        if not self.api_client.wait_for_spawn_complete(timeout=120.0):
            console.print("[yellow]Warning: Spawn did not complete within timeout[/yellow]")
        yield {"phase": "spawn_complete"}

        # Get status to verify
        status = self.api_client.get_simulation_status()
        console.print(
            f"[green]Agents active: {status.drivers_total} drivers, "
            f"{status.riders_total} riders[/green]"
        )

        # Settle time
        console.print(f"[cyan]Settle time: {self.config.sampling.settle_seconds}s[/cyan]")
        self._wait_for_steady_state(self.config.sampling.settle_seconds)
        yield {"phase": "settle_complete"}

        # Collect samples for extended duration
        duration_seconds = self.duration_minutes * 60
        console.print(
            f"[cyan]Collecting samples for {self.duration_minutes} minutes "
            f"({duration_seconds}s) with checkpoints at {self.checkpoints} min...[/cyan]"
        )
        samples = self._collect_samples(duration_seconds)
        yield {"phase": "sampling_complete", "sample_count": len(samples)}

        # Process checkpoints from collected samples
        self._process_checkpoints()

        # Calculate memory trend for key containers
        self._analyze_memory_trend()

        # Stop simulation
        console.print("[cyan]Stopping simulation...[/cyan]")
        try:
            self.api_client.stop()
        except Exception as e:
            console.print(f"[yellow]Stop response: {e}[/yellow]")
        yield {"phase": "simulation_stopped"}

        console.print(
            f"[green]Duration test ({self.duration_minutes}m) complete: "
            f"{len(samples)} samples collected, {len(self._checkpoint_data)} checkpoints[/green]"
        )

    def _process_checkpoints(self) -> None:
        """Process samples to extract checkpoint data."""
        if len(self._samples) < 2:
            console.print("[yellow]Insufficient samples for checkpoint processing[/yellow]")
            return

        # Get first timestamp as reference
        first_ts = self._samples[0]["timestamp"]
        container = "rideshare-simulation"

        for checkpoint_min in self.checkpoints:
            checkpoint_seconds = checkpoint_min * 60

            # Find samples belonging to this checkpoint
            # Checkpoint N covers samples from previous checkpoint to N minutes
            prev_checkpoint = 0
            for i, cp in enumerate(self.checkpoints):
                if cp == checkpoint_min and i > 0:
                    prev_checkpoint = self.checkpoints[i - 1]
                    break

            prev_seconds = prev_checkpoint * 60
            start_idx = None
            end_idx = None

            for i, sample in enumerate(self._samples):
                elapsed = sample["timestamp"] - first_ts
                if elapsed >= prev_seconds and start_idx is None:
                    start_idx = i
                if elapsed <= checkpoint_seconds:
                    end_idx = i

            if start_idx is None or end_idx is None or start_idx > end_idx:
                continue

            # Extract memory values for this checkpoint range
            checkpoint_samples = self._samples[start_idx : end_idx + 1]
            memory_values: list[tuple[float, float]] = []

            for sample in checkpoint_samples:
                containers = sample.get("containers", {})
                if container in containers:
                    ts = sample["timestamp"]
                    mem = containers[container]["memory_used_mb"]
                    memory_values.append((ts, mem))

            if len(memory_values) < 2:
                continue

            # Calculate slope for this checkpoint segment
            seg_first_ts, seg_first_mem = memory_values[0]
            seg_last_ts, seg_last_mem = memory_values[-1]
            seg_duration_min = (seg_last_ts - seg_first_ts) / 60

            slope_mb_per_min = 0.0
            if seg_duration_min > 0:
                slope_mb_per_min = (seg_last_mem - seg_first_mem) / seg_duration_min

            # Calculate average memory for this segment
            avg_memory = sum(m for _, m in memory_values) / len(memory_values)

            self._checkpoint_data[checkpoint_min] = {
                "sample_indices": [start_idx, end_idx],
                "sample_count": len(checkpoint_samples),
                "memory_mb": round(seg_last_mem, 2),
                "memory_avg_mb": round(avg_memory, 2),
                "slope_mb_per_min": round(slope_mb_per_min, 3),
            }

            console.print(
                f"[dim]Checkpoint {checkpoint_min}m: "
                f"{seg_last_mem:.1f} MB, slope={slope_mb_per_min:.3f} MB/min[/dim]"
            )

    def _analyze_memory_trend(self) -> None:
        """Analyze memory trend to detect potential leaks."""
        if len(self._samples) < 2:
            console.print("[yellow]Insufficient samples for trend analysis[/yellow]")
            return

        # Focus on simulation container
        container = "rideshare-simulation"
        memory_values: list[tuple[float, float]] = []

        for sample in self._samples:
            containers = sample.get("containers", {})
            if container in containers:
                ts = sample["timestamp"]
                mem = containers[container]["memory_used_mb"]
                memory_values.append((ts, mem))

        if len(memory_values) < 2:
            console.print(f"[yellow]Insufficient data for {container}[/yellow]")
            return

        # Calculate overall slope (MB per minute)
        first_ts, first_mem = memory_values[0]
        last_ts, last_mem = memory_values[-1]
        duration_minutes = (last_ts - first_ts) / 60

        overall_slope = 0.0
        if duration_minutes > 0:
            overall_slope = (last_mem - first_mem) / duration_minutes

        # Check checkpoint-to-checkpoint slopes for leaks
        leak_detected = False
        for checkpoint_min, data in sorted(self._checkpoint_data.items()):
            if data["slope_mb_per_min"] > 1.0:
                leak_detected = True
                console.print(
                    f"[red bold]POTENTIAL LEAK at checkpoint {checkpoint_min}m: "
                    f"{data['slope_mb_per_min']:.2f} MB/min[/red bold]"
                )

        # Report overall trend
        if overall_slope > 1.0:
            console.print(
                f"[red bold]POTENTIAL LEAK: {container} overall trend "
                f"{overall_slope:.2f} MB/min[/red bold]"
            )
        elif leak_detected:
            console.print(
                f"[yellow]{container} overall trend: {overall_slope:.2f} MB/min "
                f"(leak detected in checkpoint segments)[/yellow]"
            )
        else:
            console.print(f"[green]{container} memory stable: {overall_slope:.2f} MB/min[/green]")

        # Store checkpoint data in metadata for results
        self._metadata["checkpoints"] = self._checkpoint_data
        self._metadata["overall_slope_mb_per_min"] = round(overall_slope, 3)
        self._metadata["leak_detected"] = leak_detected or overall_slope > 1.0
