"""Duration/leak detection scenario: 3-phase lifecycle observation."""

import time
from typing import Any, Iterator

from rich.console import Console

from .base import BaseScenario

console = Console()


class DurationLeakScenario(BaseScenario):
    """Duration test for memory leak detection with 3 explicit phases.

    Runs with a fixed number of agents through an active → drain → cooldown
    lifecycle to observe resource behavior during normal operation and
    after shutdown.

    Phases:
        1. Active (5 min, 2s sampling) - Agents running, trips cycling
        2. Drain (variable, 4s sampling) - pause() called, wait for PAUSED
        3. Cooldown (10 min, 8s sampling) - System idle, observe resource release

    Protocol:
    1. Step 0: Clean environment (down -v, up -d, wait healthy)
    2. Start simulation
    3. Queue N drivers + N riders (mode=immediate)
    4. Wait for spawn complete, settle
    5. Phase 1: Active sampling
    6. Phase 2: Pause and drain
    7. Phase 3: Cooldown observation
    8. Analyze per-phase slopes and cooldown memory delta
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
        self.active_minutes = self.config.scenarios.duration_active_minutes
        self.cooldown_minutes = self.config.scenarios.duration_cooldown_minutes
        self.drain_timeout = self.config.scenarios.duration_drain_timeout_seconds
        self.agent_count = agent_count
        self._phase_timestamps: dict[str, float] = {}
        self._phase_sample_counts: dict[str, int] = {}

    @property
    def name(self) -> str:
        return "duration_leak"

    @property
    def description(self) -> str:
        return (
            f"Memory leak detection with {self.agent_count} agents: "
            f"{self.active_minutes}m active + drain + {self.cooldown_minutes}m cooldown"
        )

    @property
    def params(self) -> dict[str, Any]:
        return {
            "active_minutes": self.active_minutes,
            "cooldown_minutes": self.cooldown_minutes,
            "drain_timeout_seconds": self.drain_timeout,
            "drivers": self.agent_count,
            "riders": self.agent_count,
            "agent_count_source": "stress_test_drivers_queued_half",
        }

    def execute(self) -> Iterator[dict[str, Any]]:
        """Execute 3-phase duration/leak test."""
        # Start simulation
        console.print("[cyan]Starting simulation...[/cyan]")
        try:
            self.api_client.start()
        except Exception as e:
            console.print(f"[yellow]Start response: {e}[/yellow]")
        yield {"phase": "simulation_started"}

        # Queue drivers (API limits to 100 per request, so batch if needed)
        console.print(f"[cyan]Queuing {self.agent_count} drivers (mode=immediate)...[/cyan]")
        remaining_drivers = self.agent_count
        while remaining_drivers > 0:
            batch = min(remaining_drivers, 100)
            self.api_client.queue_drivers(batch)
            remaining_drivers -= batch
        yield {"phase": "drivers_queued"}

        # Queue riders (API limits to 2000 per request, so batch if needed)
        console.print(f"[cyan]Queuing {self.agent_count} riders (mode=immediate)...[/cyan]")
        remaining_riders = self.agent_count
        while remaining_riders > 0:
            batch = min(remaining_riders, 2000)
            self.api_client.queue_riders(batch)
            remaining_riders -= batch
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

        # ── Phase 1: ACTIVE ──
        active_seconds = self.active_minutes * 60
        active_interval = self.config.sampling.interval_seconds
        console.print(
            f"[bold cyan]Phase 1/3: ACTIVE ({self.active_minutes}m, "
            f"{active_interval}s sampling)[/bold cyan]"
        )
        self._phase_timestamps["active_start"] = time.time()
        active_samples = self._collect_samples(active_seconds, active_interval)
        self._phase_timestamps["active_end"] = time.time()
        self._phase_sample_counts["active"] = len(active_samples)
        yield {"phase": "active_complete", "sample_count": len(active_samples)}

        if self._aborted:
            self._store_metadata()
            return

        # ── Phase 2: DRAIN ──
        drain_interval = self.config.sampling.drain_interval_seconds
        console.print(
            f"[bold cyan]Phase 2/3: DRAIN (timeout {self.drain_timeout}s, "
            f"{drain_interval}s sampling)[/bold cyan]"
        )
        console.print("[cyan]Calling pause()...[/cyan]")
        try:
            self.api_client.pause()
        except Exception as e:
            console.print(f"[yellow]Pause response: {e}[/yellow]")

        self._phase_timestamps["drain_start"] = time.time()
        drain_samples = self._collect_samples_until_state(
            target_state="paused",
            timeout=float(self.drain_timeout),
            interval=drain_interval,
        )
        self._phase_timestamps["drain_end"] = time.time()
        self._phase_sample_counts["drain"] = len(drain_samples)
        drain_duration = self._phase_timestamps["drain_end"] - self._phase_timestamps["drain_start"]
        console.print(
            f"[green]Drain completed in {drain_duration:.1f}s "
            f"({len(drain_samples)} samples)[/green]"
        )
        yield {"phase": "drain_complete", "sample_count": len(drain_samples)}

        if self._aborted:
            self._store_metadata()
            return

        # ── Phase 3: COOLDOWN ──
        cooldown_seconds = self.cooldown_minutes * 60
        cooldown_interval = self.config.sampling.cooldown_interval_seconds
        console.print(
            f"[bold cyan]Phase 3/3: COOLDOWN ({self.cooldown_minutes}m, "
            f"{cooldown_interval}s sampling)[/bold cyan]"
        )
        self._phase_timestamps["cooldown_start"] = time.time()
        cooldown_samples = self._collect_samples(cooldown_seconds, cooldown_interval)
        self._phase_timestamps["cooldown_end"] = time.time()
        self._phase_sample_counts["cooldown"] = len(cooldown_samples)
        yield {"phase": "cooldown_complete", "sample_count": len(cooldown_samples)}

        # Analyze phases
        self._analyze_phases()
        self._analyze_cooldown()

        # Stop simulation
        console.print("[cyan]Stopping simulation...[/cyan]")
        try:
            self.api_client.stop()
        except Exception as e:
            console.print(f"[yellow]Stop response: {e}[/yellow]")
        yield {"phase": "simulation_stopped"}

        self._store_metadata()

        total_samples = (
            self._phase_sample_counts.get("active", 0)
            + self._phase_sample_counts.get("drain", 0)
            + self._phase_sample_counts.get("cooldown", 0)
        )
        console.print(
            f"[green]Duration test ({self.active_minutes}m+drain+{self.cooldown_minutes}m) "
            f"complete: {total_samples} samples collected[/green]"
        )

    def _collect_samples_until_state(
        self, target_state: str, timeout: float, interval: float
    ) -> list[dict[str, Any]]:
        """Collect samples until simulation reaches target state or timeout.

        Args:
            target_state: State to wait for (e.g., "paused").
            timeout: Maximum wall-clock seconds to wait.
            interval: Seconds between samples.

        Returns:
            List of samples collected during the drain phase.
        """
        samples: list[dict[str, Any]] = []
        start_time = time.time()
        sample_count = 0

        while time.time() - start_time < timeout:
            if self._aborted:
                console.print("[red]Drain aborted due to OOM[/red]")
                break

            sample = self._collect_sample()
            samples.append(sample)
            sample_count += 1

            elapsed = time.time() - start_time
            console.print(
                f"[dim]Drain sample {sample_count}: elapsed={elapsed:.1f}s[/dim]",
                end="\r",
            )

            # Check if simulation reached target state
            try:
                status = self.api_client.get_simulation_status()
                if status.state.lower() == target_state.lower():
                    console.print(f"\n[green]Simulation reached '{target_state}' state[/green]")
                    break
            except Exception:
                pass

            # Sleep until next sample time
            next_sample_time = start_time + (sample_count * interval)
            sleep_time = next_sample_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)

        else:
            console.print(
                f"\n[yellow]Drain timeout reached ({timeout}s) "
                f"without reaching '{target_state}' state[/yellow]"
            )

        console.print()  # Clear the progress line
        return samples

    def _get_phase_samples(self, phase: str) -> list[dict[str, Any]]:
        """Get samples belonging to a specific phase by sample count boundaries.

        Args:
            phase: Phase name ("active", "drain", or "cooldown").

        Returns:
            Slice of self._samples for the given phase.
        """
        active_count = self._phase_sample_counts.get("active", 0)
        drain_count = self._phase_sample_counts.get("drain", 0)

        if phase == "active":
            return self._samples[:active_count]
        elif phase == "drain":
            return self._samples[active_count : active_count + drain_count]
        elif phase == "cooldown":
            return self._samples[active_count + drain_count :]
        return []

    def _compute_slopes(self, samples: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
        """Compute memory and CPU slopes per container from a set of samples.

        Args:
            samples: List of sample dicts.

        Returns:
            Dict mapping container -> {"memory_slope_mb_per_min", "cpu_slope_percent_per_min"}.
        """
        if len(samples) < 2:
            return {}

        # Find all containers
        all_containers: set[str] = set()
        for sample in samples:
            all_containers.update(sample.get("containers", {}).keys())

        slopes: dict[str, dict[str, float]] = {}

        for container in all_containers:
            memory_values: list[tuple[float, float]] = []
            cpu_values: list[tuple[float, float]] = []

            for sample in samples:
                containers = sample.get("containers", {})
                if container in containers:
                    ts = sample["timestamp"]
                    mem = containers[container]["memory_used_mb"]
                    cpu = containers[container]["cpu_percent"]
                    memory_values.append((ts, mem))
                    cpu_values.append((ts, cpu))

            if len(memory_values) < 2:
                continue

            first_ts = memory_values[0][0]
            last_ts = memory_values[-1][0]
            duration_min = (last_ts - first_ts) / 60

            memory_slope = 0.0
            cpu_slope = 0.0
            if duration_min > 0:
                memory_slope = (memory_values[-1][1] - memory_values[0][1]) / duration_min
                cpu_slope = (cpu_values[-1][1] - cpu_values[0][1]) / duration_min

            slopes[container] = {
                "memory_slope_mb_per_min": round(memory_slope, 3),
                "cpu_slope_percent_per_min": round(cpu_slope, 3),
            }

        return slopes

    def _analyze_phases(self) -> None:
        """Analyze memory and CPU slopes per phase per container."""
        memory_threshold = self.config.analysis.leak_threshold_mb_per_min
        cpu_threshold = self.config.analysis.cpu_leak_threshold_per_min

        phase_analysis: dict[str, dict[str, dict[str, float]]] = {}
        leak_analysis: dict[str, dict[str, Any]] = {}

        for phase in ("active", "drain", "cooldown"):
            phase_samples = self._get_phase_samples(phase)
            slopes = self._compute_slopes(phase_samples)
            phase_analysis[phase] = slopes

        # Build per-container leak summary from active phase
        active_slopes: dict[str, dict[str, float]] = phase_analysis.get("active", {})
        for container, container_slopes in active_slopes.items():
            mem_slope = container_slopes["memory_slope_mb_per_min"]
            cpu_slope = container_slopes["cpu_slope_percent_per_min"]
            has_memory_leak = mem_slope > memory_threshold
            has_cpu_leak = cpu_slope > cpu_threshold

            leak_analysis[container] = {
                "memory_slope_mb_per_min": mem_slope,
                "cpu_slope_percent_per_min": cpu_slope,
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
                    f"{analysis['memory_slope_mb_per_min']:.2f} MB/min (active phase)[/red bold]"
                )
            elif analysis["cpu_leak_detected"]:
                console.print(
                    f"[yellow]CPU LEAK: {display} "
                    f"{analysis['cpu_slope_percent_per_min']:.2f} %/min (active phase)[/yellow]"
                )
            else:
                console.print(
                    f"[green]{display} stable: "
                    f"mem={analysis['memory_slope_mb_per_min']:.2f} MB/min, "
                    f"cpu={analysis['cpu_slope_percent_per_min']:.2f} %/min[/green]"
                )

        self._metadata["phase_analysis"] = phase_analysis
        self._metadata["leak_analysis"] = leak_analysis

    def _analyze_cooldown(self) -> None:
        """Compare per-container memory at cooldown end vs active end (drain start)."""
        active_samples = self._get_phase_samples("active")
        cooldown_samples = self._get_phase_samples("cooldown")

        if not active_samples or not cooldown_samples:
            console.print("[yellow]Insufficient data for cooldown analysis[/yellow]")
            return

        active_end_sample = active_samples[-1]
        cooldown_end_sample = cooldown_samples[-1]

        cooldown_analysis: dict[str, dict[str, float]] = {}

        all_containers: set[str] = set()
        all_containers.update(active_end_sample.get("containers", {}).keys())
        all_containers.update(cooldown_end_sample.get("containers", {}).keys())

        for container in all_containers:
            active_data = active_end_sample.get("containers", {}).get(container, {})
            cooldown_data = cooldown_end_sample.get("containers", {}).get(container, {})

            active_mem = active_data.get("memory_used_mb", 0.0)
            cooldown_mem = cooldown_data.get("memory_used_mb", 0.0)

            if active_mem > 0:
                delta_mb = cooldown_mem - active_mem
                delta_percent = (delta_mb / active_mem) * 100
                released = delta_mb < 0

                cooldown_analysis[container] = {
                    "active_end_mb": round(active_mem, 2),
                    "cooldown_end_mb": round(cooldown_mem, 2),
                    "delta_mb": round(delta_mb, 2),
                    "delta_percent": round(delta_percent, 2),
                    "memory_released": released,
                }

        # Log cooldown results for priority containers
        priority = self.config.analysis.priority_containers
        for container in priority:
            if container not in cooldown_analysis:
                continue
            data = cooldown_analysis[container]
            display = container.replace("rideshare-", "")
            delta = data["delta_mb"]

            if data["memory_released"]:
                console.print(
                    f"[green]{display}: released {abs(delta):.1f} MB "
                    f"({data['active_end_mb']:.1f} -> {data['cooldown_end_mb']:.1f} MB)[/green]"
                )
            else:
                console.print(
                    f"[yellow]{display}: retained +{delta:.1f} MB "
                    f"({data['active_end_mb']:.1f} -> {data['cooldown_end_mb']:.1f} MB)[/yellow]"
                )

        self._metadata["cooldown_analysis"] = cooldown_analysis

    def _store_metadata(self) -> None:
        """Store phase timestamps and sample counts in metadata."""
        self._metadata["phase_timestamps"] = self._phase_timestamps
        self._metadata["phase_sample_counts"] = self._phase_sample_counts
        if "drain_start" in self._phase_timestamps and "drain_end" in self._phase_timestamps:
            self._metadata["drain_duration_seconds"] = round(
                self._phase_timestamps["drain_end"] - self._phase_timestamps["drain_start"], 2
            )
