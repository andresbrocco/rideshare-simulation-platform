"""OOM (Out of Memory) event detection for Docker containers."""

import subprocess
import time
from dataclasses import dataclass
from datetime import datetime

from rich.console import Console

from ..config import CONTAINER_CONFIG

console = Console()


@dataclass
class OOMEvent:
    """Represents an OOM kill event."""

    container_name: str
    timestamp: float
    timestamp_iso: str
    previous_restart_count: int
    current_restart_count: int


@dataclass
class ContainerBaseline:
    """Baseline state for a container before testing."""

    container_name: str
    restart_count: int
    oom_killed: bool
    captured_at: float


class OOMDetector:
    """Detects OOM events by monitoring container restart counts.

    Strategy:
    1. Primary: `docker inspect {container} --format '{{.State.OOMKilled}} {{.RestartCount}}'`
       - Check every sample interval
       - Compare RestartCount to baseline
    2. Early Warning: Log if memory_percent > 95%
    3. On OOM: Mark scenario aborted, log event, continue to next scenario
    """

    def __init__(self) -> None:
        self._baselines: dict[str, ContainerBaseline] = {}
        self._oom_events: list[OOMEvent] = []

    def _get_container_state(self, container_name: str) -> tuple[bool, int] | None:
        """Get OOMKilled and RestartCount for a container.

        Returns:
            Tuple of (oom_killed, restart_count), or None if container not found.
        """
        try:
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.State.OOMKilled}} {{.RestartCount}}",
                    container_name,
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                return None

            parts = result.stdout.strip().split()
            if len(parts) < 2:
                return None

            oom_killed = parts[0].lower() == "true"
            restart_count = int(parts[1])
            return (oom_killed, restart_count)
        except Exception:
            return None

    def capture_baseline(self, containers: list[str] | None = None) -> dict[str, ContainerBaseline]:
        """Capture baseline restart counts for all containers.

        Args:
            containers: List of container names to capture.
                       If None, captures all known containers.

        Returns:
            Dict mapping container name to baseline.
        """
        if containers is None:
            containers = list(CONTAINER_CONFIG.keys())

        self._baselines.clear()
        self._oom_events.clear()
        now = time.time()

        for container_name in containers:
            state = self._get_container_state(container_name)
            if state is not None:
                oom_killed, restart_count = state
                self._baselines[container_name] = ContainerBaseline(
                    container_name=container_name,
                    restart_count=restart_count,
                    oom_killed=oom_killed,
                    captured_at=now,
                )

        console.print(f"[cyan]Captured baseline for {len(self._baselines)} containers[/cyan]")
        return self._baselines.copy()

    def check_oom(self, containers: list[str] | None = None) -> list[OOMEvent]:
        """Check for OOM events since baseline was captured.

        Args:
            containers: List of container names to check.
                       If None, checks all containers with baselines.

        Returns:
            List of new OOM events detected since last check.
        """
        if containers is None:
            containers = list(self._baselines.keys())

        new_events: list[OOMEvent] = []
        now = time.time()
        timestamp_iso = datetime.fromtimestamp(now).isoformat()

        for container_name in containers:
            baseline = self._baselines.get(container_name)
            if baseline is None:
                continue

            state = self._get_container_state(container_name)
            if state is None:
                continue

            oom_killed, restart_count = state

            # Check if restart count increased
            if restart_count > baseline.restart_count:
                event = OOMEvent(
                    container_name=container_name,
                    timestamp=now,
                    timestamp_iso=timestamp_iso,
                    previous_restart_count=baseline.restart_count,
                    current_restart_count=restart_count,
                )
                new_events.append(event)
                self._oom_events.append(event)

                # Update baseline to prevent duplicate detections
                self._baselines[container_name] = ContainerBaseline(
                    container_name=container_name,
                    restart_count=restart_count,
                    oom_killed=oom_killed,
                    captured_at=now,
                )

                console.print(
                    f"[red bold]OOM detected: {container_name} "
                    f"(restarts: {baseline.restart_count} -> {restart_count})[/red bold]"
                )

        return new_events

    def get_all_oom_events(self) -> list[OOMEvent]:
        """Get all OOM events detected since baseline capture.

        Returns:
            List of all OOM events.
        """
        return self._oom_events.copy()

    def has_oom_events(self) -> bool:
        """Check if any OOM events have been detected.

        Returns:
            True if any OOM events have occurred.
        """
        return len(self._oom_events) > 0

    def clear(self) -> None:
        """Clear all baselines and events."""
        self._baselines.clear()
        self._oom_events.clear()


@dataclass
class MemoryWarning:
    """Warning for high memory usage (potential OOM)."""

    container_name: str
    memory_percent: float
    timestamp: float


class MemoryWarningTracker:
    """Tracks high memory warnings as potential OOM indicators."""

    def __init__(self, threshold_percent: float = 95.0) -> None:
        self.threshold_percent = threshold_percent
        self._warnings: list[MemoryWarning] = []

    def check_memory(self, container_name: str, memory_percent: float) -> MemoryWarning | None:
        """Check if memory usage exceeds threshold.

        Args:
            container_name: Name of the container.
            memory_percent: Current memory usage percentage.

        Returns:
            MemoryWarning if threshold exceeded, None otherwise.
        """
        if memory_percent > self.threshold_percent:
            warning = MemoryWarning(
                container_name=container_name,
                memory_percent=memory_percent,
                timestamp=time.time(),
            )
            self._warnings.append(warning)
            console.print(
                f"[yellow]Memory warning: {container_name} at {memory_percent:.1f}%[/yellow]"
            )
            return warning
        return None

    def get_warnings(self) -> list[MemoryWarning]:
        """Get all memory warnings."""
        return self._warnings.copy()

    def clear(self) -> None:
        """Clear all warnings."""
        self._warnings.clear()
