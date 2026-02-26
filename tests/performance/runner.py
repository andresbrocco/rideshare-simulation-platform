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
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from .analysis.findings import (
    ContainerHealth,
    ContainerHealthAggregated,
    KeyMetrics,
    PerformanceIndexThresholds,
    SaturationFamily,
    ServiceHealthLatency,
    SuggestedThresholds,
    TestSummary,
)
from .analysis.report_generator import ReportGenerator
from .analysis.statistics import (
    BaselineCalibration,
    calculate_all_container_stats,
    calculate_all_health_stats,
    summarize_scenario_stats,
)
from .analysis.visualizations import ChartGenerator
from .collectors.docker_lifecycle import DockerLifecycleManager
from .collectors.oom_detector import OOMDetector
from .collectors.prometheus_collector import PrometheusCollector
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
_PERFORMANCE_RULES_PATH = (
    Path(__file__).parent.parent.parent / "services" / "prometheus" / "rules" / "performance.yml"
)


def create_test_config() -> TestConfig:
    """Create test configuration."""
    return TestConfig()


def create_collectors(
    config: TestConfig,
) -> tuple[
    DockerLifecycleManager,
    PrometheusCollector,
    SimulationAPIClient,
    OOMDetector,
]:
    """Create all collector instances."""
    lifecycle = DockerLifecycleManager(config)
    prometheus = PrometheusCollector(config)
    api_client = SimulationAPIClient(config)
    oom_detector = OOMDetector()
    return lifecycle, prometheus, api_client, oom_detector


def run_scenario(
    scenario_class: type[BaseScenario],
    config: TestConfig,
    lifecycle: DockerLifecycleManager,
    prometheus: PrometheusCollector,
    api_client: SimulationAPIClient,
    oom_detector: OOMDetector,
    **kwargs: Any,
) -> ScenarioResult:
    """Run a single scenario."""
    scenario = scenario_class(
        config=config,
        lifecycle=lifecycle,
        prometheus=prometheus,
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
) -> tuple[dict[str, Any], TestSummary]:
    """Analyze results and produce a factual summary (no severity judgments).

    Args:
        results: Full test results dictionary.
        config: Test configuration.

    Returns:
        Tuple of (analysis dict, TestSummary).
    """
    scenarios = results.get("scenarios", [])

    analysis: dict[str, Any] = {}

    # Per-scenario summaries (includes all containers)
    scenario_summaries: list[dict[str, Any]] = []
    for scenario in scenarios:
        samples = scenario.get("samples", [])
        scenario_stats = summarize_scenario_stats(samples, None)
        scenario_stats["scenario_name"] = scenario["scenario_name"]
        scenario_summaries.append(scenario_stats)

    analysis["scenario_summaries"] = scenario_summaries

    # Container health (legacy per-scenario)
    container_health = _generate_container_health(results, config)

    # Aggregated container health (across all scenarios)
    aggregated_health = _generate_aggregated_container_health(results, config)

    # Key metrics
    key_metrics = _extract_key_metrics(results, aggregated_health)

    # Service health latency analysis
    service_health_latency = _generate_service_health_latency(results)
    suggested_thresholds = _compute_suggested_thresholds(service_health_latency, config)

    # Saturation curve analysis
    saturation_family = _build_saturation_family(results)

    # Performance index thresholds derived from failure snapshots
    performance_index_thresholds = _compute_performance_index_thresholds(results)

    summary = TestSummary(
        container_health=container_health,
        aggregated_container_health=aggregated_health,
        key_metrics=key_metrics,
        service_health_latency=service_health_latency,
        suggested_thresholds=suggested_thresholds,
        saturation_family=saturation_family,
        performance_index_thresholds=performance_index_thresholds,
    )

    return analysis, summary


def _generate_container_health(
    results: dict[str, Any], config: TestConfig
) -> list[ContainerHealth]:
    """Generate container health summary from latest scenario samples.

    Args:
        results: Full test results dictionary.
        config: Test configuration.

    Returns:
        List of container health summaries.
    """
    health_list: list[ContainerHealth] = []
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

    all_stats = calculate_all_container_stats(samples)

    # Calculate leak rates
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
            leak_rates = {c: None for c in containers}
    else:
        leak_rates = {c: None for c in containers}

    for container, data in containers.items():
        display_name = CONTAINER_CONFIG.get(container, {}).get("display_name", container)
        mem_current = data.get("memory_used_mb", 0)
        mem_limit = data.get("memory_limit_mb", 0)
        mem_percent = data.get("memory_percent", 0)
        cpu_current = data.get("cpu_percent", 0)
        stats = all_stats.get(container)
        cpu_peak = stats.cpu_max if stats else cpu_current

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
            )
        )

    priority = config.analysis.priority_containers
    health_list.sort(
        key=lambda h: (
            priority.index(h.container_name) if h.container_name in priority else 999,
            h.container_name,
        )
    )

    return health_list


