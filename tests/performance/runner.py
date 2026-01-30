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

from .analysis.resource_model import fit_load_scaling_results
from .analysis.statistics import summarize_scenario_stats
from .analysis.visualizations import ChartGenerator
from .collectors.docker_lifecycle import DockerLifecycleManager
from .collectors.docker_stats import DockerStatsCollector
from .collectors.oom_detector import OOMDetector
from .collectors.simulation_api import SimulationAPIClient
from .config import CONTAINER_CONFIG, TestConfig
from .scenarios.base import ScenarioResult
from .scenarios.baseline import BaselineScenario
from .scenarios.duration_leak import DurationLeakScenario
from .scenarios.load_scaling import LoadScalingScenario
from .scenarios.reset_behavior import ResetBehaviorScenario

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
    scenario_class: type,
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


def analyze_results(results: dict[str, Any]) -> dict[str, Any]:
    """Analyze results and add analysis section."""
    scenarios = results.get("scenarios", [])

    analysis: dict[str, Any] = {}

    # Fit load scaling models
    load_fit = fit_load_scaling_results(scenarios)
    if "error" not in load_fit:
        analysis["rideshare-simulation"] = {
            "best_fit": load_fit.get("best_fit"),
            "all_fits": load_fit.get("all_fits"),
            "data_points": load_fit.get("data_points"),
        }

    # Per-scenario summaries
    scenario_summaries: list[dict[str, Any]] = []
    for scenario in scenarios:
        samples = scenario.get("samples", [])
        summary = summarize_scenario_stats(samples)
        summary["scenario_name"] = scenario["scenario_name"]
        scenario_summaries.append(summary)

    analysis["scenario_summaries"] = scenario_summaries

    return analysis


@click.group()
def cli() -> None:
    """Performance testing framework for rideshare simulation platform."""
    pass


@cli.command()
@click.option(
    "-s",
    "--scenario",
    type=click.Choice(["all", "baseline", "load", "duration", "reset"]),
    default="all",
    help="Which scenario(s) to run",
)
@click.option(
    "--skip-restart",
    is_flag=True,
    help="Skip clean restart between scenarios (faster but less accurate)",
)
def run(scenario: str, skip_restart: bool) -> None:
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
                "duration_minutes": config.scenarios.duration_minutes,
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
                )
                scenario_results.append(_result_to_dict(result))

        # Duration/leak tests
        if scenario in ["all", "duration"]:
            for minutes in config.scenarios.duration_minutes:
                console.rule(f"[bold cyan]Running Duration Test: {minutes} minutes[/bold cyan]")
                result = run_scenario(
                    DurationLeakScenario,
                    config,
                    lifecycle,
                    stats_collector,
                    api_client,
                    oom_detector,
                    duration_minutes=minutes,
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
            )
            scenario_results.append(_result_to_dict(result))

    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")

    # Finalize results
    results["scenarios"] = scenario_results
    results["completed_at"] = datetime.now().isoformat()

    # Analyze
    console.print("\n[bold]Analyzing results...[/bold]")
    results["analysis"] = analyze_results(results)

    # Save results
    results_file = save_results(results, output_dir)
    console.print(f"[green]Results saved to: {results_file}[/green]")

    # Generate charts
    console.print("\n[bold]Generating charts...[/bold]")
    chart_gen = ChartGenerator(output_dir)
    charts = chart_gen.generate_all_charts(results)
    console.print(f"[green]Generated {len(charts)} charts[/green]")

    # Summary
    _print_summary(results)

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
    with open(results_file) as f:
        results = json.load(f)

    output_dir = Path(results_file).parent

    console.print(f"[bold]Re-analyzing: {results_file}[/bold]")

    # Re-run analysis
    results["analysis"] = analyze_results(results)

    # Save updated results
    save_results(results, output_dir)

    # Regenerate charts
    chart_gen = ChartGenerator(output_dir)
    charts = chart_gen.generate_all_charts(results)
    console.print(f"[green]Generated {len(charts)} charts[/green]")

    _print_summary(results)


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


def _print_summary(results: dict[str, Any]) -> None:
    """Print test summary."""
    console.print("\n")
    console.rule("[bold]Test Summary[/bold]")

    scenarios = results.get("scenarios", [])
    passed = sum(1 for s in scenarios if not s.get("aborted", False))
    failed = len(scenarios) - passed

    console.print(f"Total scenarios: {len(scenarios)}")
    console.print(f"  [green]Passed: {passed}[/green]")
    if failed > 0:
        console.print(f"  [red]Failed/Aborted: {failed}[/red]")

    # OOM events
    total_oom = sum(len(s.get("oom_events", [])) for s in scenarios)
    if total_oom > 0:
        console.print(f"  [red]OOM Events: {total_oom}[/red]")

    # Best fit formula
    analysis = results.get("analysis", {})
    sim_analysis = analysis.get("rideshare-simulation", {})
    best_fit = sim_analysis.get("best_fit")
    if best_fit:
        console.print("\n[bold]Scaling Formula:[/bold]")
        console.print(f"  {best_fit['formula']}")
        console.print(f"  R² = {best_fit['r_squared']:.3f}")


if __name__ == "__main__":
    cli()
