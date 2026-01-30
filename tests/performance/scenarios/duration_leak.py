"""Duration/leak detection scenario: measure memory over extended time."""

from typing import Any, Iterator

from rich.console import Console

from .base import BaseScenario

console = Console()


class DurationLeakScenario(BaseScenario):
    """Duration test for memory leak detection.

    Runs with a fixed number of agents for an extended period
    to detect memory leaks (slope > 1 MB/min flagged as potential leak).

    Protocol:
    1. Step 0: Clean environment (down -v, up -d, wait healthy)
    2. Start simulation
    3. Queue 40 drivers (mode=immediate)
    4. Queue 40 riders (mode=immediate)
    5. Wait for steady state
    6. Sample every 2s for duration
    7. Calculate memory trend (slope)
    8. Flag leak if slope > 1 MB/min
    """

    def __init__(self, duration_minutes: int, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.duration_minutes = duration_minutes
        self.agent_count = self.config.scenarios.duration_agent_count

    @property
    def name(self) -> str:
        return f"duration_leak_{self.duration_minutes}m"

    @property
    def description(self) -> str:
        return (
            f"Memory leak detection with {self.agent_count} agents "
            f"for {self.duration_minutes} minutes"
        )

    @property
    def params(self) -> dict[str, Any]:
        return {
            "duration_minutes": self.duration_minutes,
            "duration_seconds": self.duration_minutes * 60,
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
            f"({duration_seconds}s)...[/cyan]"
        )
        samples = self._collect_samples(duration_seconds)
        yield {"phase": "sampling_complete", "sample_count": len(samples)}

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
            f"{len(samples)} samples collected[/green]"
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

        # Calculate slope (MB per minute)
        first_ts, first_mem = memory_values[0]
        last_ts, last_mem = memory_values[-1]
        duration_minutes = (last_ts - first_ts) / 60

        if duration_minutes > 0:
            slope_mb_per_min = (last_mem - first_mem) / duration_minutes

            # Flag potential leak if slope > 1 MB/min
            if slope_mb_per_min > 1.0:
                console.print(
                    f"[red bold]POTENTIAL LEAK: {container} growing at "
                    f"{slope_mb_per_min:.2f} MB/min[/red bold]"
                )
            else:
                console.print(
                    f"[green]{container} memory stable: " f"{slope_mb_per_min:.2f} MB/min[/green]"
                )
