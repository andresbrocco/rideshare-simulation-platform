"""Docker container lifecycle management for performance testing."""

import subprocess
import time
from dataclasses import dataclass
from typing import Any

from rich.console import Console

from ..config import TestConfig

console = Console()


@dataclass
class ContainerHealth:
    """Health status of a container."""

    name: str
    running: bool
    healthy: bool
    status: str


class DockerLifecycleManager:
    """Manages Docker container lifecycle for performance tests.

    Handles teardown, startup, and health checking of containers.
    """

    def __init__(self, config: TestConfig) -> None:
        self.config = config

    def get_compose_command(self) -> list[str]:
        """Get the base docker compose command with all profiles."""
        return self.config.get_compose_base_command()

    def teardown_with_volumes(self, timeout: float = 300.0) -> tuple[bool, float]:
        """Tear down all containers and remove volumes.

        Args:
            timeout: Maximum time to wait for teardown.

        Returns:
            Tuple of (success, elapsed_seconds).
        """
        cmd = self.get_compose_command() + ["down", "-v"]
        console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")
        console.print(f"[dim]Timeout: {timeout:.0f}s[/dim]")

        start = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = time.time() - start

            if result.returncode != 0:
                console.print(f"[red]Teardown failed after {elapsed:.1f}s[/red]")
                if result.stderr:
                    console.print(f"[red]stderr: {result.stderr[:500]}[/red]")
                return False, elapsed

            console.print(f"[green]Teardown complete in {elapsed:.1f}s[/green]")
            return True, elapsed

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            console.print(f"[red]Teardown timed out after {elapsed:.1f}s[/red]")
            return False, elapsed
        except Exception as e:
            elapsed = time.time() - start
            console.print(f"[red]Teardown error after {elapsed:.1f}s: {e}[/red]")
            return False, elapsed

    def start_all_profiles(self, timeout: float = 900.0) -> tuple[bool, float]:
        """Start all containers with all profiles.

        Args:
            timeout: Maximum time to wait for startup.

        Returns:
            Tuple of (success, elapsed_seconds).
        """
        cmd = self.get_compose_command() + ["up", "-d"]
        console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")
        console.print(f"[dim]Timeout: {timeout:.0f}s[/dim]")

        start = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = time.time() - start

            if result.returncode != 0:
                console.print(f"[red]Startup failed after {elapsed:.1f}s[/red]")
                if result.stderr:
                    console.print(f"[red]stderr: {result.stderr[:500]}[/red]")
                if result.stdout:
                    console.print(f"[dim]stdout: {result.stdout[:500]}[/dim]")
                return False, elapsed

            console.print(f"[green]Containers started in {elapsed:.1f}s[/green]")
            if result.stdout:
                # Show container count from output
                lines = result.stdout.strip().split("\n")
                console.print(f"[dim]Started {len(lines)} containers[/dim]")
            return True, elapsed

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            console.print(
                f"[red]Startup timed out after {elapsed:.1f}s (limit: {timeout:.0f}s)[/red]"
            )
            console.print(
                "[yellow]Tip: Some containers may still be starting in the background[/yellow]"
            )
            return False, elapsed
        except Exception as e:
            elapsed = time.time() - start
            console.print(f"[red]Startup error after {elapsed:.1f}s: {e}[/red]")
            return False, elapsed

    def get_container_health(self, container_name: str) -> ContainerHealth:
        """Get health status of a specific container.

        Args:
            container_name: Name of the container to check.

        Returns:
            ContainerHealth with status information.
        """
        try:
            # Get container state
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.State.Running}} {{.State.Health.Status}}",
                    container_name,
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                return ContainerHealth(
                    name=container_name,
                    running=False,
                    healthy=False,
                    status="not_found",
                )

            parts = result.stdout.strip().split()
            running = parts[0].lower() == "true" if parts else False
            health_status = parts[1] if len(parts) > 1 else "unknown"

            # Some containers don't have health checks, treat running as healthy
            healthy = health_status == "healthy" or (running and health_status == "")

            return ContainerHealth(
                name=container_name,
                running=running,
                healthy=healthy,
                status=health_status or "no_healthcheck",
            )
        except Exception as e:
            return ContainerHealth(
                name=container_name,
                running=False,
                healthy=False,
                status=f"error: {e}",
            )

    def wait_for_healthy(
        self,
        timeout: float = 900.0,
        check_interval: float = 5.0,
        required_containers: list[str] | None = None,
    ) -> tuple[bool, float]:
        """Wait for all containers to be healthy.

        Args:
            timeout: Maximum time to wait.
            check_interval: Time between health checks.
            required_containers: List of container names to wait for.
                               If None, uses core containers.

        Returns:
            Tuple of (success, elapsed_seconds).
        """
        if required_containers is None:
            # Default to core containers that must be healthy
            required_containers = [
                "rideshare-kafka",
                "rideshare-redis",
                "rideshare-osrm",
                "rideshare-simulation",
                "rideshare-cadvisor",
                "rideshare-stream-processor",
                "rideshare-frontend",
            ]

        start_time = time.time()
        console.print(
            f"[cyan]Waiting for {len(required_containers)} containers to be healthy...[/cyan]"
        )
        console.print(f"[dim]Timeout: {timeout:.0f}s[/dim]")
        console.print(f"[dim]Containers: {', '.join(required_containers)}[/dim]")

        while time.time() - start_time < timeout:
            unhealthy = []
            healthy_list = []
            for container in required_containers:
                health = self.get_container_health(container)
                if not health.healthy:
                    unhealthy.append(f"{container}({health.status})")
                else:
                    healthy_list.append(container)

            if not unhealthy:
                elapsed = time.time() - start_time
                console.print(
                    f"[green]All {len(required_containers)} containers healthy in {elapsed:.1f}s[/green]"
                )
                return True, elapsed

            elapsed = time.time() - start_time
            remaining = timeout - elapsed
            console.print(
                f"[yellow]Waiting... {elapsed:.0f}s elapsed, {remaining:.0f}s remaining | "
                f"Healthy: {len(healthy_list)}/{len(required_containers)} | "
                f"Unhealthy: {', '.join(unhealthy[:3])}"
                f"{'...' if len(unhealthy) > 3 else ''}[/yellow]"
            )
            time.sleep(check_interval)

        elapsed = time.time() - start_time
        console.print(f"[red]Timeout waiting for containers after {elapsed:.1f}s[/red]")
        # Show final status of each container
        for container in required_containers:
            health = self.get_container_health(container)
            status_color = "green" if health.healthy else "red"
            console.print(f"[{status_color}]  {container}: {health.status}[/{status_color}]")
        return False, elapsed

    def _log_container_states(self) -> None:
        """Log the current state of all expected containers for diagnostics."""
        console.print("\n[yellow]Container diagnostics:[/yellow]")
        expected_containers = [
            "rideshare-kafka",
            "rideshare-redis",
            "rideshare-osrm",
            "rideshare-simulation",
            "rideshare-cadvisor",
            "rideshare-stream-processor",
            "rideshare-frontend",
            "rideshare-minio",
            "rideshare-spark-thrift-server",
            "rideshare-bronze-ingestion-high-volume",
            "rideshare-bronze-ingestion-low-volume",
            "rideshare-airflow-webserver",
            "rideshare-airflow-scheduler",
            "rideshare-prometheus",
            "rideshare-grafana",
        ]
        for container in expected_containers:
            health = self.get_container_health(container)
            status_icon = "[green]OK[/green]" if health.healthy else "[red]FAIL[/red]"
            console.print(
                f"  {status_icon} {container}: running={health.running}, status={health.status}"
            )

    def clean_restart(self, timeout: float = 1800.0) -> bool:
        """Perform a clean restart: teardown with volumes, start fresh.

        Uses dynamic timeout allocation: each phase gets remaining time
        proportionally, so fast phases give more time to slower phases.

        Args:
            timeout: Total timeout for the entire operation (default 30 min).

        Returns:
            True if restart succeeded, False otherwise.
        """
        console.print("[bold cyan]Performing clean restart...[/bold cyan]")
        console.print(f"[dim]Total timeout budget: {timeout:.0f}s ({timeout/60:.0f} min)[/dim]")

        overall_start = time.time()
        phase_results: dict[str, dict[str, Any]] = {}

        # Phase 1: Teardown (usually fast, allocate 10% max)
        teardown_timeout = min(timeout * 0.1, 300.0)  # Cap at 5 minutes
        console.print("\n[bold]Phase 1/3: Teardown[/bold]")
        success, teardown_elapsed = self.teardown_with_volumes(timeout=teardown_timeout)
        phase_results["teardown"] = {
            "success": success,
            "elapsed_seconds": teardown_elapsed,
            "timeout": teardown_timeout,
        }
        if not success:
            console.print("[red]Phase 1 FAILED: Teardown did not complete[/red]")
            console.print(f"[dim]Phase results: {phase_results}[/dim]")
            return False

        # Wait a moment for resources to be released
        time.sleep(2.0)

        # Calculate remaining time
        total_elapsed = time.time() - overall_start
        remaining = timeout - total_elapsed
        console.print(f"[dim]Time used: {total_elapsed:.1f}s | Remaining: {remaining:.1f}s[/dim]")

        if remaining < 30:
            console.print("[red]Not enough time remaining for startup[/red]")
            return False

        # Phase 2: Start containers (allocate 15% of remaining, cap at 5 min)
        startup_timeout = min(remaining * 0.15, 300.0)  # Cap at 5 min
        console.print("\n[bold]Phase 2/3: Start containers[/bold]")
        success, startup_elapsed = self.start_all_profiles(timeout=startup_timeout)
        phase_results["startup"] = {
            "success": success,
            "elapsed_seconds": startup_elapsed,
            "timeout": startup_timeout,
        }
        if not success:
            console.print("[red]Phase 2 FAILED: Container startup did not complete[/red]")
            console.print(f"[dim]Phase results: {phase_results}[/dim]")
            self._log_container_states()
            return False

        # Calculate remaining time for health checks
        total_elapsed = time.time() - overall_start
        remaining = timeout - total_elapsed
        console.print(f"[dim]Time used: {total_elapsed:.1f}s | Remaining: {remaining:.1f}s[/dim]")

        if remaining < 30:
            console.print("[red]Not enough time remaining for health checks[/red]")
            return False

        # Phase 3: Wait for healthy (use all remaining time)
        console.print("\n[bold]Phase 3/3: Wait for healthy[/bold]")
        success, health_elapsed = self.wait_for_healthy(timeout=remaining)
        phase_results["health_check"] = {
            "success": success,
            "elapsed_seconds": health_elapsed,
            "timeout": remaining,
        }

        total_elapsed = time.time() - overall_start
        if success:
            console.print(f"\n[green]Clean restart completed in {total_elapsed:.1f}s[/green]")
        else:
            console.print(f"\n[red]Clean restart failed after {total_elapsed:.1f}s[/red]")
            console.print(f"[dim]Phase results: {phase_results}[/dim]")
            self._log_container_states()

        return success
