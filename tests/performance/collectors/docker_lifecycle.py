"""Docker container lifecycle management for performance testing."""

import subprocess
import time
from dataclasses import dataclass

from rich.console import Console

from ..config import CONTAINER_CONFIG, TestConfig

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

    def teardown_with_volumes(self) -> tuple[bool, float]:
        """Tear down all containers and remove volumes.

        Returns:
            Tuple of (success, elapsed_seconds).
        """
        cmd = self.get_compose_command() + ["down", "-v"]
        console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")

        start = time.time()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            elapsed = time.time() - start

            if result.returncode != 0:
                console.print(f"[red]Teardown failed after {elapsed:.1f}s[/red]")
                if result.stderr:
                    console.print(f"[red]stderr: {result.stderr[:500]}[/red]")
                return False, elapsed

            console.print(f"[green]Teardown complete in {elapsed:.1f}s[/green]")
            return True, elapsed

        except Exception as e:
            elapsed = time.time() - start
            console.print(f"[red]Teardown error after {elapsed:.1f}s: {e}[/red]")
            return False, elapsed

    def start_all_profiles(self) -> tuple[bool, float]:
        """Start all containers with all profiles.

        Docker compose will wait for depends_on health conditions to be satisfied
        before starting dependent containers, so this may take several minutes
        for slow-starting services like Airflow.

        Returns:
            Tuple of (success, elapsed_seconds).
        """
        cmd = self.get_compose_command() + ["up", "-d"]
        console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")

        start = time.time()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
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

    def _get_containers_for_profiles(self) -> list[str]:
        """Get all container names for the active profiles.

        Returns:
            List of container names from CONTAINER_CONFIG matching active profiles.
        """
        active_profiles = self.config.docker.profiles
        return [
            name
            for name, config in CONTAINER_CONFIG.items()
            if config["profile"] in active_profiles
        ]

    def _get_display_name(self, container_name: str) -> str:
        """Get display name for a container.

        Args:
            container_name: Full container name (e.g., rideshare-kafka).

        Returns:
            Display name from config or stripped container name.
        """
        config = CONTAINER_CONFIG.get(container_name)
        if config:
            return config["display_name"]
        # Fallback: strip 'rideshare-' prefix
        return container_name.replace("rideshare-", "").title()

    def wait_for_healthy(
        self,
        required_containers: list[str] | None = None,
        check_interval: float = 5.0,
    ) -> tuple[bool, float]:
        """Wait for all containers to be healthy.

        Args:
            required_containers: List of container names to wait for.
                               If None, uses ALL containers from active profiles.
            check_interval: Time between health checks.

        Returns:
            Tuple of (success, elapsed_seconds).
        """
        if required_containers is None:
            required_containers = self._get_containers_for_profiles()

        start_time = time.time()
        total_containers = len(required_containers)
        last_status_time = 0.0

        console.print(f"[cyan]Waiting for {total_containers} containers to be healthy...[/cyan]")

        while True:
            unhealthy_details: list[tuple[str, str]] = []  # (display_name, status)
            healthy_count = 0

            for container in required_containers:
                health = self.get_container_health(container)
                if health.healthy:
                    healthy_count += 1
                else:
                    display_name = self._get_display_name(container)
                    unhealthy_details.append((display_name, health.status))

            elapsed = time.time() - start_time

            if healthy_count == total_containers:
                console.print(
                    f"[green]All {total_containers} containers healthy "
                    f"in {elapsed:.1f}s[/green]"
                )
                return True, elapsed

            # Show progress every 15 seconds
            if elapsed - last_status_time >= 15.0:
                last_status_time = elapsed
                unhealthy_names = [f"{name} ({status})" for name, status in unhealthy_details[:5]]
                if len(unhealthy_details) > 5:
                    unhealthy_names.append(f"...and {len(unhealthy_details) - 5} more")
                console.print(
                    f"[yellow]Waiting... {elapsed:.0f}s | "
                    f"Healthy: {healthy_count}/{total_containers} | "
                    f"{', '.join(unhealthy_names)}[/yellow]"
                )

            time.sleep(check_interval)

    def _log_container_states(self) -> None:
        """Log the current state of all expected containers for diagnostics."""
        console.print("\n[yellow]Container diagnostics:[/yellow]")
        expected_containers = self._get_containers_for_profiles()
        for container in sorted(expected_containers):
            health = self.get_container_health(container)
            display_name = self._get_display_name(container)
            status_icon = "[green]✓[/green]" if health.healthy else "[red]✗[/red]"
            console.print(
                f"  {status_icon} {display_name} ({container}): "
                f"running={health.running}, status={health.status}"
            )

    def clean_restart(self) -> bool:
        """Perform a clean restart: teardown with volumes, start fresh.

        Steps:
        1. Teardown all containers and volumes
        2. Start all containers (docker compose waits for depends_on health)
        3. Verify all containers are healthy

        Returns:
            True if restart succeeded, False otherwise.
        """
        all_containers = self._get_containers_for_profiles()

        console.print("[bold cyan]Performing clean restart...[/bold cyan]")
        console.print(f"[dim]Containers to start: {len(all_containers)}[/dim]")

        overall_start = time.time()

        # Step 1: Teardown
        console.print("\n[bold]Step 1/3: Teardown[/bold]")
        success, _ = self.teardown_with_volumes()
        if not success:
            console.print("[red]Step 1 FAILED: Teardown did not complete[/red]")
            return False

        # Brief pause for resources to be released
        time.sleep(2.0)

        # Step 2: Start containers
        console.print("\n[bold]Step 2/3: Start containers[/bold]")
        console.print("[dim]Docker compose will wait for depends_on health conditions[/dim]")
        success, _ = self.start_all_profiles()
        if not success:
            console.print("[red]Step 2 FAILED: Container startup failed[/red]")
            self._log_container_states()
            return False

        # Step 3: Verify all containers are healthy
        console.print("\n[bold]Step 3/3: Verify all containers healthy[/bold]")
        success, _ = self.wait_for_healthy(required_containers=all_containers)
        if not success:
            console.print("[red]Step 3 FAILED: Not all containers healthy[/red]")
            return False

        total_elapsed = time.time() - overall_start
        console.print(
            f"\n[green]Clean restart completed in {total_elapsed:.1f}s "
            f"({total_elapsed/60:.1f} min)[/green]"
        )
        return True
