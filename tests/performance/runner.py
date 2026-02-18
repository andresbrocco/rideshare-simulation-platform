#!/usr/bin/env python3
"""Performance testing CLI runner.

Usage:
    ./venv/bin/python -m tests.performance run              # Full 4-scenario pipeline
    ./venv/bin/python -m tests.performance run -s baseline   # Only baseline
    ./venv/bin/python -m tests.performance run -s stress -s speed  # Stress + speed
    ./venv/bin/python -m tests.performance run -s duration --agents 50 --speed 4
    ./venv/bin/python -m tests.performance check            # Service status
    ./venv/bin/python -m tests.performance analyze <file>   # Re-analyze
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from .analysis.findings import (
    ContainerHealth,
    Finding,
    FindingCategory,
    OverallStatus,
    Severity,
    TestVerdict,
)
from .analysis.report_generator import ReportGenerator
from .analysis.statistics import calculate_all_container_stats, summarize_scenario_stats
from .analysis.visualizations import ChartGenerator
from .collectors.docker_lifecycle import DockerLifecycleManager
from .collectors.docker_stats import DockerStatsCollector
from .collectors.oom_detector import OOMDetector
from .collectors.simulation_api import SimulationAPIClient
from .config import CONTAINER_CONFIG, TestConfig
from .scenarios.base import BaseScenario, ScenarioResult
from .scenarios.baseline import BaselineScenario
from .scenarios.duration_leak import DurationLeakScenario
from .scenarios.speed_scaling import SpeedScalingScenario
from .scenarios.stress_test import StressTestScenario

console = Console()

SCENARIO_REGISTRY: dict[str, type[BaseScenario]] = {
    "baseline": BaselineScenario,
    "stress": StressTestScenario,
    "speed": SpeedScalingScenario,
    "duration": DurationLeakScenario,
}
VALID_SCENARIO_NAMES: tuple[str, ...] = tuple(SCENARIO_REGISTRY.keys())
_FULL_PIPELINE_ORDER: tuple[str, ...] = ("baseline", "stress", "speed", "duration")
_REUSES_PREVIOUS_STATE: frozenset[str] = frozenset({"stress"})


def create_test_config() -> TestConfig:
    """Create test configuration."""
    return TestConfig()


def create_collectors(config: TestConfig) -> tuple[
    DockerLifecycleManager,
    DockerStatsCollector,
    SimulationAPIClient,
    OOMDetector,
]:
    """Create all collector instances."""
    lifecycle = DockerLifecycleManager(config)
    stats_collector = DockerStatsCollector(config)
    api_client = SimulationAPIClient(config)
    oom_detector = OOMDetector()
    return lifecycle, stats_collector, api_client, oom_detector


def run_scenario(
    scenario_class: type[BaseScenario],
    config: TestConfig,
    lifecycle: DockerLifecycleManager,
    stats_collector: DockerStatsCollector,
    api_client: SimulationAPIClient,
    oom_detector: OOMDetector,
    **kwargs: Any,
) -> ScenarioResult:
    """Run a single scenario."""
    scenario = scenario_class(
        config=config,
        lifecycle=lifecycle,
        stats_collector=stats_collector,
        api_client=api_client,
        oom_detector=oom_detector,
        **kwargs,
    )
    return scenario.run()


def save_results(results: dict[str, Any], output_dir: Path) -> Path:
    """Save results to JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    results_file = output_dir / "results.json"

    with open(results_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    return results_file


def analyze_results(
    results: dict[str, Any], config: TestConfig
) -> tuple[dict[str, Any], TestVerdict]:
    """Analyze results and generate findings.

    Args:
        results: Full test results dictionary.
        config: Test configuration with thresholds.

    Returns:
        Tuple of (analysis dict, TestVerdict).
    """
    scenarios = results.get("scenarios", [])

    analysis: dict[str, Any] = {}

    # Per-scenario summaries (includes all containers)
    scenario_summaries: list[dict[str, Any]] = []
    for scenario in scenarios:
        samples = scenario.get("samples", [])
        summary = summarize_scenario_stats(samples, None)
        summary["scenario_name"] = scenario["scenario_name"]
        scenario_summaries.append(summary)

    analysis["scenario_summaries"] = scenario_summaries

    # Generate findings and verdict
    findings = _generate_findings(results, config)
    container_health = _generate_container_health(results, config)
    verdict = _calculate_verdict(results, findings, container_health)

    return analysis, verdict


def _generate_findings(results: dict[str, Any], config: TestConfig) -> list[Finding]:
    """Generate findings from test results.

    Checks for:
    - Memory leaks (sustained increase over time)
    - High memory usage (% of limit)
    - High CPU usage
    - OOM events
    - Reset failures (memory not returning to baseline)

    Args:
        results: Full test results dictionary.
        config: Test configuration with thresholds.

    Returns:
        List of findings.
    """
    findings: list[Finding] = []
    thresholds = config.analysis.thresholds
    scenarios = results.get("scenarios", [])

    for scenario in scenarios:
        scenario_name = scenario.get("scenario_name", "unknown")
        samples = scenario.get("samples", [])

        if not samples:
            continue

        # Check for OOM events (stress test OOM is an expected stop condition)
        if scenario_name != "stress_test":
            oom_events = scenario.get("oom_events", [])
            for oom in oom_events:
                container = oom.get("container", "unknown")
                findings.append(
                    Finding(
                        severity=Severity.CRITICAL,
                        category=FindingCategory.OOM_EVENT,
                        container=container,
                        message=f"OOM event detected in {container}",
                        metric_value=0,
                        threshold=0,
                        scenario_name=scenario_name,
                        recommendation="Increase memory limit or optimize memory usage",
                    )
                )

        # Calculate stats for all containers
        all_stats = calculate_all_container_stats(samples)

        for container, stats in all_stats.items():
            display_name = CONTAINER_CONFIG.get(container, {}).get("display_name", container)

            # Check memory usage thresholds
            mem_critical = thresholds.get_memory_critical_percent(container)
            mem_warning = thresholds.get_memory_warning_percent(container)

            if stats.memory_max > 0:
                # Calculate memory percent if we have limit info
                # Use the last sample's limit
                last_sample = samples[-1] if samples else {}
                container_data = last_sample.get("containers", {}).get(container, {})
                mem_limit = container_data.get("memory_limit_mb", 0)

                if mem_limit > 0:
                    mem_percent = (stats.memory_max / mem_limit) * 100

                    if mem_percent >= mem_critical:
                        findings.append(
                            Finding(
                                severity=Severity.CRITICAL,
                                category=FindingCategory.HIGH_MEMORY_USAGE,
                                container=container,
                                message=f"{display_name} memory at {mem_percent:.1f}% of limit",
                                metric_value=mem_percent,
                                threshold=mem_critical,
                                scenario_name=scenario_name,
                                recommendation="Increase memory limit or investigate memory usage",
                            )
                        )
                    elif mem_percent >= mem_warning:
                        findings.append(
                            Finding(
                                severity=Severity.WARNING,
                                category=FindingCategory.HIGH_MEMORY_USAGE,
                                container=container,
                                message=f"{display_name} memory at {mem_percent:.1f}% of limit",
                                metric_value=mem_percent,
                                threshold=mem_warning,
                                scenario_name=scenario_name,
                            )
                        )

            # Check CPU usage thresholds
            cpu_critical = thresholds.get_cpu_critical_percent(container)
            cpu_warning = thresholds.get_cpu_warning_percent(container)

            if stats.cpu_max >= cpu_critical:
                findings.append(
                    Finding(
                        severity=Severity.CRITICAL,
                        category=FindingCategory.HIGH_CPU_USAGE,
                        container=container,
                        message=f"{display_name} CPU peaked at {stats.cpu_max:.1f}%",
                        metric_value=stats.cpu_max,
                        threshold=cpu_critical,
                        scenario_name=scenario_name,
                        recommendation="Investigate CPU hotspots or increase CPU allocation",
                    )
                )
            elif stats.cpu_max >= cpu_warning:
                findings.append(
                    Finding(
                        severity=Severity.WARNING,
                        category=FindingCategory.HIGH_CPU_USAGE,
                        container=container,
                        message=f"{display_name} CPU peaked at {stats.cpu_max:.1f}%",
                        metric_value=stats.cpu_max,
                        threshold=cpu_warning,
                        scenario_name=scenario_name,
                    )
                )

        # Check for memory leaks in duration tests
        if scenario_name == "duration_leak" or scenario_name.startswith("duration_leak_"):
            # Calculate leak rate from first to last sample
            if len(samples) >= 2:
                first_ts = samples[0].get("timestamp", 0)
                last_ts = samples[-1].get("timestamp", 0)
                duration_min = (last_ts - first_ts) / 60

                if duration_min > 0:
                    for container in all_stats:
                        first_container = samples[0].get("containers", {}).get(container, {})
                        last_container = samples[-1].get("containers", {}).get(container, {})

                        first_mem = first_container.get("memory_used_mb", 0)
                        last_mem = last_container.get("memory_used_mb", 0)

                        if first_mem > 0 and last_mem > 0:
                            leak_rate = (last_mem - first_mem) / duration_min
                            leak_threshold = thresholds.get_memory_leak_threshold(container)

                            if leak_rate >= leak_threshold:
                                display_name = CONTAINER_CONFIG.get(container, {}).get(
                                    "display_name", container
                                )
                                findings.append(
                                    Finding(
                                        severity=Severity.WARNING,
                                        category=FindingCategory.MEMORY_LEAK,
                                        container=container,
                                        message=f"{display_name} memory growing at {leak_rate:.2f} MB/min",
                                        metric_value=leak_rate,
                                        threshold=leak_threshold,
                                        scenario_name=scenario_name,
                                        recommendation="Profile memory allocation and check for leaks",
                                    )
                                )

    return findings


def _generate_container_health(
    results: dict[str, Any], config: TestConfig
) -> list[ContainerHealth]:
    """Generate container health summary from latest scenario samples.

    Args:
        results: Full test results dictionary.
        config: Test configuration with thresholds.

    Returns:
        List of container health summaries.
    """
    health_list: list[ContainerHealth] = []
    thresholds = config.analysis.thresholds
    scenarios = results.get("scenarios", [])

    if not scenarios:
        return health_list

    # Use the last scenario's samples for current state
    last_scenario = scenarios[-1]
    samples = last_scenario.get("samples", [])

    if not samples:
        return health_list

    last_sample = samples[-1]
    containers = last_sample.get("containers", {})

    # Calculate stats for leak rate estimation
    all_stats = calculate_all_container_stats(samples)

    # Calculate leak rates if we have duration
    leak_rates: dict[str, float | None] = {}
    if len(samples) >= 2:
        first_ts = samples[0].get("timestamp", 0)
        last_ts = samples[-1].get("timestamp", 0)
        duration_min = (last_ts - first_ts) / 60

        if duration_min > 0:
            for container in containers:
                first_container = samples[0].get("containers", {}).get(container, {})
                last_container = containers.get(container, {})

                first_mem = first_container.get("memory_used_mb", 0)
                last_mem = last_container.get("memory_used_mb", 0)

                if first_mem > 0 and last_mem > 0:
                    leak_rates[container] = (last_mem - first_mem) / duration_min
                else:
                    leak_rates[container] = None
        else:
            for container in containers:
                leak_rates[container] = None
    else:
        for container in containers:
            leak_rates[container] = None

    for container, data in containers.items():
        display_name = CONTAINER_CONFIG.get(container, {}).get("display_name", container)

        mem_current = data.get("memory_used_mb", 0)
        mem_limit = data.get("memory_limit_mb", 0)
        mem_percent = data.get("memory_percent", 0)
        cpu_current = data.get("cpu_percent", 0)

        # Get peak CPU from stats
        stats = all_stats.get(container)
        cpu_peak = stats.cpu_max if stats else cpu_current

        # Determine status
        mem_critical = thresholds.get_memory_critical_percent(container)
        mem_warning = thresholds.get_memory_warning_percent(container)
        cpu_critical = thresholds.get_cpu_critical_percent(container)
        cpu_warning = thresholds.get_cpu_warning_percent(container)

        if mem_percent >= mem_critical or cpu_peak >= cpu_critical:
            status = "critical"
        elif mem_percent >= mem_warning or cpu_peak >= cpu_warning:
            status = "warning"
        else:
            status = "healthy"

        health_list.append(
            ContainerHealth(
                container_name=container,
                display_name=display_name,
                memory_current_mb=mem_current,
                memory_limit_mb=mem_limit,
                memory_percent=mem_percent,
                memory_leak_rate_mb_per_min=leak_rates.get(container),
                cpu_current_percent=cpu_current,
                cpu_peak_percent=cpu_peak,
                status=status,
            )
        )

    # Sort by priority containers first, then alphabetically
    priority = config.analysis.priority_containers
    health_list.sort(
        key=lambda h: (
            priority.index(h.container_name) if h.container_name in priority else 999,
            h.container_name,
        )
    )

    return health_list


def _calculate_verdict(
    results: dict[str, Any],
    findings: list[Finding],
    container_health: list[ContainerHealth],
) -> TestVerdict:
    """Calculate overall test verdict from findings.

    Args:
        results: Full test results dictionary.
        findings: List of findings.
        container_health: List of container health summaries.

    Returns:
        TestVerdict with overall status and recommendations.
    """
    scenarios = results.get("scenarios", [])

    # Stress test OOM/abort is an expected stop condition, not a failure.
    # Exclude it from pass/fail and OOM tallies.
    non_stress = [s for s in scenarios if s.get("scenario_name") != "stress_test"]

    # Count scenarios (stress excluded — its abort is by design)
    scenarios_passed = sum(1 for s in non_stress if not s.get("aborted", False))
    scenarios_failed = len(non_stress) - scenarios_passed

    # Count OOM events (stress excluded — OOM is a valid stop condition)
    total_oom = sum(len(s.get("oom_events", [])) for s in non_stress)

    # Determine overall status
    critical_count = sum(1 for f in findings if f.severity == Severity.CRITICAL)
    warning_count = sum(1 for f in findings if f.severity == Severity.WARNING)

    if critical_count > 0 or total_oom > 0:
        overall_status = OverallStatus.FAIL
    elif warning_count > 0:
        overall_status = OverallStatus.WARNING
    else:
        overall_status = OverallStatus.PASS

    # Generate recommendations from findings
    recommendations: list[str] = []
    seen_recommendations: set[str] = set()

    for finding in findings:
        if finding.recommendation and finding.recommendation not in seen_recommendations:
            recommendations.append(finding.recommendation)
            seen_recommendations.add(finding.recommendation)

    # Add general recommendations based on patterns
    if total_oom > 0:
        rec = "Review memory limits - OOM events detected during testing"
        if rec not in seen_recommendations:
            recommendations.append(rec)

    if any(f.category == FindingCategory.MEMORY_LEAK for f in findings):
        rec = "Run profiling to identify memory leak sources"
        if rec not in seen_recommendations:
            recommendations.append(rec)

    return TestVerdict(
        overall_status=overall_status,
        findings=findings,
        recommendations=recommendations,
        container_health=container_health,
        scenarios_passed=scenarios_passed,
        scenarios_failed=scenarios_failed,
        total_oom_events=total_oom,
    )


@click.group()
def cli() -> None:
    """Performance testing framework for rideshare simulation platform."""
    pass


@cli.command()
@click.option(
    "--scenario",
    "-s",
    "scenarios",
    type=click.Choice(VALID_SCENARIO_NAMES, case_sensitive=False),
    multiple=True,
    help="Scenario(s) to run. Omit for full pipeline. Repeatable.",
)
@click.option(
    "--agents",
    "-a",
    type=click.IntRange(min=2),
    default=None,
    help="Manual agent count for speed/duration (skips stress derivation).",
)
@click.option(
    "--speed",
    "-x",
    "speed_multiplier",
    type=click.IntRange(min=1),
    default=None,
    help="Manual speed multiplier for duration (default: 1 when not derived).",
)
@click.option(
    "--baseline-seconds",
    type=click.IntRange(min=5),
    default=None,
    help="Override baseline_duration_seconds.",
)
@click.option(
    "--duration-minutes",
    type=click.IntRange(min=1),
    default=None,
    help="Override duration_active_minutes.",
)
@click.option(
    "--cooldown-minutes",
    type=click.IntRange(min=1),
    default=None,
    help="Override duration_cooldown_minutes.",
)
@click.option(
    "--stress-max-minutes",
    type=click.IntRange(min=1),
    default=None,
    help="Override stress_max_duration_minutes.",
)
@click.option(
    "--speed-step-minutes",
    type=click.IntRange(min=1),
    default=None,
    help="Override speed_scaling_step_duration_minutes.",
)
@click.option(
    "--speed-max-multiplier",
    type=click.IntRange(min=2),
    default=None,
    help="Override speed_scaling_max_multiplier.",
)
def run(
    scenarios: tuple[str, ...],
    agents: int | None,
    speed_multiplier: int | None,
    baseline_seconds: int | None,
    duration_minutes: int | None,
    cooldown_minutes: int | None,
    stress_max_minutes: int | None,
    speed_step_minutes: int | None,
    speed_max_multiplier: int | None,
) -> None:
    """Run performance test scenarios.

    \b
    With no flags the full pipeline runs in order:
      1. Baseline  - idle resource usage
      2. Stress    - find max sustainable agent count
      3. Speed     - double speed multiplier each step
      4. Duration  - 3-phase lifecycle at proven speed
    The stress result derives agent_count for speed/duration, and the
    speed result derives speed_multiplier for duration.

    \b
    Select individual scenarios with -s (repeatable). Order is always
    canonical (baseline -> stress -> speed -> duration) regardless of
    flag order. When speed or duration are selected without stress,
    --agents is required.

    \b
    Examples:
      # Full pipeline (default)
      run

    \b
      # Only baseline, 10-second measurement
      run -s baseline --baseline-seconds 10

    \b
      # Stress test with 15-minute cap
      run -s stress --stress-max-minutes 15

    \b
      # Speed scaling with manual agent count
      run -s speed --agents 50

    \b
      # Duration test with explicit parameters
      run -s duration --agents 50 --speed 4 --duration-minutes 10

    \b
      # Stress + speed (agents derived from stress)
      run -s stress -s speed
    """
    # Determine which scenarios to run in canonical order
    if scenarios:
        selected = set(scenarios)
    else:
        selected = set(_FULL_PIPELINE_ORDER)

    # Validate: agent count must be even (split equally between drivers and riders)
    if agents is not None and agents % 2 != 0:
        raise click.UsageError(
            f"--agents must be even (split equally between drivers and riders), got {agents}"
        )

    # Validate: speed/duration without stress require --agents
    needs_agents = selected & {"speed", "duration"}
    has_stress = "stress" in selected
    if needs_agents and not has_stress and agents is None:
        names = " and ".join(sorted(needs_agents))
        raise click.UsageError(
            f"--agents is required when running {names} without stress.\n"
            f"  Example: run -s {sorted(needs_agents)[0]} --agents 50"
        )

    # Build ordered list of scenarios to run
    ordered = [s for s in _FULL_PIPELINE_ORDER if s in selected]
    total_steps = len(ordered)

    config = create_test_config()

    # Apply config overrides
    if baseline_seconds is not None:
        config.scenarios.baseline_duration_seconds = baseline_seconds
    if duration_minutes is not None:
        config.scenarios.duration_active_minutes = duration_minutes
    if cooldown_minutes is not None:
        config.scenarios.duration_cooldown_minutes = cooldown_minutes
    if stress_max_minutes is not None:
        config.scenarios.stress_max_duration_minutes = stress_max_minutes
    if speed_step_minutes is not None:
        config.scenarios.speed_scaling_step_duration_minutes = speed_step_minutes
    if speed_max_multiplier is not None:
        config.scenarios.speed_scaling_max_multiplier = speed_max_multiplier

    lifecycle, stats_collector, api_client, oom_detector = create_collectors(config)

    # Create output directory
    test_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = config.output_dir / test_id
    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Test ID: {test_id}[/bold]")
    console.print(f"Output directory: {output_dir}")
    console.print(f"Scenarios: {', '.join(ordered)}\n")

    # Initialize results
    results: dict[str, Any] = {
        "test_id": test_id,
        "started_at": datetime.now().isoformat(),
        "config": {
            "api": {"base_url": config.api.base_url},
            "docker": {
                "compose_file": config.docker.compose_file,
                "profiles": config.docker.profiles,
            },
            "sampling": {
                "interval_seconds": config.sampling.interval_seconds,
                "warmup_seconds": config.sampling.warmup_seconds,
            },
            "scenarios": {
                "duration_active_minutes": config.scenarios.duration_active_minutes,
                "duration_cooldown_minutes": config.scenarios.duration_cooldown_minutes,
                "duration_drain_timeout_seconds": config.scenarios.duration_drain_timeout_seconds,
                "stress_cpu_threshold_percent": config.scenarios.stress_cpu_threshold_percent,
                "stress_memory_threshold_percent": config.scenarios.stress_memory_threshold_percent,
                "speed_scaling_step_duration_minutes": config.scenarios.speed_scaling_step_duration_minutes,
                "speed_scaling_max_multiplier": config.scenarios.speed_scaling_max_multiplier,
            },
        },
        "scenarios": [],
    }

    scenario_results: list[dict[str, Any]] = []
    aborted = False
    abort_reason = None

    # Mutable state derived across scenarios
    agent_count: int | None = agents
    derived_speed: int | None = speed_multiplier

    try:
        # Pre-flight: scenarios that skip clean_restart expect a predecessor
        # to have left Docker running. When they're first, we must ensure it.
        if ordered[0] in _REUSES_PREVIOUS_STATE and not api_client.is_available():
            console.print(
                "[cyan]Starting Docker environment "
                f"({ordered[0]} reuses previous state but none exists)...[/cyan]"
            )
            if not lifecycle.clean_restart():
                console.print("[red]Failed to start Docker environment[/red]")
                aborted = True
                abort_reason = "docker_setup_failed"

        if not aborted:
            for step_idx, scenario_name in enumerate(ordered, 1):
                step_label = f"Step {step_idx}/{total_steps}"

                if scenario_name == "baseline":
                    console.rule(f"[bold cyan]{step_label}: Running Baseline Scenario[/bold cyan]")
                    baseline_result = run_scenario(
                        BaselineScenario,
                        config,
                        lifecycle,
                        stats_collector,
                        api_client,
                        oom_detector,
                    )
                    scenario_results.append(_result_to_dict(baseline_result))

                elif scenario_name == "stress":
                    console.rule(
                        f"[bold cyan]{step_label}: Running Stress Test "
                        f"(until {config.scenarios.stress_cpu_threshold_percent}% CPU "
                        f"or {config.scenarios.stress_memory_threshold_percent}% memory)"
                        f"[/bold cyan]"
                    )
                    stress_result = run_scenario(
                        StressTestScenario,
                        config,
                        lifecycle,
                        stats_collector,
                        api_client,
                        oom_detector,
                    )
                    scenario_results.append(_result_to_dict(stress_result))

                    # Derive agent count from stress result (unless manually overridden)
                    if agent_count is None:
                        stress_metadata = stress_result.metadata
                        if stress_result.aborted:
                            console.print(
                                "[red]Stress test aborted (likely OOM). "
                                "Cannot derive agent count.[/red]"
                            )
                            aborted = True
                            abort_reason = "stress_test_oom"
                            break
                        total_agents_queued = stress_metadata.get("total_agents_queued", 0)
                        if total_agents_queued < 4:
                            console.print(
                                "[red]Stress test did not queue enough agents. "
                                "Cannot derive agent count.[/red]"
                            )
                            aborted = True
                            abort_reason = "stress_test_insufficient_agents"
                            break
                        agent_count = total_agents_queued // 2
                        # Round down to nearest even number
                        agent_count -= agent_count % 2
                        console.print(
                            f"\n[cyan]Derived agent count: {agent_count} "
                            f"(half of {total_agents_queued} total from stress test)[/cyan]\n"
                        )
                        results.setdefault("derived_config", {}).update(
                            {
                                "duration_agent_count": agent_count,
                                "total_agents_queued": total_agents_queued,
                            }
                        )
                    else:
                        if selected & {"speed", "duration"}:
                            console.print(
                                f"\n[cyan]Using manual override: --agents {agent_count}[/cyan]\n"
                            )

                elif scenario_name == "speed":
                    console.rule(
                        f"[bold cyan]{step_label}: Running Speed Scaling Test "
                        f"(2x-{config.scenarios.speed_scaling_max_multiplier}x, "
                        f"{config.scenarios.speed_scaling_step_duration_minutes}m/step, "
                        f"base agents={agent_count})[/bold cyan]"
                    )
                    speed_result = run_scenario(
                        SpeedScalingScenario,
                        config,
                        lifecycle,
                        stats_collector,
                        api_client,
                        oom_detector,
                        agent_count=agent_count,
                    )
                    scenario_results.append(_result_to_dict(speed_result))

                    # Derive speed from speed scaling result (unless manually overridden)
                    if derived_speed is None:
                        max_reliable_speed = _derive_max_reliable_speed(speed_result)
                        derived_speed = max_reliable_speed
                        console.print(
                            f"\n[cyan]With {agent_count} agents, the simulation "
                            f"ran reliably up to {max_reliable_speed}x speed[/cyan]\n"
                        )
                        results.setdefault("derived_config", {})[
                            "duration_speed_multiplier"
                        ] = max_reliable_speed
                    else:
                        if "duration" in selected:
                            console.print(
                                f"\n[cyan]Using manual override: --speed {derived_speed}[/cyan]\n"
                            )

                elif scenario_name == "duration":
                    effective_speed = derived_speed if derived_speed is not None else 1
                    active_min = config.scenarios.duration_active_minutes
                    cooldown_min = config.scenarios.duration_cooldown_minutes
                    speed_label = f", {effective_speed}x speed" if effective_speed > 1 else ""
                    console.rule(
                        f"[bold cyan]{step_label}: Running Duration Test "
                        f"({active_min}m+drain+{cooldown_min}m, "
                        f"{agent_count} agents{speed_label})[/bold cyan]"
                    )
                    duration_result = run_scenario(
                        DurationLeakScenario,
                        config,
                        lifecycle,
                        stats_collector,
                        api_client,
                        oom_detector,
                        agent_count=agent_count,
                        speed_multiplier=effective_speed,
                    )
                    scenario_results.append(_result_to_dict(duration_result))

    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
        aborted = True
        abort_reason = "user_interrupt"

    # Finalize results
    results["scenarios"] = scenario_results
    results["completed_at"] = datetime.now().isoformat()
    if aborted:
        results["aborted"] = True
        results["abort_reason"] = abort_reason

    # Analyze
    console.print("\n[bold]Analyzing results...[/bold]")
    analysis, verdict = analyze_results(results, config)
    results["analysis"] = analysis

    # Save results
    results_file = save_results(results, output_dir)
    console.print(f"[green]Results saved to: {results_file}[/green]")

    # Generate charts (organized by scenario)
    console.print("\n[bold]Generating charts...[/bold]")
    chart_gen = ChartGenerator(output_dir)
    chart_paths = chart_gen.generate_charts_by_scenario(results)
    total_charts = sum(len(paths) for paths in chart_paths.values())
    console.print(f"[green]Generated {total_charts} charts in subdirectories[/green]")

    # Generate reports
    console.print("\n[bold]Generating reports...[/bold]")
    report_gen = ReportGenerator(output_dir, output_dir / "charts")
    report_paths = report_gen.generate_all(results, verdict)
    console.print(
        f"[green]Generated reports: {report_paths.markdown.name}, {report_paths.html.name}[/green]"
    )

    # Summary
    _print_summary(results, verdict)

    # Teardown Docker environment
    console.print("\n[bold]Tearing down Docker environment...[/bold]")
    success, _ = lifecycle.teardown_with_volumes()
    if not success:
        console.print("[yellow]Warning: Teardown may have failed, check Docker manually[/yellow]")


@cli.command()
def check() -> None:
    """Check status of required services."""
    config = create_test_config()
    lifecycle, stats_collector, api_client, _ = create_collectors(config)

    table = Table(title="Service Status")
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details")

    # Check cAdvisor
    if stats_collector.is_available():
        table.add_row("cAdvisor", "✓ Available", config.docker.cadvisor_url)
    else:
        table.add_row("cAdvisor", "[red]✗ Unavailable[/red]", config.docker.cadvisor_url)

    # Check Simulation API
    if api_client.is_available():
        status = api_client.get_simulation_status()
        table.add_row(
            "Simulation API",
            "✓ Available",
            f"State: {status.state}, Drivers: {status.drivers_total}, Riders: {status.riders_total}",
        )
    else:
        table.add_row("Simulation API", "[red]✗ Unavailable[/red]", config.api.base_url)

    # Check container status
    console.print(table)
    console.print()

    # Container details
    stats = stats_collector.get_all_container_stats()
    if stats:
        container_table = Table(title="Container Metrics")
        container_table.add_column("Container")
        container_table.add_column("Memory (MB)", justify="right")
        container_table.add_column("Limit (MB)", justify="right")
        container_table.add_column("Usage %", justify="right")
        container_table.add_column("CPU %", justify="right")

        for name, sample in sorted(stats.items()):
            display_name = CONTAINER_CONFIG.get(name, {}).get("display_name", name)
            container_table.add_row(
                display_name,
                f"{sample.memory_used_mb:.1f}",
                f"{sample.memory_limit_mb:.1f}" if sample.memory_limit_mb > 0 else "N/A",
                f"{sample.memory_percent:.1f}%" if sample.memory_percent > 0 else "N/A",
                f"{sample.cpu_percent:.1f}%",
            )

        console.print(container_table)
    else:
        console.print("[yellow]No container metrics available[/yellow]")


@cli.command()
@click.argument("results_file", type=click.Path(exists=True))
def analyze(results_file: str) -> None:
    """Re-analyze existing results and regenerate charts."""
    config = create_test_config()

    with open(results_file) as f:
        results = json.load(f)

    output_dir = Path(results_file).parent

    console.print(f"[bold]Re-analyzing: {results_file}[/bold]")

    # Re-run analysis
    analysis, verdict = analyze_results(results, config)
    results["analysis"] = analysis

    # Save updated results
    save_results(results, output_dir)

    # Regenerate charts (organized by scenario)
    chart_gen = ChartGenerator(output_dir)
    chart_paths = chart_gen.generate_charts_by_scenario(results)
    total_charts = sum(len(paths) for paths in chart_paths.values())
    console.print(f"[green]Generated {total_charts} charts[/green]")

    # Generate reports
    report_gen = ReportGenerator(output_dir, output_dir / "charts")
    report_paths = report_gen.generate_all(results, verdict)
    console.print(
        f"[green]Generated reports: {report_paths.markdown.name}, {report_paths.html.name}[/green]"
    )

    _print_summary(results, verdict)


def _derive_max_reliable_speed(speed_result: ScenarioResult) -> int:
    """Derive the maximum reliable speed multiplier from a speed scaling result.

    Rules:
    - If no step results exist, returns 1.
    - If aborted (e.g., OOM) or stopped by threshold, returns the multiplier
      from the last step where threshold was NOT hit (the last known-good
      speed), or 1 if the first step hit.
    - If all steps passed, returns max_speed_achieved from metadata.

    Args:
        speed_result: Result from SpeedScalingScenario.

    Returns:
        The highest speed multiplier that was stable, minimum 1.
    """
    step_results = speed_result.metadata.get("step_results", [])
    if not step_results:
        return 1

    # Find last step where threshold was NOT hit (works for both
    # aborted and threshold-stopped scenarios)
    if speed_result.aborted or speed_result.metadata.get("stopped_by_threshold", False):
        last_good_multiplier = 1
        for step in step_results:
            if not step.get("threshold_hit", False):
                last_good_multiplier = step.get("multiplier", 1)
        return last_good_multiplier

    # All steps passed — use max_speed_achieved
    max_speed: int = speed_result.metadata.get("max_speed_achieved", 1)
    return max(max_speed, 1)


def _result_to_dict(result: ScenarioResult) -> dict[str, Any]:
    """Convert ScenarioResult to dict."""
    return {
        "scenario_name": result.scenario_name,
        "scenario_params": result.scenario_params,
        "started_at": result.started_at,
        "completed_at": result.completed_at,
        "duration_seconds": result.duration_seconds,
        "samples": result.samples,
        "oom_events": result.oom_events,
        "aborted": result.aborted,
        "abort_reason": result.abort_reason,
        "metadata": result.metadata,
    }


def _print_summary(results: dict[str, Any], verdict: TestVerdict | None = None) -> None:
    """Print test summary with verdict, findings, and recommendations.

    Args:
        results: Full test results dictionary.
        verdict: Optional TestVerdict (generated if not provided).
    """
    console.print("\n")
    console.rule("[bold]Test Summary[/bold]")

    # Overall verdict
    if verdict:
        status_styles = {
            OverallStatus.PASS: "[bold green]PASS[/bold green]",
            OverallStatus.WARNING: "[bold yellow]WARNING[/bold yellow]",
            OverallStatus.FAIL: "[bold red]FAIL[/bold red]",
        }
        status_display = status_styles.get(verdict.overall_status, str(verdict.overall_status))
        console.print(f"\nOverall Status: {status_display}")
        console.print(
            f"  Scenarios: {verdict.scenarios_passed} passed, {verdict.scenarios_failed} failed"
        )
        if verdict.total_oom_events > 0:
            console.print(f"  [red]OOM Events: {verdict.total_oom_events}[/red]")
    else:
        scenarios = results.get("scenarios", [])
        non_stress = [s for s in scenarios if s.get("scenario_name") != "stress_test"]
        passed = sum(1 for s in non_stress if not s.get("aborted", False))
        failed = len(non_stress) - passed

        console.print(f"\nTotal scenarios: {len(scenarios)}")
        console.print(f"  [green]Passed: {passed}[/green]")
        if failed > 0:
            console.print(f"  [red]Failed/Aborted: {failed}[/red]")

        total_oom = sum(len(s.get("oom_events", [])) for s in non_stress)
        if total_oom > 0:
            console.print(f"  [red]OOM Events: {total_oom}[/red]")

    # Findings section
    if verdict and verdict.findings:
        console.print("\n[bold]Findings:[/bold]")

        # Group and display by severity
        critical_findings = [f for f in verdict.findings if f.severity == Severity.CRITICAL]
        warning_findings = [f for f in verdict.findings if f.severity == Severity.WARNING]

        for finding in critical_findings:
            console.print(f"  [red]X[/red] {finding.message}")
        for finding in warning_findings:
            console.print(f"  [yellow]![/yellow] {finding.message}")

    # Container Health Table
    if verdict and verdict.container_health:
        console.print("\n[bold]Container Health:[/bold]")

        health_table = Table(show_header=True, header_style="bold")
        health_table.add_column("Container")
        health_table.add_column("Memory", justify="right")
        health_table.add_column("Limit", justify="right")
        health_table.add_column("Usage %", justify="right")
        health_table.add_column("Leak Rate", justify="right")
        health_table.add_column("Status")

        for health in verdict.container_health:
            leak_str = (
                f"{health.memory_leak_rate_mb_per_min:.2f} MB/min"
                if health.memory_leak_rate_mb_per_min is not None
                else "N/A"
            )
            limit_str = f"{health.memory_limit_mb:.0f} MB" if health.memory_limit_mb > 0 else "N/A"
            percent_str = f"{health.memory_percent:.1f}%" if health.memory_percent > 0 else "N/A"

            health_status_styles: dict[str, str] = {
                "healthy": "[green]OK[/green]",
                "warning": "[yellow]WARN[/yellow]",
                "critical": "[red]CRIT[/red]",
            }
            status_display = health_status_styles.get(health.status, health.status)

            health_table.add_row(
                health.display_name,
                f"{health.memory_current_mb:.1f} MB",
                limit_str,
                percent_str,
                leak_str,
                status_display,
            )

        console.print(health_table)

    # Derived configuration (stress → duration agent count, speed scaling → speed)
    derived_config = results.get("derived_config", {})
    if derived_config:
        console.print("\n[bold]Derived Configuration:[/bold]")
        duration_agents = derived_config.get("duration_agent_count")
        total_queued = derived_config.get("total_agents_queued")
        if duration_agents and total_queued:
            console.print(
                f"  Duration test agents: {duration_agents} "
                f"(half of {total_queued} total from stress test)"
            )
        duration_speed = derived_config.get("duration_speed_multiplier")
        if duration_speed and duration_agents:
            console.print(
                f"  With {duration_agents} agents, simulation ran reliably "
                f"up to {duration_speed}x speed"
            )

    # Speed scaling results
    scenarios = results.get("scenarios", [])
    speed_scenarios = [s for s in scenarios if s.get("scenario_name") == "speed_scaling"]
    if speed_scenarios:
        speed_meta = speed_scenarios[0].get("metadata", {})
        total_steps = speed_meta.get("total_steps", 0)
        max_speed = speed_meta.get("max_speed_achieved", 0)
        stopped = speed_meta.get("stopped_by_threshold", False)

        console.print("\n[bold]Speed Scaling Results:[/bold]")
        console.print(f"  Steps completed: {total_steps}")
        console.print(f"  Max speed achieved: {max_speed}x")
        if stopped:
            console.print("  [yellow]Stopped by threshold[/yellow]")
        else:
            console.print("  [green]Completed all steps[/green]")

    # Recommendations
    if verdict and verdict.recommendations:
        console.print("\n[bold]Recommendations:[/bold]")
        for rec in verdict.recommendations:
            console.print(f"  - {rec}")


if __name__ == "__main__":
    cli()