def _generate_aggregated_container_health(
    results: dict[str, Any], config: TestConfig
) -> list[ContainerHealthAggregated]:
    """Generate container health aggregated across ALL scenarios.

    Uses baseline for idle values, peak across all scenarios, and
    leak rate from duration_leak scenario.
    """
    scenarios = results.get("scenarios", [])
    if not scenarios:
        return []

    # Collect all containers
    all_containers: set[str] = set()
    for scenario in scenarios:
        for sample in scenario.get("samples", []):
            all_containers.update(sample.get("containers", {}).keys())

    # Baseline stats
    baseline_stats: dict[str, Any] = {}
    baseline_scenarios = [s for s in scenarios if s["scenario_name"] == "baseline"]
    if baseline_scenarios:
        baseline_stats = calculate_all_container_stats(baseline_scenarios[0].get("samples", []))

    # Peak stats across all scenarios
    peak_memory: dict[str, tuple[float, str]] = {}  # container -> (peak_mb, scenario)
    peak_cpu: dict[str, tuple[float, str]] = {}  # container -> (peak_%, scenario)
    memory_limits: dict[str, float] = {}

    for scenario in scenarios:
        scenario_name = scenario["scenario_name"]
        stats = calculate_all_container_stats(scenario.get("samples", []))
        for container, s in stats.items():
            if container not in peak_memory or s.memory_max > peak_memory[container][0]:
                peak_memory[container] = (s.memory_max, scenario_name)
            if container not in peak_cpu or s.cpu_max > peak_cpu[container][0]:
                peak_cpu[container] = (s.cpu_max, scenario_name)
            if s.memory_limit_mb > 0:
                memory_limits[container] = s.memory_limit_mb

    # Leak rates from duration scenario
    leak_rates: dict[str, float | None] = {}
    duration_scenarios = [
        s
        for s in scenarios
        if s["scenario_name"] == "duration_leak" or s["scenario_name"].startswith("duration_leak_")
    ]
    if duration_scenarios:
        leak_analysis = duration_scenarios[0].get("metadata", {}).get("leak_analysis", {})
        for container, la in leak_analysis.items():
            slope = la.get("memory_slope_mb_per_min")
            if slope is not None:
                leak_rates[container] = slope

    # Final memory from last scenario's last sample
    last_scenario = scenarios[-1]
    last_samples = last_scenario.get("samples", [])
    last_sample = last_samples[-1] if last_samples else {}
    final_containers = last_sample.get("containers", {})

    health_list: list[ContainerHealthAggregated] = []

    for container in sorted(all_containers):
        display_name = CONTAINER_CONFIG.get(container, {}).get("display_name", container)
        mem_limit = memory_limits.get(container, 0)

        # Baseline
        bs = baseline_stats.get(container)
        baseline_mem = bs.memory_mean if bs else None
        baseline_cpu = bs.cpu_mean if bs else None

        # Peak
        p_mem, p_mem_scenario = peak_memory.get(container, (0, "unknown"))
        p_cpu, p_cpu_scenario = peak_cpu.get(container, (0, "unknown"))
        p_mem_pct = (p_mem / mem_limit * 100) if mem_limit > 0 else 0

        # Final
        final_data = final_containers.get(container, {})
        final_mem = final_data.get("memory_used_mb", 0)
        final_mem_pct = final_data.get("memory_percent", 0)

        # Leak
        leak = leak_rates.get(container)

        health_list.append(
            ContainerHealthAggregated(
                container_name=container,
                display_name=display_name,
                memory_limit_mb=mem_limit,
                baseline_memory_mb=baseline_mem,
                baseline_cpu_percent=baseline_cpu,
                peak_memory_mb=p_mem,
                peak_memory_percent=p_mem_pct,
                peak_memory_scenario=p_mem_scenario,
                peak_cpu_percent=p_cpu,
                peak_cpu_scenario=p_cpu_scenario,
                leak_rate_mb_per_min=leak,
                final_memory_mb=final_mem,
                final_memory_percent=final_mem_pct,
            )
        )

    # Sort by priority
    priority = config.analysis.priority_containers
    health_list.sort(
        key=lambda h: (
            priority.index(h.container_name) if h.container_name in priority else 999,
            h.container_name,
        )
    )

    return health_list


def _generate_service_health_latency(
    results: dict[str, Any],
) -> list[ServiceHealthLatency]:
    """Generate service health latency summaries across scenarios.

    For each service found in health data, computes baseline p95, stressed p95,
    and peak latency across all scenarios.  When baseline calibration data exists,
    uses baseline-derived thresholds instead of API-reported values.
    """
    scenarios = results.get("scenarios", [])
    if not scenarios:
        return []

    # Extract baseline calibration if available
    calibration_dict: dict[str, Any] | None = None
    for scenario in scenarios:
        if scenario.get("scenario_name") == "baseline":
            calibration_dict = scenario.get("metadata", {}).get("calibration")
            break

    # Compute health stats per scenario
    per_scenario: dict[str, dict[str, Any]] = {}
    for scenario in scenarios:
        name = scenario.get("scenario_name", "unknown")
        samples = scenario.get("samples", [])
        stats = calculate_all_health_stats(samples)
        if stats:
            per_scenario[name] = {svc: s for svc, s in stats.items()}

    if not per_scenario:
        return []

    # Discover all service names
    all_services: set[str] = set()
    for stats_dict in per_scenario.values():
        all_services.update(stats_dict.keys())

    # Build ServiceHealthLatency for each service
    health_list: list[ServiceHealthLatency] = []
    for svc_name in sorted(all_services):
        baseline_p95: float | None = None
        stressed_p95: float | None = None
        peak_latency: float | None = None
        peak_scenario: str | None = None
        threshold_degraded: float | None = None
        threshold_unhealthy: float | None = None
        threshold_source = "api-reported"

        # Use baseline-derived thresholds when available
        if calibration_dict is not None:
            cal_thresholds = calibration_dict.get("health_thresholds", {}).get(svc_name)
            if cal_thresholds is not None:
                threshold_degraded = cal_thresholds.get("degraded")
                threshold_unhealthy = cal_thresholds.get("unhealthy")
                threshold_source = "baseline-derived"

        # Baseline
        baseline_stats = per_scenario.get("baseline", {}).get(svc_name)
        if baseline_stats is not None:
            baseline_p95 = baseline_stats.latency_p95

        # Stress
        stress_stats = per_scenario.get("stress_test", {}).get(svc_name)
        if stress_stats is not None:
            stressed_p95 = stress_stats.latency_p95

        # Peak across all scenarios
        for scenario_name, stats_dict in per_scenario.items():
            svc_stats = stats_dict.get(svc_name)
            if svc_stats is not None:
                if peak_latency is None or svc_stats.latency_max > peak_latency:
                    peak_latency = svc_stats.latency_max
                    peak_scenario = scenario_name
                # Capture thresholds from first available (only if not already set by calibration)
                if threshold_degraded is None and svc_stats.threshold_degraded is not None:
                    threshold_degraded = svc_stats.threshold_degraded
                if threshold_unhealthy is None and svc_stats.threshold_unhealthy is not None:
                    threshold_unhealthy = svc_stats.threshold_unhealthy

        health_list.append(
            ServiceHealthLatency(
                service_name=svc_name,
                baseline_latency_p95=baseline_p95,
                stressed_latency_p95=stressed_p95,
                peak_latency_ms=peak_latency,
                peak_latency_scenario=peak_scenario,
                threshold_degraded=threshold_degraded,
                threshold_unhealthy=threshold_unhealthy,
                threshold_source=threshold_source,
            )
        )

    return health_list


