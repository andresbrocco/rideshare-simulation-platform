"""Reset behavior scenario: verify memory returns to baseline after reset."""

from typing import Any, Iterator

from rich.console import Console

from .base import BaseScenario

console = Console()


class ResetBehaviorScenario(BaseScenario):
    """Reset behavior verification scenario.

    Verifies that simulation reset properly releases memory.
    Post-reset memory should be within 10% of baseline.

    Protocol:
    1. Step 0: Clean environment (down -v, up -d, wait healthy)
    2. Capture baseline (5 samples)
    3. Start simulation
    4. Apply load (40 agents immediate, 30s)
    5. Reset (POST /simulation/reset)
    6. Capture post-reset (30s)
    7. Compare: post-reset should be within 10% of baseline
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.agent_count = self.config.scenarios.duration_agent_count
        self._baseline_samples: list[dict[str, Any]] = []
        self._load_samples: list[dict[str, Any]] = []
        self._post_reset_samples: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "reset_behavior"

    @property
    def description(self) -> str:
        return "Verify memory returns to baseline after reset"

    @property
    def params(self) -> dict[str, Any]:
        return {
            "drivers": self.agent_count,
            "riders": self.agent_count,
            "tolerance_percent": self.config.scenarios.reset_tolerance_percent,
        }

    def execute(self) -> Iterator[dict[str, Any]]:
        """Execute reset behavior test."""
        # Phase 1: Capture baseline
        console.print("[bold cyan]Phase 1: Capturing baseline...[/bold cyan]")
        console.print("[cyan]Warming up...[/cyan]")
        self._wait_for_steady_state(self.config.sampling.warmup_seconds)

        console.print("[cyan]Collecting baseline samples...[/cyan]")
        self._baseline_samples = self._collect_samples(10.0)  # 5 samples at 2s interval
        yield {"phase": "baseline_complete", "sample_count": len(self._baseline_samples)}

        # Phase 2: Apply load
        console.print("[bold cyan]Phase 2: Applying load...[/bold cyan]")
        try:
            self.api_client.start()
        except Exception:
            pass  # May already be running

        console.print(f"[cyan]Queuing {self.agent_count} drivers (mode=immediate)...[/cyan]")
        self.api_client.queue_drivers(self.agent_count)

        console.print(f"[cyan]Queuing {self.agent_count} riders (mode=immediate)...[/cyan]")
        self.api_client.queue_riders(self.agent_count)

        console.print("[cyan]Waiting for spawn to complete...[/cyan]")
        if not self.api_client.wait_for_spawn_complete(timeout=120.0):
            console.print("[yellow]Warning: Spawn did not complete within timeout[/yellow]")

        # Settle and collect load samples
        self._wait_for_steady_state(self.config.sampling.settle_seconds)
        duration = self.config.scenarios.reset_load_duration_seconds
        console.print(f"[cyan]Collecting load samples for {duration}s...[/cyan]")
        self._load_samples = self._collect_samples(duration)
        yield {"phase": "load_complete", "sample_count": len(self._load_samples)}

        # Phase 3: Reset
        console.print("[bold cyan]Phase 3: Resetting simulation...[/bold cyan]")
        self.api_client.reset()
        yield {"phase": "reset_complete"}

        # Wait for reset to settle
        console.print("[cyan]Waiting for reset to settle...[/cyan]")
        self._wait_for_steady_state(self.config.sampling.settle_seconds)

        # Phase 4: Capture post-reset
        console.print("[bold cyan]Phase 4: Capturing post-reset...[/bold cyan]")
        duration = self.config.scenarios.reset_post_duration_seconds
        console.print(f"[cyan]Collecting post-reset samples for {duration}s...[/cyan]")
        self._post_reset_samples = self._collect_samples(duration)
        yield {"phase": "post_reset_complete", "sample_count": len(self._post_reset_samples)}

        # Phase 5: Analyze
        self._analyze_reset_effectiveness()
        yield {"phase": "analysis_complete"}

        console.print("[green]Reset behavior test complete[/green]")

    def _analyze_reset_effectiveness(self) -> None:
        """Compare post-reset memory to baseline."""
        if not self._baseline_samples or not self._post_reset_samples:
            console.print("[yellow]Insufficient samples for analysis[/yellow]")
            return

        tolerance = self.config.scenarios.reset_tolerance_percent

        # Focus on simulation container
        container = "rideshare-simulation"

        # Calculate average baseline memory
        baseline_mems = []
        for sample in self._baseline_samples:
            containers = sample.get("containers", {})
            if container in containers:
                baseline_mems.append(containers[container]["memory_used_mb"])

        # Calculate average post-reset memory
        post_reset_mems = []
        for sample in self._post_reset_samples:
            containers = sample.get("containers", {})
            if container in containers:
                post_reset_mems.append(containers[container]["memory_used_mb"])

        if not baseline_mems or not post_reset_mems:
            console.print(f"[yellow]No data for {container}[/yellow]")
            return

        baseline_avg = sum(baseline_mems) / len(baseline_mems)
        post_reset_avg = sum(post_reset_mems) / len(post_reset_mems)

        # Calculate load peak for reference
        load_mems = []
        for sample in self._load_samples:
            containers = sample.get("containers", {})
            if container in containers:
                load_mems.append(containers[container]["memory_used_mb"])
        load_peak = max(load_mems) if load_mems else 0

        # Calculate difference percentage
        if baseline_avg > 0:
            diff_percent = ((post_reset_avg - baseline_avg) / baseline_avg) * 100
        else:
            diff_percent = 0

        console.print(f"\n[bold]Reset Analysis for {container}:[/bold]")
        console.print(f"  Baseline avg:   {baseline_avg:.1f} MB")
        console.print(f"  Load peak:      {load_peak:.1f} MB")
        console.print(f"  Post-reset avg: {post_reset_avg:.1f} MB")
        console.print(f"  Difference:     {diff_percent:+.1f}%")

        if abs(diff_percent) <= tolerance:
            console.print(
                f"[green bold]PASS: Post-reset within {tolerance}% of baseline[/green bold]"
            )
        else:
            console.print(
                f"[red bold]FAIL: Post-reset exceeds {tolerance}% tolerance "
                f"({diff_percent:+.1f}%)[/red bold]"
            )

        # Store results in metadata
        self._samples.append(
            {
                "analysis": {
                    "container": container,
                    "baseline_avg_mb": baseline_avg,
                    "load_peak_mb": load_peak,
                    "post_reset_avg_mb": post_reset_avg,
                    "diff_percent": diff_percent,
                    "tolerance_percent": tolerance,
                    "passed": abs(diff_percent) <= tolerance,
                }
            }
        )
