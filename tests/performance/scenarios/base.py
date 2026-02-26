"""Base scenario class for performance tests."""

import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator

from rich.console import Console

from ..collectors.docker_lifecycle import DockerLifecycleManager
from ..collectors.oom_detector import OOMDetector, OOMEvent
from ..collectors.prometheus_collector import PrometheusCollector
from ..collectors.simulation_api import SimulationAPIClient
from ..config import TestConfig

console = Console()


@dataclass
class ScenarioResult:
    """Result from running a scenario."""

    scenario_name: str
    scenario_params: dict[str, Any]
    started_at: str
    completed_at: str
    duration_seconds: float
    samples: list[dict[str, Any]]
    oom_events: list[dict[str, Any]]
    aborted: bool
    abort_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseScenario(ABC):
    """Abstract base class for performance test scenarios.

    All scenarios follow this protocol:
    1. Setup: Clean environment (Step 0) - down -v, up -d, wait healthy
    2. Execute: Run the scenario-specific test logic
    3. Teardown: Clean up (optional, depends on scenario)
    """

    def __init__(
        self,
        config: TestConfig,
        lifecycle: DockerLifecycleManager,
        prometheus: PrometheusCollector,
        api_client: SimulationAPIClient,
        oom_detector: OOMDetector,
    ) -> None:
        self.config = config
        self.lifecycle = lifecycle
        self.prometheus = prometheus
        self.api_client = api_client
        self.oom_detector = oom_detector
        self._samples: list[dict[str, Any]] = []
        self._oom_events: list[OOMEvent] = []
        self._aborted = False
        self._abort_reason: str | None = None
        self._metadata: dict[str, Any] = {}
        self._available_cores: int = 0  # Detected during setup

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this scenario."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of this scenario."""
        ...

    @property
    def params(self) -> dict[str, Any]:
        """Scenario-specific parameters."""
        return {}

    @property
    def requires_clean_restart(self) -> bool:
        """Whether this scenario requires a clean Docker restart before running.

        Scenarios can override to False when they can safely reuse the
        previous scenario's container state.
        """
        return True

    def setup(self) -> bool:
        """Step 0: Clean environment before scenario.

        Performs:
        1. docker compose down -v (unless requires_clean_restart is False)
        2. docker compose up -d (unless requires_clean_restart is False)
        3. Wait for healthy

        Returns:
            True if setup succeeded, False otherwise.
        """
        console.print(f"\n[bold cyan]Setting up scenario: {self.name}[/bold cyan]")
        console.print(f"[dim]{self.description}[/dim]")

        # Clean restart (unless scenario declares it can reuse previous state)
        if self.requires_clean_restart:
            if not self.lifecycle.clean_restart():
                console.print("[red]Setup failed: could not restart containers[/red]")
                return False
        else:
            console.print(
                f"[yellow]Skipping clean restart ({self.name} reuses previous state)[/yellow]"
            )

        # Wait for API to be available
        console.print("[cyan]Waiting for Simulation API...[/cyan]")
        max_wait = 60.0
        start = time.time()
        while time.time() - start < max_wait:
            if self.api_client.is_available():
                console.print("[green]Simulation API is ready[/green]")
                break
            time.sleep(2.0)
        else:
            console.print("[red]Setup failed: Simulation API not available[/red]")
            return False

        # Detect available CPU cores
        self._available_cores = self._detect_available_cores()
        console.print(f"[cyan]Available CPU cores: {self._available_cores}[/cyan]")

        # Capture OOM baseline
        self.oom_detector.capture_baseline()
        self._samples = []
        self._oom_events = []
        self._aborted = False
        self._abort_reason = None

        return True

    @abstractmethod
    def execute(self) -> Iterator[dict[str, Any]]:
        """Execute the scenario test logic.

        Yields:
            Progress updates as dicts with optional metadata.
        """
        ...

    def teardown(self) -> None:
        """Clean up after scenario (optional)."""
        # Default: do nothing, let next scenario's setup handle cleanup
        pass

    def _detect_available_cores(self) -> int:
        """Detect available CPU cores from Docker or config override.

        Returns:
            Number of available CPU cores.
        """
        # Use config override if set
        if self.config.docker.available_cpu_cores is not None:
            return self.config.docker.available_cpu_cores

        try:
            result = subprocess.run(
                ["docker", "info", "--format", "{{.NCPU}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except (subprocess.TimeoutExpired, ValueError, OSError) as e:
            console.print(f"[yellow]Could not detect CPU cores: {e}, defaulting to 1[/yellow]")

        return 1

    def _check_container_liveness(self) -> list[str]:
        """Check which expected containers are not running.

        Returns:
            List of container names that are not running.
        """
        dead_containers: list[str] = []
        for container_name in self.config.get_all_containers():
            health = self.lifecycle.get_container_health(container_name)
            if not health.running:
                dead_containers.append(container_name)
        return dead_containers

    def _collect_sample(self) -> dict[str, Any]:
        """Collect a single metric sample from all containers.

        Returns:
            Dict with timestamp and per-container metrics.
        """
        container_stats = self.prometheus.get_all_container_stats()

        # Check for OOM events
        oom_events = self.oom_detector.check_oom()
        self._oom_events.extend(oom_events)

        if oom_events:
            self._aborted = True
            self._abort_reason = (
                f"OOM detected in: {', '.join(e.container_name for e in oom_events)}"
            )

        # Check container liveness (skip if already aborted by OOM)
        if not self._aborted:
            dead = self._check_container_liveness()
            if dead:
                self._aborted = True
                self._abort_reason = f"Container(s) not running: {', '.join(dead)}"
                console.print(f"[red]Container failure detected: {', '.join(dead)}[/red]")

        # Build sample
        sample: dict[str, Any] = {
            "timestamp": time.time(),
            "timestamp_iso": datetime.now().isoformat(),
            "containers": {},
        }

        for name, stats in container_stats.items():
            sample["containers"][name] = {
                "memory_used_mb": stats.memory_used_mb,
                "memory_limit_mb": stats.memory_limit_mb,
                "memory_percent": stats.memory_percent,
                "cpu_percent": stats.cpu_percent,
            }

        # Compute global CPU sum across all containers
        global_cpu = sum(
            container_data["cpu_percent"] for container_data in sample["containers"].values()
        )
        sample["global_cpu_percent"] = round(global_cpu, 2)
        sample["available_cores"] = self._available_cores

        # Collect simulation status from the API (control fields)
        sim_status = self._collect_sim_status()
        if sim_status is not None:
            sample["rtr"] = sim_status

        # Collect infrastructure health latencies
        if self.config.scenarios.health_check_enabled:
            health_data = self.prometheus.get_health_latencies()
            if health_data is not None:
                sample["health"] = {
                    name: {
                        "latency_ms": svc.latency_ms,
                        "status": svc.status,
                        "message": svc.message,
                        "threshold_degraded": svc.threshold_degraded,
                        "threshold_unhealthy": svc.threshold_unhealthy,
                    }
                    for name, svc in health_data.items()
                }

        # Collect simulation metrics from Prometheus
        sim_metrics = self.prometheus.get_simulation_metrics()
        if sim_metrics is not None:
            sample["active_trips"] = sim_metrics.active_trips
            sample["throughput_events_per_sec"] = sim_metrics.throughput_events_per_sec
            sample["speed_multiplier"] = sim_metrics.speed_multiplier
            if sim_metrics.real_time_ratio is not None:
                sample.setdefault("rtr", {})["rtr"] = sim_metrics.real_time_ratio
            if sim_metrics.kafka_consumer_lag is not None:
                sample["kafka_consumer_lag"] = sim_metrics.kafka_consumer_lag
            if sim_metrics.simpy_event_queue is not None:
                sample["simpy_event_queue"] = sim_metrics.simpy_event_queue

        self._samples.append(sample)
        return sample

    def _collect_sim_status(self) -> dict[str, Any] | None:
        """Read simulation status from the API (control fields only, RTR comes from Prometheus)."""
        try:
            status = self.api_client.get_simulation_status()
        except Exception:
            return None

        result: dict[str, Any] = {
            "sim_time_iso": status.current_time,
            "speed_multiplier": status.speed_multiplier,
            "state": status.state,
            "active_trips": status.active_trips_count,
            "drivers_total": status.drivers_total,
            "riders_total": status.riders_total,
        }
        return result

    def _wait_for_steady_state(self, duration_seconds: float) -> None:
        """Wait for a specified duration, used for warmup/settle periods.

        Args:
            duration_seconds: Time to wait.
        """
        console.print(f"[dim]Waiting {duration_seconds:.0f}s for steady state...[/dim]")
        time.sleep(duration_seconds)

    def _collect_samples(
        self,
        duration_seconds: float,
        interval_seconds: float | None = None,
    ) -> list[dict[str, Any]]:
        """Collect samples for a specified duration.

        Args:
            duration_seconds: How long to collect samples.
            interval_seconds: Time between samples (default from config).

        Returns:
            List of collected samples.
        """
        if interval_seconds is None:
            interval_seconds = self.config.sampling.interval_seconds

        samples: list[dict[str, Any]] = []
        start_time = time.time()
        sample_count = 0

        while time.time() - start_time < duration_seconds:
            if self._aborted:
                console.print(f"[red]Collection aborted: {self._abort_reason}[/red]")
                break

            sample = self._collect_sample()
            samples.append(sample)
            sample_count += 1

            elapsed = time.time() - start_time
            console.print(
                f"[dim]Sample {sample_count}: elapsed={elapsed:.1f}s[/dim]",
                end="\r",
            )

            # Sleep until next sample time
            next_sample_time = start_time + (sample_count * interval_seconds)
            sleep_time = next_sample_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)

        console.print()  # Clear the progress line
        return samples

    def run(self) -> ScenarioResult:
        """Run the complete scenario: setup, execute, teardown.

        Returns:
            ScenarioResult with all collected data.
        """
        started_at = datetime.now().isoformat()
        start_time = time.time()

        try:
            # Setup
            if not self.setup():
                return ScenarioResult(
                    scenario_name=self.name,
                    scenario_params=self.params,
                    started_at=started_at,
                    completed_at=datetime.now().isoformat(),
                    duration_seconds=time.time() - start_time,
                    samples=[],
                    oom_events=[],
                    aborted=True,
                    abort_reason="Setup failed",
                )

            # Execute
            console.print(f"\n[bold green]Executing scenario: {self.name}[/bold green]")
            for progress in self.execute():
                if self._aborted:
                    break
                # Progress updates can be logged here if needed

            # Teardown
            self.teardown()

        except Exception as e:
            console.print(f"[red]Scenario error: {e}[/red]")
            self._aborted = True
            self._abort_reason = str(e)

        completed_at = datetime.now().isoformat()
        duration = time.time() - start_time

        # Convert OOM events to dicts
        oom_event_dicts = [
            {
                "container_name": e.container_name,
                "timestamp": e.timestamp,
                "timestamp_iso": e.timestamp_iso,
                "previous_restart_count": e.previous_restart_count,
                "current_restart_count": e.current_restart_count,
            }
            for e in self._oom_events
        ]

        result = ScenarioResult(
            scenario_name=self.name,
            scenario_params=self.params,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            samples=self._samples,
            oom_events=oom_event_dicts,
            aborted=self._aborted,
            abort_reason=self._abort_reason,
            metadata=self._metadata,
        )

        status = "[red]ABORTED[/red]" if self._aborted else "[green]COMPLETED[/green]"
        console.print(
            f"\n[bold]Scenario {self.name}: {status}[/bold] "
            f"({len(self._samples)} samples, {len(self._oom_events)} OOM events)"
        )

        return result