def _compute_suggested_thresholds(
    health_latency: list[ServiceHealthLatency],
    config: TestConfig,
) -> list[SuggestedThresholds]:
    """Compute suggested thresholds based on empirically observed p95 latencies.

    Derivation rule:
        suggested_degraded = reference_p95 * degraded_multiplier
        suggested_unhealthy = reference_p95 * unhealthy_multiplier
    Prefers stressed p95 when available, falls back to baseline p95.
    """
    degraded_mult = config.scenarios.health_baseline_degraded_multiplier
    unhealthy_mult = config.scenarios.health_baseline_unhealthy_multiplier
    thresholds: list[SuggestedThresholds] = []

    for h in health_latency:
        # Choose reference p95: prefer stressed, fall back to baseline
        reference_p95: float | None = None
        based_on_scenario = "unknown"
        if h.stressed_latency_p95 is not None:
            reference_p95 = h.stressed_latency_p95
            based_on_scenario = "stress_test"
        elif h.baseline_latency_p95 is not None:
            reference_p95 = h.baseline_latency_p95
            based_on_scenario = "baseline"

        if reference_p95 is None or reference_p95 <= 0:
            continue

        thresholds.append(
            SuggestedThresholds(
                service_name=h.service_name,
                current_degraded=h.threshold_degraded,
                current_unhealthy=h.threshold_unhealthy,
                suggested_degraded=round(reference_p95 * degraded_mult, 1),
                suggested_unhealthy=round(reference_p95 * unhealthy_mult, 1),
                based_on_p95=reference_p95,
                based_on_scenario=based_on_scenario,
            )
        )

    return thresholds


def _build_saturation_family(results: dict[str, Any]) -> SaturationFamily | None:
    """Build a SaturationFamily from scenario results.

    NOTE: USL-based saturation curve building is currently disabled.
    This function always returns None.

    Args:
        results: Full test results dictionary.

    Returns:
        None (saturation family building disabled).
    """
    return None


def _compute_performance_index_thresholds(
    results: dict[str, Any],
) -> PerformanceIndexThresholds | None:
    """Derive performance index saturation divisors from observed failure snapshots.

    Prefers the failure snapshot from the stress test scenario. Falls back to
    the last triggered step in speed_scaling if no stress snapshot is available.
    Returns None if no failure snapshot is found in either scenario.

    Applies safety margins (10% headroom on counts, floor values on percentages)
    so that divisors represent a safe saturation ceiling rather than the raw
    observed peak.

    Args:
        results: Full test results dictionary.

    Returns:
        PerformanceIndexThresholds populated from observed data, or None.
    """
    scenarios = results.get("scenarios", [])

    snapshot: dict[str, Any] | None = None
    source_scenario = ""
    source_trigger = ""

    # Preferred: stress_test failure_snapshot
    stress_scenarios = [s for s in scenarios if s["scenario_name"] == "stress_test"]
    if stress_scenarios:
        meta = stress_scenarios[0].get("metadata", {})
        fs = meta.get("failure_snapshot")
        if fs:
            snapshot = fs
            source_scenario = "stress_test"
            trigger_info = meta.get("trigger", {}) or {}
            source_trigger = (
                f"{trigger_info.get('metric', 'unknown')} at " f"{trigger_info.get('value', 0)}"
            )

    # Fallback: last triggered step in speed_scaling
    if snapshot is None:
        speed_scenarios = [s for s in scenarios if s["scenario_name"] == "speed_scaling"]
        if speed_scenarios:
            meta = speed_scenarios[0].get("metadata", {})
            step_results = meta.get("step_results", [])
            for step in reversed(step_results):
                if step.get("threshold_hit") and step.get("failure_snapshot"):
                    snapshot = step["failure_snapshot"]
                    source_scenario = "speed_scaling"
                    trigger_info = step.get("trigger") or {}
                    source_trigger = (
                        f"{trigger_info.get('metric', 'unknown')} at "
                        f"{trigger_info.get('value', 0)}"
                    )
                    break

    if snapshot is None:
        return None

    # Kafka lag: observed value * 1.1, minimum 1000, default 10000
    raw_kafka_lag = snapshot.get("kafka_consumer_lag")
    if raw_kafka_lag is not None:
        kafka_lag_saturation = max(1000, int(raw_kafka_lag * 1.1))
    else:
        kafka_lag_saturation = 10000

    # SimPy queue: observed value * 1.1, minimum 100, default 500
    raw_simpy_queue = snapshot.get("simpy_event_queue")
    if raw_simpy_queue is not None:
        simpy_queue_saturation = max(100, int(raw_simpy_queue * 1.1))
    else:
        simpy_queue_saturation = 500

    return PerformanceIndexThresholds(
        kafka_lag_saturation=kafka_lag_saturation,
        simpy_queue_saturation=simpy_queue_saturation,
        source_scenario=source_scenario,
        source_trigger=source_trigger,
    )


def _update_performance_rules(
    thresholds: PerformanceIndexThresholds,
    rules_path: Path = _PERFORMANCE_RULES_PATH,
) -> bool:
    """Update Prometheus performance rule divisors from empirical thresholds.

    Uses regex to replace the numeric divisors in the YAML while preserving
    formatting. Each replacement targets the recording rule by name and swaps
    the first numeric divisor in its expression.

    Args:
        thresholds: Empirically-derived saturation divisors.
        rules_path: Path to the performance.yml rules file.

    Returns:
        True if any divisor was updated, False otherwise.
    """
    if not rules_path.exists():
        console.print(f"[yellow]Performance rules not found at {rules_path}[/yellow]")
        return False

    content = rules_path.read_text()
    original = content
    updates: list[str] = []

    # kafka_lag_headroom: replace divisor after "/ <number>"
    new_content = re.sub(
        r"(kafka_lag_headroom.*?/ )\d+",
        rf"\g<1>{thresholds.kafka_lag_saturation}",
        content,
        count=1,
        flags=re.DOTALL,
    )
    if new_content != content:
        updates.append(f"kafka_lag divisor -> {thresholds.kafka_lag_saturation}")
    content = new_content

    # simpy_queue_headroom: replace divisor after "/ <number>"
    new_content = re.sub(
        r"(simpy_queue_headroom.*?/ )\d+",
        rf"\g<1>{thresholds.simpy_queue_saturation}",
        content,
        count=1,
        flags=re.DOTALL,
    )
    if new_content != content:
        updates.append(f"simpy_queue divisor -> {thresholds.simpy_queue_saturation}")
    content = new_content

    if content == original:
        console.print("[dim]Performance rules unchanged (divisors already match)[/dim]")
        return False

    rules_path.write_text(content)
    for update in updates:
        console.print(f"[green]Updated performance rule: {update}[/green]")
    console.print(
        f"[green]Performance rules updated at {rules_path} "
        f"(source: {thresholds.source_scenario})[/green]"
    )
    return True


