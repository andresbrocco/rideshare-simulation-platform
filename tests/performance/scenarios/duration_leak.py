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

    def __init__(self, agent_count: int, *args: Any, **kwargs: Any) -> None:
        """Initialize duration/leak scenario.

        Args:
            agent_count: Number of drivers/riders to spawn (derived from stress test).
            *args: Positional arguments passed to BaseScenario.
            **kwargs: Keyword arguments passed to BaseScenario.

        Raises:
            ValueError: If agent_count is less than 2.
        """
        super().__init__(*args, **kwargs)
        if agent_count < 2:
            raise ValueError(
                f"agent_count must be at least 2, got {agent_count} "
                "(derived from stress test drivers_queued // 2)"
            )
        self.duration_minutes = self.config.scenarios.duration_total_minutes
        self.checkpoints = self.config.scenarios.duration_checkpoints
        self.agent_count = agent_count
        # Per-checkpoint data: {checkpoint_min: {container: {memory_slope, cpu_slope, ...}}}
        self._checkpoint_data: dict[int, dict[str, dict[str, Any]]] = {}

    @property
    def name(self) -> str:
        return "duration_leak"

    @property
    def description(self) -> str:
        return (
            f"Memory leak detection with {self.agent_count} agents (derived from stress test) "
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
            "agent_count_source": "stress_test_drivers_queued_half",
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

        # Analyze trends for all containers (memory and CPU)
        self._analyze_trends()

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
        """Process samples to extract checkpoint data for all containers."""
        if len(self._samples) < 2:
            console.print("[yellow]Insufficient samples for checkpoint processing[/yellow]")
            return

        # Get first timestamp as reference
        first_ts = self._samples[0]["timestamp"]

        # Find all containers
        all_containers: set[str] = set()
        for sample in self._samples:
            all_containers.update(sample.get("containers", {}).keys())

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

            checkpoint_samples = self._samples[start_idx : end_idx + 1]
            self._checkpoint_data[checkpoint_min] = {}

            # Process each container
            for container in all_containers:
                memory_values: list[tuple[float, float]] = []
                cpu_values: list[tuple[float, float]] = []

                for sample in checkpoint_samples:
                    containers = sample.get("containers", {})
                    if container in containers:
                        ts = sample["timestamp"]
                        mem = containers[container]["memory_used_mb"]
                        cpu = containers[container]["cpu_percent"]
                        memory_values.append((ts, mem))
                        cpu_values.append((ts, cpu))

                if len(memory_values) < 2:
                    continue

                # Calculate slopes for this checkpoint segment
                seg_first_ts = memory_values[0][0]
                seg_last_ts = memory_values[-1][0]
                seg_duration_min = (seg_last_ts - seg_first_ts) / 60

                # Memory slope
                seg_first_mem = memory_values[0][1]
                seg_last_mem = memory_values[-1][1]
                memory_slope = 0.0
                if seg_duration_min > 0:
                    memory_slope = (seg_last_mem - seg_first_mem) / seg_duration_min

                # CPU slope
                seg_first_cpu = cpu_values[0][1]
                seg_last_cpu = cpu_values[-1][1]
                cpu_slope = 0.0
                if seg_duration_min > 0:
                    cpu_slope = (seg_last_cpu - seg_first_cpu) / seg_duration_min

                # Calculate averages
                avg_memory = sum(m for _, m in memory_values) / len(memory_values)
                avg_cpu = sum(c for _, c in cpu_values) / len(cpu_values)

                self._checkpoint_data[checkpoint_min][container] = {
                    "sample_indices": [start_idx, end_idx],
                    "sample_count": len(checkpoint_samples),
                    "memory_mb": round(seg_last_mem, 2),
                    "memory_avg_mb": round(avg_memory, 2),
                    "memory_slope_mb_per_min": round(memory_slope, 3),
                    "cpu_percent": round(seg_last_cpu, 2),
                    "cpu_avg_percent": round(avg_cpu, 2),
                    "cpu_slope_percent_per_min": round(cpu_slope, 3),
                }

            # Log simulation container for backward compat
            sim_data = self._checkpoint_data[checkpoint_min].get("rideshare-simulation", {})
            if sim_data:
                console.print(
                    f"[dim]Checkpoint {checkpoint_min}m (simulation): "
                    f"{sim_data.get('memory_mb', 0):.1f} MB, "
                    f"slope={sim_data.get('memory_slope_mb_per_min', 0):.3f} MB/min[/dim]"
                )

    def _analyze_trends(self) -> None:
        """Analyze memory and CPU trends to detect potential leaks for all containers."""
        if len(self._samples) < 2:
            console.print("[yellow]Insufficient samples for trend analysis[/yellow]")
            return

        # Get thresholds from config
        memory_threshold = self.config.analysis.leak_threshold_mb_per_min
        cpu_threshold = self.config.analysis.cpu_leak_threshold_per_min

        # Find all containers
        all_containers: set[str] = set()
        for sample in self._samples:
            all_containers.update(sample.get("containers", {}).keys())

        leak_analysis: dict[str, dict[str, Any]] = {}

        for container in all_containers:
            memory_values: list[tuple[float, float]] = []
            cpu_values: list[tuple[float, float]] = []

            for sample in self._samples:
                containers = sample.get("containers", {})
                if container in containers:
                    ts = sample["timestamp"]
                    mem = containers[container]["memory_used_mb"]
                    cpu = containers[container]["cpu_percent"]
                    memory_values.append((ts, mem))
                    cpu_values.append((ts, cpu))

            if len(memory_values) < 2:
                continue

            # Calculate overall slopes
            first_ts = memory_values[0][0]
            last_ts = memory_values[-1][0]
            duration_minutes = (last_ts - first_ts) / 60

            # Memory slope
            first_mem = memory_values[0][1]
            last_mem = memory_values[-1][1]
            memory_slope = 0.0
            if duration_minutes > 0:
                memory_slope = (last_mem - first_mem) / duration_minutes

            # CPU slope
            first_cpu = cpu_values[0][1]
            last_cpu = cpu_values[-1][1]
            cpu_slope = 0.0
            if duration_minutes > 0:
                cpu_slope = (last_cpu - first_cpu) / duration_minutes

            # Check checkpoint-to-checkpoint slopes for leaks
            memory_leak_detected = False
            cpu_leak_detected = False

            for checkpoint_min, containers_data in sorted(self._checkpoint_data.items()):
                if container in containers_data:
                    checkpoint_data = containers_data[container]
                    if checkpoint_data.get("memory_slope_mb_per_min", 0) > memory_threshold:
                        memory_leak_detected = True
                    if checkpoint_data.get("cpu_slope_percent_per_min", 0) > cpu_threshold:
                        cpu_leak_detected = True

            # Overall leak detection
            has_memory_leak = memory_leak_detected or memory_slope > memory_threshold
            has_cpu_leak = cpu_leak_detected or cpu_slope > cpu_threshold

            leak_analysis[container] = {
                "memory_slope_mb_per_min": round(memory_slope, 3),
                "cpu_slope_percent_per_min": round(cpu_slope, 3),
                "memory_leak_detected": has_memory_leak,
                "cpu_leak_detected": has_cpu_leak,
            }

        # Log findings for priority containers
        priority = self.config.analysis.priority_containers
        for container in priority:
            if container not in leak_analysis:
                continue
            analysis = leak_analysis[container]
            display = container.replace("rideshare-", "")

            if analysis["memory_leak_detected"]:
                console.print(
                    f"[red bold]MEMORY LEAK: {display} "
                    f"{analysis['memory_slope_mb_per_min']:.2f} MB/min[/red bold]"
                )
            elif analysis["cpu_leak_detected"]:
                console.print(
                    f"[yellow]CPU LEAK: {display} "
                    f"{analysis['cpu_slope_percent_per_min']:.2f} %/min[/yellow]"
                )
            else:
                console.print(
                    f"[green]{display} stable: mem={analysis['memory_slope_mb_per_min']:.2f} MB/min, "
                    f"cpu={analysis['cpu_slope_percent_per_min']:.2f} %/min[/green]"
                )

        # Store in metadata
        self._metadata["checkpoints"] = self._checkpoint_data
        self._metadata["leak_analysis"] = leak_analysis
