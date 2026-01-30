"""Baseline scenario: measure resource usage with 0 agents."""

from typing import Any, Iterator

from rich.console import Console

from .base import BaseScenario

console = Console()


class BaselineScenario(BaseScenario):
    """Baseline scenario with 0 agents.

    Measures baseline resource usage of all containers when
    the simulation is running but no agents are active.

    Protocol:
    1. Step 0: Clean environment (down -v, up -d, wait healthy)
    2. Wait 10s warmup
    3. Sample every 2s for 30s (15 samples)
    """

    @property
    def name(self) -> str:
        return "baseline"

    @property
    def description(self) -> str:
        return "Baseline resource usage with 0 agents"

    def execute(self) -> Iterator[dict[str, Any]]:
        """Execute baseline measurement."""
        # Warmup period
        console.print(f"[cyan]Warmup: {self.config.sampling.warmup_seconds}s[/cyan]")
        self._wait_for_steady_state(self.config.sampling.warmup_seconds)
        yield {"phase": "warmup_complete"}

        # Collect samples
        duration = self.config.scenarios.baseline_duration_seconds
        console.print(f"[cyan]Collecting samples for {duration}s...[/cyan]")
        samples = self._collect_samples(duration)
        yield {"phase": "sampling_complete", "sample_count": len(samples)}

        console.print(f"[green]Baseline complete: {len(samples)} samples collected[/green]")