def _extract_key_metrics(
    results: dict[str, Any],
    aggregated_health: list[ContainerHealthAggregated],
) -> KeyMetrics:
    """Extract hero numbers for reports."""
    scenarios = results.get("scenarios", [])

    # Max agents from stress
    max_agents: int | None = None
    stress_trigger: str | None = None
    available_cores: int | None = None
    stress_scenarios = [s for s in scenarios if s["scenario_name"] == "stress_test"]
    active_trips_peak: float | None = None
    throughput_peak: float | None = None
    if stress_scenarios:
        meta = stress_scenarios[0].get("metadata", {})
        max_agents = meta.get("total_agents_queued")
        available_cores = meta.get("available_cores")
        active_trips_peak = meta.get("active_trips_peak")
        throughput_peak = meta.get("throughput_peak_events_per_sec")
        trigger = meta.get("trigger")
        if trigger:
            metric = trigger.get("metric", "unknown")
            value = trigger.get("value", 0)
            threshold = trigger.get("threshold", 0)
            if metric == "rtr_collapse":
                stress_trigger = f"RTR collapse at {value:.4f} (threshold: {threshold})"
            elif metric == "max_duration":
                stress_trigger = f"Time limit ({value:.0f}s)"
            else:
                stress_trigger = f"{metric} at {value:.1f} (threshold: {threshold})"

    # Max speed from speed_scaling
    max_speed: int | None = None
    speed_scenarios = [s for s in scenarios if s["scenario_name"] == "speed_scaling"]
    if speed_scenarios:
        meta = speed_scenarios[0].get("metadata", {})
        max_speed = meta.get("max_speed_achieved")

    # RTR peak across all scenarios
    rtr_peak: float | None = None
    for scenario in scenarios:
        for sample in scenario.get("samples", []):
            rtr = sample.get("rtr")
            if rtr is not None and "rtr" in rtr:
                v = rtr["rtr"]
                if rtr_peak is None or v < rtr_peak:
                    rtr_peak = v

    # Leak rates (container display name -> MB/min slope)
    leak_rates: dict[str, float] = {
        h.display_name: h.leak_rate_mb_per_min
        for h in aggregated_health
        if h.leak_rate_mb_per_min is not None and h.leak_rate_mb_per_min > 0
    }

    # Total duration
    started = results.get("started_at", "")
    completed = results.get("completed_at", "")
    duration_str = "N/A"
    if started and completed:
        try:
            s = datetime.fromisoformat(started)
            e = datetime.fromisoformat(completed)
            duration_str = str(e - s).split(".")[0]
        except ValueError:
            pass

    return KeyMetrics(
        max_agents_queued=max_agents,
        max_speed_achieved=max_speed,
        leak_rates=leak_rates,
        rtr_peak=rtr_peak,
        stress_trigger=stress_trigger,
        total_duration_str=duration_str,
        available_cores=available_cores,
        active_trips_peak=active_trips_peak,
        throughput_peak_events_per_sec=throughput_peak,
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
@click.option(
    "--stop-at-knee",
    is_flag=True,
    default=False,
    help="Stop stress test at USL knee point instead of running to failure.",
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
    stop_at_knee: bool,
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

    # Validate: agent count must be even
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
    if stop_at_knee:
        config.scenarios.stop_at_knee = stop_at_knee

    lifecycle, prometheus, api_client, oom_detector = create_collectors(config)

    test_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = config.output_dir / test_id
    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Test ID: {test_id}[/bold]")
    console.print(f"Output directory: {output_dir}")
    console.print(f"Scenarios: {', '.join(ordered)}\n")

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
                "stress_global_cpu_threshold_percent": config.scenarios.stress_global_cpu_threshold_percent,
                "stress_memory_threshold_percent": config.scenarios.stress_memory_threshold_percent,
                "stress_rtr_threshold": config.scenarios.stress_rtr_threshold,
                "stress_rtr_collapse_threshold": config.scenarios.stress_rtr_collapse_threshold,
                "health_baseline_degraded_multiplier": config.scenarios.health_baseline_degraded_multiplier,
                "health_baseline_unhealthy_multiplier": config.scenarios.health_baseline_unhealthy_multiplier,
                "rtr_baseline_fraction": config.scenarios.rtr_baseline_fraction,
                "speed_scaling_step_duration_minutes": config.scenarios.speed_scaling_step_duration_minutes,
                "speed_scaling_max_multiplier": config.scenarios.speed_scaling_max_multiplier,
                "health_check_enabled": config.scenarios.health_check_enabled,
            },
        },
        "scenarios": [],
    }

    scenario_results: list[dict[str, Any]] = []
    aborted = False
    abort_reason = None

    agent_count: int | None = agents
    derived_speed: int | None = speed_multiplier
    baseline_calibration: BaselineCalibration | None = None

    try:
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
                        prometheus,
                        api_client,
                        oom_detector,
                    )
                    result_dict = _result_to_dict(baseline_result)
                    scenario_results.append(result_dict)
                    _print_scenario_result("baseline", result_dict)

                    # Extract baseline calibration for downstream scenarios
                    calibration_dict = baseline_result.metadata.get("calibration")
                    if calibration_dict is not None:
                        baseline_calibration = BaselineCalibration(
                            health_thresholds=calibration_dict.get("health_thresholds", {}),
                            rtr_mean=calibration_dict.get("rtr_mean"),
                            rtr_threshold=calibration_dict.get("rtr_threshold"),
                            rtr_threshold_source=calibration_dict.get(
                                "rtr_threshold_source", "config-fallback"
                            ),
                            health_threshold_source=calibration_dict.get(
                                "health_threshold_source", "config-fallback"
                            ),
                        )
                        results.setdefault("derived_config", {}).update(
                            {
                                "baseline_rtr_mean": baseline_calibration.rtr_mean,
                                "baseline_rtr_threshold": baseline_calibration.rtr_threshold,
                                "baseline_rtr_threshold_source": (
                                    baseline_calibration.rtr_threshold_source
                                ),
                            }
                        )
                        _print_baseline_health_table(calibration_dict)

                elif scenario_name == "stress":
                    console.rule(
                        f"[bold cyan]{step_label}: Running Stress Test "
                        f"(until RTR collapse <= {config.scenarios.stress_rtr_collapse_threshold:.2f}, "
                        f"OOM, container death, or "
                        f"{config.scenarios.stress_max_duration_minutes}m max)"
                        f"[/bold cyan]"
                    )
                    stress_result = run_scenario(
                        StressTestScenario,
                        config,
                        lifecycle,
                        prometheus,
                        api_client,
                        oom_detector,
                        baseline_calibration=baseline_calibration,
                    )
                    result_dict = _result_to_dict(stress_result)
                    scenario_results.append(result_dict)
                    _print_scenario_result("stress_test", result_dict)

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
                        agent_count = round(total_agents_queued / 50 / 2) * 2
                        if agent_count < 2:
                            agent_count = 2
                        console.print(
                            f"\n[cyan]Derived agent count: {agent_count} "
                            f"(1/50 of {total_agents_queued} total from stress test)[/cyan]\n"
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
                        prometheus,
                        api_client,
                        oom_detector,
                        agent_count=agent_count,
                        baseline_calibration=baseline_calibration,
                    )
                    result_dict = _result_to_dict(speed_result)
                    scenario_results.append(result_dict)
                    _print_scenario_result("speed_scaling", result_dict)

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
                        prometheus,
                        api_client,
                        oom_detector,
                        agent_count=agent_count,
                        speed_multiplier=effective_speed,
                    )
                    result_dict = _result_to_dict(duration_result)
                    scenario_results.append(result_dict)
                    _print_scenario_result("duration_leak", result_dict)

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
    analysis, summary = analyze_results(results, config)
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

    # Generate saturation charts if data is available
    if summary.saturation_family is not None:
        saturation_dir = output_dir / "charts" / "saturation"
        sat_chart_paths = chart_gen.generate_saturation_charts(
            summary.saturation_family, saturation_dir
        )
        chart_paths.setdefault("saturation", []).extend(sat_chart_paths)
        console.print(f"[green]Generated {len(sat_chart_paths)} saturation charts[/green]")

    # Generate reports
    console.print("\n[bold]Generating reports...[/bold]")
    report_gen = ReportGenerator(output_dir, output_dir / "charts")
    report_paths = report_gen.generate_all(results, summary)
    console.print(
        f"[green]Generated reports: {report_paths.markdown.name}, {report_paths.html.name}[/green]"
    )

    # Auto-update Prometheus performance rules from empirical thresholds
    if summary.performance_index_thresholds is not None:
        _update_performance_rules(summary.performance_index_thresholds)

    # Summary
    _print_summary(results, summary)

    # Teardown Docker environment
    console.print("\n[bold]Tearing down Docker environment...[/bold]")
    success, _ = lifecycle.teardown_with_volumes()
    if not success:
        console.print("[yellow]Warning: Teardown may have failed, check Docker manually[/yellow]")


