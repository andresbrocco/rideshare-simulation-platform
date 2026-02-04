#!/usr/bin/env python3
"""Dev test automation script for rideshare simulation platform.

Automates the development test workflow:
1. Docker compose down/up with DEV_MODE=true
2. Wait for services to be healthy
3. Start simulation and spawn agents
4. Enable all Airflow DAGs

Usage:
    ./venv/bin/python3 scripts/dev_test.py
    ./venv/bin/python3 scripts/dev_test.py --no-reset --skip-agents
    ./venv/bin/python3 scripts/dev_test.py --immediate-drivers 100 --delay 30
"""

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable

import requests


# ANSI color codes
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def log_info(msg: str) -> None:
    print(f"{Colors.CYAN}[INFO]{Colors.RESET} {msg}")


def log_success(msg: str) -> None:
    print(f"{Colors.GREEN}[OK]{Colors.RESET} {msg}")


def log_warning(msg: str) -> None:
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {msg}")


def log_error(msg: str) -> None:
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {msg}")


def log_step(msg: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}==> {msg}{Colors.RESET}")


@dataclass
class Config:
    """Configuration for dev test run."""

    no_reset: bool = False
    skip_agents: bool = False
    immediate_drivers: int = 50
    immediate_riders: int = 25
    scheduled_drivers: int = 50
    scheduled_riders: int = 475
    delay: int = 25
    trigger_silver: bool = False


# Service configuration
COMPOSE_FILE = "infrastructure/docker/compose.yml"
SIMULATION_URL = "http://localhost:8000"
AIRFLOW_URL = "http://localhost:8082"
SIMULATION_API_KEY = "dev-api-key-change-in-production"
AIRFLOW_USERNAME = "admin"
AIRFLOW_PASSWORD = "admin"

# Global state for Airflow JWT token
_airflow_jwt_token: str | None = None

DAGS_TO_ENABLE = [
    "dbt_silver_transformation",
    "dbt_gold_transformation",
    "dlq_monitoring",
    "delta_maintenance",
    "superset_dashboard_provisioning",
]


def run_command(
    cmd: list[str],
    check: bool = True,
    capture_output: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture_output,
        text=True,
        env=merged_env,
    )


def docker_compose_down() -> None:
    """Stop all docker compose services."""
    log_step("Stopping Docker services")
    run_command(
        [
            "docker",
            "compose",
            "-f",
            COMPOSE_FILE,
            "--profile",
            "core",
            "--profile",
            "data-pipeline",
            "--profile",
            "analytics",
            "down",
            "-v",
        ]
    )
    log_success("Docker services stopped")


def docker_compose_up() -> None:
    """Start docker compose services with DEV_MODE=true."""
    log_step("Starting Docker services with DEV_MODE=true")
    run_command(
        [
            "docker",
            "compose",
            "-f",
            COMPOSE_FILE,
            "--profile",
            "core",
            "--profile",
            "data-pipeline",
            "--profile",
            "analytics",
            "up",
            "-d",
        ],
        env={"DEV_MODE": "true"},
    )
    log_success("Docker services started")


def wait_for_service(
    name: str,
    check_fn: Callable[[], bool],
    max_retries: int = 60,
    retry_interval: int = 5,
) -> bool:
    """Wait for a service to become healthy."""
    log_info(f"Waiting for {name} to be ready...")

    for attempt in range(max_retries):
        try:
            if check_fn():
                log_success(f"{name} is ready")
                return True
        except Exception:
            pass

        if attempt < max_retries - 1:
            time.sleep(retry_interval)
            if (attempt + 1) % 6 == 0:  # Log every 30 seconds
                log_info(f"Still waiting for {name}... (attempt {attempt + 1}/{max_retries})")

    log_error(f"{name} did not become ready after {max_retries * retry_interval} seconds")
    return False


def check_simulation_health() -> bool:
    """Check if simulation service is healthy."""
    response = requests.get(f"{SIMULATION_URL}/health", timeout=5)
    return response.status_code == 200


def check_airflow_health() -> bool:
    """Check if Airflow is healthy."""
    # Health endpoint doesn't require auth
    response = requests.get(
        f"{AIRFLOW_URL}/api/v2/monitor/health",
        timeout=5,
    )
    return response.status_code == 200


