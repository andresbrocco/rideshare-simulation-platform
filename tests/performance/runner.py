#!/usr/bin/env python3
"""Performance testing CLI runner.

Usage:
    ./venv/bin/python tests/performance/runner.py run           # All scenarios
    ./venv/bin/python tests/performance/runner.py run -s load   # Specific scenario
    ./venv/bin/python tests/performance/runner.py check         # Service status
    ./venv/bin/python tests/performance/runner.py analyze <file> # Re-analyze
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
from .analysis.resource_model import fit_load_scaling_all_containers
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
from .scenarios.load_scaling import LoadScalingScenario
from .scenarios.reset_behavior import ResetBehaviorScenario
from .scenarios.stress_test import StressTestScenario

console = Console()


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

    # Fit load scaling models for ALL containers, both memory and cpu
    all_container_fits = fit_load_scaling_all_containers(scenarios, None, ["memory", "cpu"])
    analysis["container_fits"] = all_container_fits

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

        # Check for OOM events
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

        # Check reset behavior failures
        if scenario_name == "reset_behavior":
            for sample in samples:
                analysis = sample.get("analysis", {})
                all_containers = analysis.get("all_containers", {})

                for container, data in all_containers.items():
                    display_name = CONTAINER_CONFIG.get(container, {}).get(
                        "display_name", container
                    )

                    if not data.get("mem_passed", True):
                        diff = data.get("mem_diff_percent", 0)
                        findings.append(
                            Finding(
                                severity=Severity.WARNING,
                                category=FindingCategory.RESET_FAILURE,
                                container=container,
                                message=f"{display_name} memory not fully released after reset ({diff:+.1f}%)",
                                metric_value=diff,
                                threshold=config.scenarios.reset_tolerance_percent,
                                scenario_name=scenario_name,
                                recommendation="Check for memory leaks or resource cleanup issues",
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

    # Count scenarios
    scenarios_passed = sum(1 for s in scenarios if not s.get("aborted", False))
    scenarios_failed = len(scenarios) - scenarios_passed

    # Count OOM events
    total_oom = sum(len(s.get("oom_events", [])) for s in scenarios)

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
    "-s",
    "--scenario",
    type=click.Choice(["all", "baseline", "load", "duration", "reset", "stress"]),
    default="all",
    help="Which scenario(s) to run",
)
@click.option(
    "--skip-restart",
    is_flag=True,
    help="Skip clean restart between scenarios (faster but less accurate)",
)
@click.option(
    "--include-stress",
    is_flag=True,
    help="Include stress test when running 'all' scenarios (excluded by default)",
)
def run(scenario: str, skip_restart: bool, include_stress: bool) -> None:
    """Run performance test scenarios."""
    config = create_test_config()
    lifecycle, stats_collector, api_client, oom_detector = create_collectors(config)

    # Create output directory
    test_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = config.output_dir / test_id
    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Test ID: {test_id}[/bold]")
    console.print(f"Output directory: {output_dir}\n")

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
                "load_levels": config.scenarios.load_levels,
                "duration_total_minutes": config.scenarios.duration_total_minutes,
                "duration_checkpoints": config.scenarios.duration_checkpoints,
            },
        },
        "scenarios": [],
    }

    scenario_results: list[dict[str, Any]] = []

    try:
        # Baseline
        if scenario in ["all", "baseline"]:
            console.rule("[bold cyan]Running Baseline Scenario[/bold cyan]")
            result = run_scenario(
                BaselineScenario,
                config,
                lifecycle,
                stats_collector,
                api_client,
                oom_detector,
                skip_clean_restart=True,
            )
            scenario_results.append(_result_to_dict(result))

        # Load scaling
        if scenario in ["all", "load"]:
            for level in config.scenarios.load_levels:
                console.rule(f"[bold cyan]Running Load Scaling: {level} agents[/bold cyan]")
                result = run_scenario(
                    LoadScalingScenario,
                    config,
                    lifecycle,
                    stats_collector,
                    api_client,
                    oom_detector,
                    agent_count=level,
                    skip_clean_restart=True,
                )
                scenario_results.append(_result_to_dict(result))

        # Duration/leak test (single continuous run with checkpoints)
        if scenario in ["all", "duration"]:
            console.rule(
                f"[bold cyan]Running Duration Test: {config.scenarios.duration_total_minutes} minutes "
                f"(checkpoints: {config.scenarios.duration_checkpoints})[/bold cyan]"
            )
            result = run_scenario(
                DurationLeakScenario,
                config,
                lifecycle,
                stats_collector,
                api_client,
                oom_detector,
                skip_clean_restart=True,
            )
            scenario_results.append(_result_to_dict(result))

        # Reset behavior
        if scenario in ["all", "reset"]:
            console.rule("[bold cyan]Running Reset Behavior Test[/bold cyan]")
            result = run_scenario(
                ResetBehaviorScenario,
                config,
                lifecycle,
                stats_collector,
                api_client,
                oom_detector,
                skip_clean_restart=True,
            )
            scenario_results.append(_result_to_dict(result))

        # Stress test (excluded from "all" by default)
        if scenario == "stress" or (scenario == "all" and include_stress):
            console.rule(
                f"[bold cyan]Running Stress Test: until {config.scenarios.stress_cpu_threshold_percent}% CPU "
                f"or {config.scenarios.stress_memory_threshold_percent}% memory[/bold cyan]"
            )
            result = run_scenario(
                StressTestScenario,
                config,
                lifecycle,
                stats_collector,
                api_client,
                oom_detector,
                skip_clean_restart=True,
            )
            scenario_results.append(_result_to_dict(result))

    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")

    # Finalize results
    results["scenarios"] = scenario_results
    results["completed_at"] = datetime.now().isoformat()

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
        passed = sum(1 for s in scenarios if not s.get("aborted", False))
        failed = len(scenarios) - passed

        console.print(f"\nTotal scenarios: {len(scenarios)}")
        console.print(f"  [green]Passed: {passed}[/green]")
        if failed > 0:
            console.print(f"  [red]Failed/Aborted: {failed}[/red]")

        total_oom = sum(len(s.get("oom_events", [])) for s in scenarios)
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

            status_styles = {
                "healthy": "[green]OK[/green]",
                "warning": "[yellow]WARN[/yellow]",
                "critical": "[red]CRIT[/red]",
            }
            status_display = status_styles.get(health.status, health.status)

            health_table.add_row(
                health.display_name,
                f"{health.memory_current_mb:.1f} MB",
                limit_str,
                percent_str,
                leak_str,
                status_display,
            )

        console.print(health_table)

    # Scaling formulas for priority containers
    analysis = results.get("analysis", {})
    container_fits = analysis.get("container_fits", {})

    priority_containers = [
        "rideshare-simulation",
        "rideshare-kafka",
        "rideshare-redis",
    ]

    has_formulas = False
    for container in priority_containers:
        container_data = container_fits.get(container, {})
        display = container.replace("rideshare-", "").title()

        memory_fit = container_data.get("memory", {})
        memory_best = memory_fit.get("best_fit")

        cpu_fit = container_data.get("cpu", {})
        cpu_best = cpu_fit.get("best_fit")

        if memory_best or cpu_best:
            if not has_formulas:
                console.print("\n[bold]Scaling Formulas:[/bold]")
                has_formulas = True
            console.print(f"\n  [cyan]{display}:[/cyan]")
            if memory_best:
                console.print(
                    f"    Memory: {memory_best['formula']} (R²={memory_best['r_squared']:.3f})"
                )
            if cpu_best:
                console.print(f"    CPU:    {cpu_best['formula']} (R²={cpu_best['r_squared']:.3f})")

    # Recommendations
    if verdict and verdict.recommendations:
        console.print("\n[bold]Recommendations:[/bold]")
        for rec in verdict.recommendations:
            console.print(f"  - {rec}")


if __name__ == "__main__":
    cli()
