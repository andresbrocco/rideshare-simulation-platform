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
        """Compare post-reset memory and CPU to baseline for all containers."""
        if not self._baseline_samples or not self._post_reset_samples:
            console.print("[yellow]Insufficient samples for analysis[/yellow]")
            return

        tolerance = self.config.scenarios.reset_tolerance_percent

        # Find all containers
        all_containers: set[str] = set()
        for sample in self._baseline_samples + self._load_samples + self._post_reset_samples:
            all_containers.update(sample.get("containers", {}).keys())

        all_container_results: dict[str, dict[str, Any]] = {}

        for container in all_containers:
            # Collect baseline data
            baseline_mems: list[float] = []
            baseline_cpus: list[float] = []
            for sample in self._baseline_samples:
                containers = sample.get("containers", {})
                if container in containers:
                    baseline_mems.append(containers[container]["memory_used_mb"])
                    baseline_cpus.append(containers[container]["cpu_percent"])

            # Collect load data
            load_mems: list[float] = []
            load_cpus: list[float] = []
            for sample in self._load_samples:
                containers = sample.get("containers", {})
                if container in containers:
                    load_mems.append(containers[container]["memory_used_mb"])
                    load_cpus.append(containers[container]["cpu_percent"])

            # Collect post-reset data
            post_reset_mems: list[float] = []
            post_reset_cpus: list[float] = []
            for sample in self._post_reset_samples:
                containers = sample.get("containers", {})
                if container in containers:
                    post_reset_mems.append(containers[container]["memory_used_mb"])
                    post_reset_cpus.append(containers[container]["cpu_percent"])

            if not baseline_mems or not post_reset_mems:
                continue

            # Calculate averages and peaks
            baseline_mem_avg = sum(baseline_mems) / len(baseline_mems)
            baseline_cpu_avg = sum(baseline_cpus) / len(baseline_cpus) if baseline_cpus else 0
            load_mem_peak = max(load_mems) if load_mems else 0
            load_cpu_peak = max(load_cpus) if load_cpus else 0
            post_reset_mem_avg = sum(post_reset_mems) / len(post_reset_mems)
            post_reset_cpu_avg = (
                sum(post_reset_cpus) / len(post_reset_cpus) if post_reset_cpus else 0
            )

            # Calculate difference percentages
            mem_diff_percent = 0.0
            if baseline_mem_avg > 0:
                mem_diff_percent = (
                    (post_reset_mem_avg - baseline_mem_avg) / baseline_mem_avg
                ) * 100

            cpu_diff_percent = 0.0
            if baseline_cpu_avg > 0:
                cpu_diff_percent = (
                    (post_reset_cpu_avg - baseline_cpu_avg) / baseline_cpu_avg
                ) * 100

            all_container_results[container] = {
                "baseline_mem_avg_mb": round(baseline_mem_avg, 2),
                "baseline_cpu_avg_percent": round(baseline_cpu_avg, 2),
                "load_mem_peak_mb": round(load_mem_peak, 2),
                "load_cpu_peak_percent": round(load_cpu_peak, 2),
                "post_reset_mem_avg_mb": round(post_reset_mem_avg, 2),
                "post_reset_cpu_avg_percent": round(post_reset_cpu_avg, 2),
                "mem_diff_percent": round(mem_diff_percent, 2),
                "cpu_diff_percent": round(cpu_diff_percent, 2),
                "mem_passed": abs(mem_diff_percent) <= tolerance,
                "cpu_passed": abs(cpu_diff_percent) <= tolerance,
            }

        # Log priority containers
        priority = self.config.analysis.priority_containers
        for container in priority:
            if container not in all_container_results:
                continue
            result = all_container_results[container]
            display = container.replace("rideshare-", "")

            console.print(f"\n[bold]Reset Analysis for {display}:[/bold]")
            console.print(
                f"  Memory: baseline={result['baseline_mem_avg_mb']:.1f} MB, "
                f"peak={result['load_mem_peak_mb']:.1f} MB, "
                f"post={result['post_reset_mem_avg_mb']:.1f} MB ({result['mem_diff_percent']:+.1f}%)"
            )
            console.print(
                f"  CPU:    baseline={result['baseline_cpu_avg_percent']:.1f}%, "
                f"peak={result['load_cpu_peak_percent']:.1f}%, "
                f"post={result['post_reset_cpu_avg_percent']:.1f}% ({result['cpu_diff_percent']:+.1f}%)"
            )

            if result["mem_passed"]:
                console.print(
                    f"[green bold]  PASS: Memory within {tolerance}% of baseline[/green bold]"
                )
            else:
                console.print(f"[red bold]  FAIL: Memory exceeds {tolerance}% tolerance[/red bold]")

        # Store results in samples
        self._samples.append(
            {
                "analysis": {
                    "tolerance_percent": tolerance,
                    "all_containers": all_container_results,
                }
            }
        )
