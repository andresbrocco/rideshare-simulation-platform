"""Baseline scenario: measure resource usage with 0 agents."""

from typing import Any, Iterator

from rich.console import Console

from ..analysis.statistics import BaselineCalibration, compute_baseline_calibration
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
    4. Compute baseline calibration for dynamic stop-condition thresholds
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.calibration: BaselineCalibration | None = None

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

        # Compute baseline calibration for dynamic thresholds
        self.calibration = compute_baseline_calibration(
            samples=samples,
            degraded_multiplier=self.config.scenarios.health_baseline_degraded_multiplier,
            unhealthy_multiplier=self.config.scenarios.health_baseline_unhealthy_multiplier,
            rtr_fraction=self.config.scenarios.rtr_baseline_fraction,
            rtr_config_fallback=self.config.scenarios.stress_rtr_threshold,
        )
        self._metadata["calibration"] = self.calibration.to_dict()

        # Print calibration summary
        n_services = len(self.calibration.health_thresholds)
        rtr_info = (
            f"RTR threshold={self.calibration.rtr_threshold:.4f} "
            f"({self.calibration.rtr_threshold_source})"
            if self.calibration.rtr_threshold is not None
            else "RTR: no data"
        )
        console.print(
            f"[green]Baseline complete: {len(samples)} samples collected, "
            f"calibrated {n_services} services, {rtr_info}[/green]"
        )