@cli.command()
def check() -> None:
    """Check status of required services."""
    config = create_test_config()
    lifecycle, prometheus, api_client, _ = create_collectors(config)

    table = Table(title="Service Status")
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details")

    if prometheus.is_available():
        table.add_row("Prometheus", "Available", config.docker.prometheus_url)
    else:
        table.add_row("Prometheus", "[red]Unavailable[/red]", config.docker.prometheus_url)

    if api_client.is_available():
        status = api_client.get_simulation_status()
        table.add_row(
            "Simulation API",
            "Available",
            f"State: {status.state}, Drivers: {status.drivers_total}, Riders: {status.riders_total}",
        )
    else:
        table.add_row("Simulation API", "[red]Unavailable[/red]", config.api.base_url)

    health_data = prometheus.get_health_latencies()
    if health_data is not None:
        table.add_row(
            "Health API",
            "Available",
            f"{len(health_data)} services reporting",
        )
    else:
        table.add_row(
            "Health API",
            "[red]Unavailable[/red]",
            f"{config.api.base_url}/metrics/infrastructure",
        )

    console.print(table)
    console.print()

    stats = prometheus.get_all_container_stats()
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
    analysis, summary = analyze_results(results, config)
    results["analysis"] = analysis

    # Save updated results
    save_results(results, output_dir)

    # Regenerate charts (organized by scenario)
    chart_gen = ChartGenerator(output_dir)
    chart_paths = chart_gen.generate_charts_by_scenario(results)
    total_charts = sum(len(paths) for paths in chart_paths.values())
    console.print(f"[green]Generated {total_charts} charts[/green]")

    # Generate saturation charts if data is available
    if summary.saturation_family is not None:
        saturation_dir = output_dir / "charts" / "saturation"
        sat_chart_paths = chart_gen.generate_saturation_charts(
            summary.saturation_family, saturation_dir
        )
        chart_paths.setdefault("saturation", []).extend(sat_chart_paths)
        console.print(f"[green]Generated {len(sat_chart_paths)} saturation charts[/green]")

    # Generate reports
    report_gen = ReportGenerator(output_dir, output_dir / "charts")
    report_paths = report_gen.generate_all(results, summary)
    console.print(
        f"[green]Generated reports: {report_paths.markdown.name}, {report_paths.html.name}[/green]"
    )

    # Auto-update Prometheus performance rules from empirical thresholds
    if summary.performance_index_thresholds is not None:
        _update_performance_rules(summary.performance_index_thresholds)

    _print_summary(results, summary)