def get_airflow_jwt_token() -> str | None:
    """Get JWT token from Airflow 3.x /auth/token endpoint.

    Returns:
        JWT access token, or None on failure
    """
    global _airflow_jwt_token
    if _airflow_jwt_token:
        return _airflow_jwt_token

    try:
        response = requests.post(
            f"{AIRFLOW_URL}/auth/token",
            json={"username": AIRFLOW_USERNAME, "password": AIRFLOW_PASSWORD},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if response.status_code in (200, 201):
            _airflow_jwt_token = response.json()["access_token"]
            return _airflow_jwt_token
        log_error(f"Failed to get Airflow JWT token: {response.status_code}")
        return None
    except requests.RequestException as e:
        log_error(f"Failed to get Airflow JWT token: {e}")
        return None


def airflow_api_headers() -> dict[str, str]:
    """Get headers for Airflow API requests with JWT auth."""
    token = get_airflow_jwt_token()
    if token:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
    return {"Content-Type": "application/json"}


def wait_for_all_services() -> bool:
    """Wait for all required services to be healthy."""
    log_step("Waiting for services to be healthy")

    if not wait_for_service("Simulation", check_simulation_health, max_retries=60):
        return False

    if not wait_for_service("Airflow", check_airflow_health, max_retries=120):
        return False

    return True


def start_simulation() -> bool:
    """Start the simulation."""
    log_step("Starting simulation")
    try:
        response = requests.post(
            f"{SIMULATION_URL}/simulation/start",
            headers={"X-API-Key": SIMULATION_API_KEY},
            json={},
            timeout=10,
        )
        if response.status_code in (200, 201):
            log_success("Simulation started")
            return True
        if response.status_code == 400 and "already running" in response.text.lower():
            log_success("Simulation already running")
            return True
        log_error(f"Failed to start simulation: {response.status_code} - {response.text}")
        return False
    except requests.RequestException as e:
        log_error(f"Failed to start simulation: {e}")
        return False


def spawn_agents(agent_type: str, mode: str, count: int) -> bool:
    """Spawn agents (drivers or riders)."""
    endpoint = "drivers" if agent_type == "driver" else "riders"
    url = f"{SIMULATION_URL}/agents/{endpoint}?mode={mode}"

    try:
        response = requests.post(
            url,
            headers={"X-API-Key": SIMULATION_API_KEY},
            json={"count": count},
            timeout=30,
        )
        if response.status_code in (200, 201):
            log_success(f"Spawned {count} {mode} {agent_type}s")
            return True
        log_error(f"Failed to spawn {agent_type}s: {response.status_code} - {response.text}")
        return False
    except requests.RequestException as e:
        log_error(f"Failed to spawn {agent_type}s: {e}")
        return False


def spawn_all_agents(config: Config) -> bool:
    """Spawn all configured agents."""
    log_step("Spawning agents")

    # Spawn immediate drivers first
    if config.immediate_drivers > 0:
        if not spawn_agents("driver", "immediate", config.immediate_drivers):
            return False

    # Wait before spawning riders
    if config.delay > 0 and (config.immediate_riders > 0 or config.scheduled_riders > 0):
        log_info(f"Waiting {config.delay}s before spawning riders...")
        time.sleep(config.delay)

    # Spawn immediate riders
    if config.immediate_riders > 0:
        if not spawn_agents("rider", "immediate", config.immediate_riders):
            return False

    # Spawn scheduled agents
    if config.scheduled_drivers > 0:
        if not spawn_agents("driver", "scheduled", config.scheduled_drivers):
            return False

    if config.scheduled_riders > 0:
        if not spawn_agents("rider", "scheduled", config.scheduled_riders):
            return False

    return True


def enable_dag(dag_id: str) -> bool:
    """Enable (unpause) a specific DAG."""
    try:
        response = requests.patch(
            f"{AIRFLOW_URL}/api/v2/dags/{dag_id}",
            json={"is_paused": False},
            headers=airflow_api_headers(),
            timeout=10,
        )
        if response.status_code == 200:
            return True
        log_warning(f"Failed to enable DAG {dag_id}: {response.status_code}")
        return False
    except requests.RequestException as e:
        log_warning(f"Failed to enable DAG {dag_id}: {e}")
        return False


def wait_for_dags_available(max_retries: int = 60, retry_interval: int = 5) -> bool:
    """Wait for Airflow scheduler to parse DAGs."""
    log_info("Waiting for Airflow DAGs to be parsed...")

    for attempt in range(max_retries):
        try:
            response = requests.get(
                f"{AIRFLOW_URL}/api/v2/dags",
                headers=airflow_api_headers(),
                timeout=10,
            )
            if response.status_code == 200:
                dags = response.json().get("dags", [])
                dag_ids = {d["dag_id"] for d in dags}
                missing = [d for d in DAGS_TO_ENABLE if d not in dag_ids]
                if not missing:
                    log_success("All DAGs are available")
                    return True
                if attempt > 0 and (attempt + 1) % 6 == 0:
                    log_info(f"Still waiting for DAGs: {missing}")
        except requests.RequestException:
            pass

        if attempt < max_retries - 1:
            time.sleep(retry_interval)

    log_warning("Not all DAGs became available, will try to enable what's there")
    return False


def enable_all_dags() -> bool:
    """Enable all configured DAGs."""
    log_step("Enabling Airflow DAGs")

    # Get JWT token first
    token = get_airflow_jwt_token()
    if not token:
        log_error("Could not obtain Airflow JWT token")
        return False

    # Wait for DAGs to be parsed by scheduler
    wait_for_dags_available(max_retries=60, retry_interval=5)

    success_count = 0
    for dag_id in DAGS_TO_ENABLE:
        if enable_dag(dag_id):
            log_success(f"Enabled DAG: {dag_id}")
            success_count += 1
        else:
            log_warning(f"Could not enable DAG: {dag_id}")

    if success_count == len(DAGS_TO_ENABLE):
        return True
    elif success_count > 0:
        log_warning(f"Enabled {success_count}/{len(DAGS_TO_ENABLE)} DAGs")
        return True
    return False


def trigger_dag(dag_id: str) -> bool:
    """Manually trigger a DAG run."""
    from datetime import datetime, timezone

    try:
        payload = {
            "logical_date": datetime.now(timezone.utc).isoformat(),
            "conf": {},
        }
        response = requests.post(
            f"{AIRFLOW_URL}/api/v2/dags/{dag_id}/dagRuns",
            json=payload,
            headers=airflow_api_headers(),
            timeout=10,
        )
        if response.status_code in (200, 201):
            log_success(f"Triggered DAG: {dag_id}")
            return True
        log_error(f"Failed to trigger DAG {dag_id}: {response.status_code}")
        return False
    except requests.RequestException as e:
        log_error(f"Failed to trigger DAG {dag_id}: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dev test automation for rideshare simulation platform"
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Skip docker compose down/up",
    )
    parser.add_argument(
        "--skip-agents",
        action="store_true",
        help="Only start simulation, don't spawn agents",
    )
    parser.add_argument(
        "--immediate-drivers",
        type=int,
        default=50,
        help="Number of immediate drivers (default: 50)",
    )
    parser.add_argument(
        "--immediate-riders",
        type=int,
        default=25,
        help="Number of immediate riders (default: 25)",
    )
    parser.add_argument(
        "--scheduled-drivers",
        type=int,
        default=50,
        help="Number of scheduled drivers (default: 50)",
    )
    parser.add_argument(
        "--scheduled-riders",
        type=int,
        default=475,
        help="Number of scheduled riders (default: 475)",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=25,
        help="Seconds between spawning drivers and riders (default: 25)",
    )
    parser.add_argument(
        "--trigger-silver",
        action="store_true",
        help="Manually trigger Silver DAG immediately",
    )

    args = parser.parse_args()

    config = Config(
        no_reset=args.no_reset,
        skip_agents=args.skip_agents,
        immediate_drivers=args.immediate_drivers,
        immediate_riders=args.immediate_riders,
        scheduled_drivers=args.scheduled_drivers,
        scheduled_riders=args.scheduled_riders,
        delay=args.delay,
        trigger_silver=args.trigger_silver,
    )

    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}  Rideshare Simulation Dev Test Automation{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")

    # Step 1: Docker compose down/up
    if not config.no_reset:
        try:
            docker_compose_down()
            docker_compose_up()
        except subprocess.CalledProcessError as e:
            log_error(f"Docker compose failed: {e}")
            return 1
    else:
        log_info("Skipping docker reset (--no-reset)")

    # Step 2: Wait for services
    if not wait_for_all_services():
        log_error("Services did not become healthy")
        return 1

    # Step 3: Start simulation
    if not start_simulation():
        return 1

    # Step 4: Spawn agents
    if not config.skip_agents:
        if not spawn_all_agents(config):
            return 1
    else:
        log_info("Skipping agent spawning (--skip-agents)")

    # Step 5: Enable DAGs
    if not enable_all_dags():
        log_warning("Some DAGs could not be enabled")

    # Step 6: Optional - trigger Silver DAG
    if config.trigger_silver:
        log_step("Triggering Silver DAG manually")
        trigger_dag("dbt_silver_transformation")

    # Summary
    print(f"\n{Colors.BOLD}{Colors.GREEN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}  Dev test environment ready!{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}{'=' * 60}{Colors.RESET}")
    print(f"\n{Colors.CYAN}Services:{Colors.RESET}")
    print("  - Frontend:   http://localhost:5173")
    print("  - Simulation: http://localhost:8000/docs")
    print("  - Airflow:    http://localhost:8082 (admin/admin)")
    print("  - Superset:   http://localhost:8088 (admin/admin)")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
