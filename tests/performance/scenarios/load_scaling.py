"""Load scaling scenario: measure resource usage at various agent counts."""

from typing import Any, Iterator

from rich.console import Console

from .base import BaseScenario

console = Console()


class LoadScalingScenario(BaseScenario):
    """Load scaling scenario at a specific agent count.

    Measures resource usage with N drivers and N riders active.
    All agents spawn with mode=immediate.

    Protocol:
    1. Step 0: Clean environment (down -v, up -d, wait healthy)
    2. Start simulation (POST /simulation/start)
    3. Queue N drivers (POST /agents/drivers?mode=immediate)
    4. Queue N riders (POST /agents/riders?mode=immediate)
    5. Wait for spawn queues empty (poll /agents/spawn-status)
    6. Wait 5s settle time
    7. Sample every 2s for 60s (30 samples)
    8. Stop simulation
    """

    def __init__(self, agent_count: int, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.agent_count = agent_count

    @property
    def name(self) -> str:
        return f"load_scaling_{self.agent_count}"

    @property
    def description(self) -> str:
        return f"Load test with {self.agent_count} drivers and {self.agent_count} riders"

    @property
    def params(self) -> dict[str, Any]:
        return {
            "drivers": self.agent_count,
            "riders": self.agent_count,
            "total_agents": self.agent_count * 2,
        }

    def execute(self) -> Iterator[dict[str, Any]]:
        """Execute load scaling test."""
        # Start simulation
        console.print("[cyan]Starting simulation...[/cyan]")
        try:
            self.api_client.start()
        except Exception as e:
            # Simulation might already be running
            console.print(f"[yellow]Start response: {e}[/yellow]")
        yield {"phase": "simulation_started"}

        # Queue drivers
        console.print(f"[cyan]Queuing {self.agent_count} drivers (mode=immediate)...[/cyan]")
        driver_response = self.api_client.queue_drivers(self.agent_count)
        console.print(f"[dim]Drivers queued: {driver_response}[/dim]")
        yield {"phase": "drivers_queued", "response": driver_response}

        # Queue riders
        console.print(f"[cyan]Queuing {self.agent_count} riders (mode=immediate)...[/cyan]")
        rider_response = self.api_client.queue_riders(self.agent_count)
        console.print(f"[dim]Riders queued: {rider_response}[/dim]")
        yield {"phase": "riders_queued", "response": rider_response}

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

        # Collect samples
        duration = self.config.scenarios.load_duration_seconds
        console.print(f"[cyan]Collecting samples for {duration}s...[/cyan]")
        samples = self._collect_samples(duration)
        yield {"phase": "sampling_complete", "sample_count": len(samples)}

        # Stop simulation
        console.print("[cyan]Stopping simulation...[/cyan]")
        try:
            self.api_client.stop()
        except Exception as e:
            console.print(f"[yellow]Stop response: {e}[/yellow]")
        yield {"phase": "simulation_stopped"}

        console.print(
            f"[green]Load scaling ({self.agent_count} agents) complete: "
            f"{len(samples)} samples collected[/green]"
        )