def _derive_max_reliable_speed(speed_result: ScenarioResult) -> int:
    """Derive the maximum reliable speed multiplier from a speed scaling result."""
    step_results = speed_result.metadata.get("step_results", [])
    if not step_results:
        return 1

    if speed_result.aborted or speed_result.metadata.get("stopped_by_threshold", False):
        last_good_multiplier = 1
        for step in step_results:
            if not step.get("threshold_hit", False):
                last_good_multiplier = step.get("multiplier", 1)
        return last_good_multiplier

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


def _format_duration(seconds: float) -> str:
    """Format seconds into h:mm:ss or m:ss."""
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _print_scenario_result(scenario_name: str, result: dict[str, Any]) -> None:
    """Print a concise one-line result right after a scenario completes."""
    duration = result.get("duration_seconds", 0)
    n_samples = len(result.get("samples", []))
    meta = result.get("metadata", {})
    duration_str = _format_duration(duration)

    if scenario_name == "baseline":
        # Find top container by CPU and memory
        samples = result.get("samples", [])
        if samples:
            stats = calculate_all_container_stats(samples)
            top_cpu = max(stats.values(), key=lambda s: s.cpu_mean) if stats else None
            top_mem = max(stats.values(), key=lambda s: s.memory_mean) if stats else None
            cpu_info = (
                f"idle CPU {top_cpu.cpu_mean:.1f}% ({_get_display_name(top_cpu.container_name)})"
                if top_cpu
                else ""
            )
            mem_info = (
                f"idle mem {top_mem.memory_mean:.0f} MB ({_get_display_name(top_mem.container_name)})"
                if top_mem
                else ""
            )
            console.print(
                f"  [green]Baseline:[/green] {n_samples} samples, {duration_str}"
                f" -- {cpu_info}, {mem_info}"
            )
        else:
            console.print(f"  [green]Baseline:[/green] {n_samples} samples, {duration_str}")

    elif scenario_name == "stress_test":
        total_agents = meta.get("total_agents_queued", 0)
        trigger = meta.get("trigger", {})
        batch_count = meta.get("batch_count", 0)
        trigger_desc = ""
        if trigger:
            metric = trigger.get("metric", "")
            value = trigger.get("value", 0)
            if metric == "rtr_collapse":
                trigger_desc = f"stopped by RTR collapse ({value:.4f})"
            elif metric == "max_duration":
                trigger_desc = f"stopped by time limit ({value:.0f}s)"
            else:
                trigger_desc = f"stopped by {metric}"
        console.print(
            f"  [green]Stress:[/green] {total_agents} agents, {trigger_desc}, "
            f"{batch_count} batches, {duration_str}"
        )

    elif scenario_name == "speed_scaling":
        step_results = meta.get("step_results", [])
        total_steps = len(step_results)
        max_speed = meta.get("max_speed_achieved", 0)
        stopped = meta.get("stopped_by_threshold", False)
        # Find min/max multiplier
        multipliers = [s.get("multiplier", 0) for s in step_results]
        range_str = f"{min(multipliers)}x-{max(multipliers)}x" if multipliers else "N/A"
        stop_info = (
            f"stopped by threshold at {max(multipliers)}x"
            if stopped and multipliers
            else f"max reliable {max_speed}x"
        )
        console.print(
            f"  [green]Speed:[/green] {total_steps} steps ({range_str}), "
            f"{stop_info}, {duration_str}"
        )

    elif scenario_name == "duration_leak":
        leak_analysis = meta.get("leak_analysis", {})
        positive_slopes: dict[str, float] = {}
        for c, la in leak_analysis.items():
            slope = la.get("memory_slope_mb_per_min")
            if slope is not None and slope > 0:
                positive_slopes[_get_display_name(c)] = slope
        phase_ts = meta.get("phase_timestamps", {})
        active_dur = phase_ts.get("active_end", 0) - phase_ts.get("active_start", 0)
        drain_dur = meta.get("drain_duration_seconds", 0)
        cooldown_dur = phase_ts.get("cooldown_end", 0) - phase_ts.get("cooldown_start", 0)
        if positive_slopes:
            max_slope = max(positive_slopes.values())
            leak_str = f"{len(positive_slopes)} positive slope(s), max {max_slope:.2f} MB/min"
        else:
            leak_str = "no positive slopes"
        console.print(
            f"  [green]Duration:[/green] {_format_duration(active_dur)} active + "
            f"{_format_duration(drain_dur)} drain + {_format_duration(cooldown_dur)} cooldown"
            f" -- {leak_str}"
        )


def _get_display_name(container: str) -> str:
    """Get display name for a container."""
    return CONTAINER_CONFIG.get(container, {}).get("display_name", container)


def _print_baseline_health_table(calibration_dict: dict[str, Any]) -> None:
    """Print baseline health thresholds immediately after baseline completes."""
    health_thresholds = calibration_dict.get("health_thresholds", {})
    if health_thresholds:
        console.print("\n[bold]Baseline Health Calibration:[/bold]")
        cal_table = Table(show_header=True, header_style="bold")
        cal_table.add_column("Service")
        cal_table.add_column("Baseline p95 (ms)", justify="right")
        cal_table.add_column("Degraded Threshold (ms)", justify="right")
        cal_table.add_column("Unhealthy Threshold (ms)", justify="right")
        for svc_name in sorted(health_thresholds.keys()):
            th = health_thresholds[svc_name]
            cal_table.add_row(
                svc_name,
                f"{th.get('baseline_p95', 0):.1f}",
                f"{th.get('degraded', 0):.0f}",
                f"{th.get('unhealthy', 0):.0f}",
            )
        console.print(cal_table)

    rtr_threshold = calibration_dict.get("rtr_threshold")
    rtr_mean = calibration_dict.get("rtr_mean")
    rtr_source = calibration_dict.get("rtr_threshold_source", "unknown")
    if rtr_threshold is not None:
        console.print(
            f"  RTR threshold: {rtr_threshold:.4f}x (mean={rtr_mean:.4f}x, {rtr_source})"
            if rtr_mean is not None
            else f"  RTR threshold: {rtr_threshold:.4f}x ({rtr_source})"
        )


def _print_summary(results: dict[str, Any], summary: TestSummary | None = None) -> None:
    """Print test summary with key metrics, scenario table, and health data."""
    console.print("\n")
    console.rule("[bold]Test Summary[/bold]")

    if not summary:
        _print_summary_legacy(results)
        return

    # --- Key Metrics ---
    km = summary.key_metrics
    if km:
        console.print("\n[bold]Key Metrics:[/bold]")
        metrics_table = Table(show_header=False, box=None, padding=(0, 2))
        metrics_table.add_column(style="dim")
        metrics_table.add_column(style="bold")
        metrics_table.add_column(style="dim")
        metrics_table.add_column(style="bold")

        metrics_table.add_row(
            "Max Agents:",
            str(km.max_agents_queued) if km.max_agents_queued else "N/A",
            "Max Speed:",
            f"{km.max_speed_achieved}x" if km.max_speed_achieved else "N/A",
        )

        # Show leak slopes with rates
        leak_count = len(km.leak_rates)
        if km.leak_rates:
            rates_str = ", ".join(f"{name}: {rate:.2f}" for name, rate in km.leak_rates.items())
            leak_display = f"{leak_count} ({rates_str})"
        else:
            leak_display = "0"

        metrics_table.add_row(
            "Leak Slopes:",
            leak_display,
            "RTR Peak:",
            f"{km.rtr_peak:.1f}x" if km.rtr_peak else "N/A",
        )
        metrics_table.add_row(
            "CPU Cores:",
            str(km.available_cores) if km.available_cores else "N/A",
            "Duration:",
            km.total_duration_str,
        )
        console.print(metrics_table)

    # --- Baseline Calibration ---
    calibration_data: dict[str, Any] | None = None
    scenarios = results.get("scenarios", [])
    for s in scenarios:
        if s.get("scenario_name") == "baseline":
            calibration_data = s.get("metadata", {}).get("calibration")
            break

    if calibration_data is not None:
        health_thresholds = calibration_data.get("health_thresholds", {})
        if health_thresholds:
            console.print("\n[bold]Baseline Calibration:[/bold]")
            cal_table = Table(show_header=True, header_style="bold")
            cal_table.add_column("Service")
            cal_table.add_column("Baseline p95 (ms)", justify="right")
            cal_table.add_column("Degraded Threshold", justify="right")
            cal_table.add_column("Unhealthy Threshold", justify="right")
            for svc_name in sorted(health_thresholds.keys()):
                th = health_thresholds[svc_name]
                cal_table.add_row(
                    svc_name,
                    f"{th.get('baseline_p95', 0):.1f}",
                    f"{th.get('degraded', 0):.0f}",
                    f"{th.get('unhealthy', 0):.0f}",
                )
            console.print(cal_table)

        rtr_threshold = calibration_data.get("rtr_threshold")
        rtr_mean = calibration_data.get("rtr_mean")
        rtr_source = calibration_data.get("rtr_threshold_source", "unknown")
        if rtr_threshold is not None:
            console.print(
                f"  RTR threshold: {rtr_threshold:.4f}x " f"(mean={rtr_mean:.4f}x, {rtr_source})"
                if rtr_mean is not None
                else f"  RTR threshold: {rtr_threshold:.4f}x ({rtr_source})"
            )

    # --- Scenario Results Table ---
    if scenarios:
        console.print("\n[bold]Scenario Results:[/bold]")
        scenario_table = Table(show_header=True, header_style="bold")
        scenario_table.add_column("Scenario")
        scenario_table.add_column("Status")
        scenario_table.add_column("Key Result")
        scenario_table.add_column("Duration", justify="right")

        for s in scenarios:
            name = s["scenario_name"]
            aborted_flag = s.get("aborted", False)
            duration_secs = s.get("duration_seconds", 0)

            # Status: stress abort is OK (by design)
            if name == "stress_test":
                status_str = "[green]OK[/green]"
            elif aborted_flag:
                status_str = "[red]ABORT[/red]"
            else:
                status_str = "[green]OK[/green]"

            # Key result per scenario type
            key_result = _scenario_key_result(name, s)

            scenario_table.add_row(
                _format_scenario_name(name),
                status_str,
                key_result,
                _format_duration(duration_secs),
            )

        console.print(scenario_table)

    # --- Container Health Table (aggregated) ---
    if summary.aggregated_container_health:
        console.print("\n[bold]Container Health:[/bold]")

        health_table = Table(show_header=True, header_style="bold")
        health_table.add_column("Container")
        health_table.add_column("Baseline", justify="right")
        health_table.add_column("Peak Mem", justify="right")
        health_table.add_column("Peak CPU", justify="right")
        health_table.add_column("Leak Rate", justify="right")

        for h in summary.aggregated_container_health:
            baseline_str = f"{h.baseline_memory_mb:.0f} MB" if h.baseline_memory_mb else "N/A"
            peak_mem_str = f"{h.peak_memory_mb:.0f} MB ({h.peak_memory_percent:.0f}%)"
            peak_cpu_str = f"{h.peak_cpu_percent:.0f}%"
            leak_str = (
                f"{h.leak_rate_mb_per_min:.2f} MB/min"
                if h.leak_rate_mb_per_min is not None
                else "-"
            )

            health_table.add_row(
                h.display_name,
                baseline_str,
                peak_mem_str,
                peak_cpu_str,
                leak_str,
            )

        console.print(health_table)

    elif summary.container_health:
        # Fallback to legacy health
        _print_legacy_health_table(summary.container_health)

    # --- Speed Scaling Steps ---
    speed_scenarios = [s for s in scenarios if s.get("scenario_name") == "speed_scaling"]
    if speed_scenarios:
        step_results = speed_scenarios[0].get("metadata", {}).get("step_results", [])
        if step_results:
            console.print("\n[bold]Speed Scaling Steps:[/bold]")
            step_table = Table(show_header=True, header_style="bold")
            step_table.add_column("Step", justify="right")
            step_table.add_column("Speed")
            step_table.add_column("Result")

            for step in step_results:
                step_num = step.get("step", "?")
                multiplier = f"{step.get('multiplier', '?')}x"
                hit = step.get("threshold_hit", False)
                trigger = step.get("trigger")
                if hit and trigger:
                    metric = trigger.get("metric", "")
                    value = trigger.get("value", 0)
                    result_str = f"[red]{metric} {value:.2f}x[/red]"
                elif hit:
                    result_str = "[red]THRESHOLD[/red]"
                else:
                    rtr_peak = step.get("rtr_peak")
                    result_str = f"RTR {rtr_peak:.2f}x" if rtr_peak is not None else "-"
                step_table.add_row(str(step_num), multiplier, result_str)

            console.print(step_table)

    # --- Saturation Analysis (USL) ---
    if summary.saturation_family is not None:
        console.print("\n[bold]Saturation Analysis (USL):[/bold]")
        usl_table = Table(show_header=True, header_style="bold")
        usl_table.add_column("Speed")
        usl_table.add_column("N* (Knee)", justify="right")
        usl_table.add_column("X_max (Peak)", justify="right")
        usl_table.add_column("R\u00b2", justify="right")
        usl_table.add_column("Bottleneck")
        usl_table.add_column("Method")

        for curve in summary.saturation_family.curves:
            if curve.usl_fit is not None:
                n_star = f"{curve.usl_fit.n_star:.0f}"
                x_max = f"{curve.usl_fit.x_max:.1f}"
                r2 = f"{curve.usl_fit.r_squared:.3f}"
            else:
                n_star = "-"
                x_max = "-"
                r2 = "-"

            method = curve.knee_point.detection_method if curve.knee_point else "none"
            bottleneck = _get_display_name(curve.resource_bottleneck)

            usl_table.add_row(
                f"{curve.speed_multiplier}x",
                n_star,
                x_max,
                r2,
                bottleneck,
                method,
            )

        console.print(usl_table)

        if summary.saturation_family.best_n_star is not None:
            console.print(
                f"  Best operating point: N*={summary.saturation_family.best_n_star:.0f} "
                f"active trips at {summary.saturation_family.best_speed_multiplier}x"
            )

    # --- Derived Configuration ---
    derived_config = results.get("derived_config", {})
    if derived_config:
        console.print("\n[bold]Derived Configuration:[/bold]")
        duration_agents = derived_config.get("duration_agent_count")
        total_queued = derived_config.get("total_agents_queued")
        if duration_agents and total_queued:
            console.print(
                f"  Duration test agents: {duration_agents} "
                f"(1/50 of {total_queued} total from stress test)"
            )
        duration_speed = derived_config.get("duration_speed_multiplier")
        if duration_speed and duration_agents:
            console.print(
                f"  With {duration_agents} agents, simulation ran reliably "
                f"up to {duration_speed}x speed"
            )
        baseline_rtr_threshold = derived_config.get("baseline_rtr_threshold")
        baseline_rtr_mean = derived_config.get("baseline_rtr_mean")
        baseline_rtr_source = derived_config.get("baseline_rtr_threshold_source")
        if baseline_rtr_threshold is not None:
            mean_str = f", mean={baseline_rtr_mean:.4f}x" if baseline_rtr_mean is not None else ""
            console.print(
                f"  Baseline RTR threshold: {baseline_rtr_threshold:.4f}x"
                f"{mean_str} ({baseline_rtr_source})"
            )


def _print_summary_legacy(results: dict[str, Any]) -> None:
    """Fallback summary when no TestSummary is available."""
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


def _print_legacy_health_table(container_health: list[ContainerHealth]) -> None:
    """Print legacy container health table."""
    console.print("\n[bold]Container Health:[/bold]")

    health_table = Table(show_header=True, header_style="bold")
    health_table.add_column("Container")
    health_table.add_column("Memory", justify="right")
    health_table.add_column("Limit", justify="right")
    health_table.add_column("Usage %", justify="right")
    health_table.add_column("Leak Rate", justify="right")

    for health in container_health:
        leak_str = (
            f"{health.memory_leak_rate_mb_per_min:.2f} MB/min"
            if health.memory_leak_rate_mb_per_min is not None
            else "N/A"
        )
        limit_str = f"{health.memory_limit_mb:.0f} MB" if health.memory_limit_mb > 0 else "N/A"
        percent_str = f"{health.memory_percent:.1f}%" if health.memory_percent > 0 else "N/A"

        health_table.add_row(
            health.display_name,
            f"{health.memory_current_mb:.1f} MB",
            limit_str,
            percent_str,
            leak_str,
        )

    console.print(health_table)


def _format_scenario_name(name: str) -> str:
    """Format scenario name for display."""
    name_map = {
        "baseline": "Baseline",
        "stress_test": "Stress Test",
        "speed_scaling": "Speed Scaling",
        "duration_leak": "Duration Leak",
    }
    return name_map.get(name, name.replace("_", " ").title())


def _scenario_key_result(name: str, scenario: dict[str, Any]) -> str:
    """Extract a concise key result string for a scenario."""
    meta = scenario.get("metadata", {})
    n_samples = len(scenario.get("samples", []))

    if name == "baseline":
        return f"{n_samples} samples"

    elif name == "stress_test":
        total_agents = meta.get("total_agents_queued", 0)
        trigger = meta.get("trigger", {})
        metric = trigger.get("metric", "") if trigger else ""
        if metric == "rtr_collapse":
            return f"{total_agents} agents -> RTR collapse"
        elif metric == "max_duration":
            return f"{total_agents} agents -> time limit"
        elif metric:
            return f"{total_agents} agents -> {metric} trigger"
        return f"{total_agents} agents"

    elif name == "speed_scaling":
        max_speed = meta.get("max_speed_achieved", 0)
        total_steps = meta.get("total_steps", 0)
        stopped = meta.get("stopped_by_threshold", False)
        if stopped:
            return f"{max_speed}x max ({total_steps} steps, threshold)"
        return f"{max_speed}x max ({total_steps} steps)"

    elif name == "duration_leak" or name.startswith("duration_leak_"):
        leak_analysis = meta.get("leak_analysis", {})
        positive_slopes = {
            c: la.get("memory_slope_mb_per_min", 0)
            for c, la in leak_analysis.items()
            if la.get("memory_slope_mb_per_min") is not None
            and la.get("memory_slope_mb_per_min", 0) > 0
        }
        if positive_slopes:
            max_slope = max(positive_slopes.values())
            return f"max slope {max_slope:.2f} MB/min ({len(positive_slopes)} containers)"
        return "no positive slopes"

    return f"{n_samples} samples"


if __name__ == "__main__":
    cli()
