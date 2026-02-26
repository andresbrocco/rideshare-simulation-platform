"""Report generation for performance test results."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import CONTAINER_CONFIG
from .findings import (
    ContainerHealthAggregated,
    SaturationFamily,
    TestSummary,
)


@dataclass
class ReportPaths:
    """Paths to generated report files."""

    markdown: Path
    html: Path
    summary_json: Path


class ReportGenerator:
    """Generates reports in multiple formats from test results."""

    def __init__(self, output_dir: Path, charts_dir: Path) -> None:
        self.output_dir = output_dir
        self.charts_dir = charts_dir

    def generate_all(self, results: dict[str, Any], summary: TestSummary) -> ReportPaths:
        """Generate all report formats."""
        return ReportPaths(
            markdown=self.generate_markdown(results, summary),
            html=self.generate_html(results, summary),
            summary_json=self.generate_summary_json(results, summary),
        )

    # ─────────────────────────────────────────────────────────
    #  Markdown Report
    # ─────────────────────────────────────────────────────────

    def generate_markdown(self, results: dict[str, Any], summary: TestSummary) -> Path:
        """Generate Markdown report with key metrics and per-scenario details."""
        test_id = results.get("test_id", "unknown")
        started_at = results.get("started_at", "")
        completed_at = results.get("completed_at", "")
        scenarios = results.get("scenarios", [])

        duration_str = _calc_duration_str(started_at, completed_at)

        lines: list[str] = [
            "# Performance Test Report",
            "",
        ]

        # ── Key Metrics ──
        km = summary.key_metrics
        if km:
            leak_count = len(km.leak_rates)
            if km.leak_rates:
                rates_str = ", ".join(f"{name}: {rate:.2f}" for name, rate in km.leak_rates.items())
                leak_display = f"{leak_count} ({rates_str})"
            else:
                leak_display = "0 (none)"

            lines.extend(
                [
                    "## Key Metrics",
                    "",
                    "| Metric | Value |",
                    "|--------|-------|",
                    f"| Max Agents | {km.max_agents_queued or 'N/A'} |",
                    f"| Max Speed | {f'{km.max_speed_achieved}x' if km.max_speed_achieved else 'N/A'} |",
                    f"| Leak Slopes | {leak_display} |",
                    f"| RTR Peak | {f'{km.rtr_peak:.2f}x' if km.rtr_peak else 'N/A'} |",
                    f"| CPU Cores | {km.available_cores or 'N/A'} |",
                    f"| Duration | {km.total_duration_str} |",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "## Test Summary",
                    "",
                    "| Property | Value |",
                    "|----------|-------|",
                    f"| Test ID | `{test_id}` |",
                    f"| Started | {started_at} |",
                    f"| Completed | {completed_at} |",
                    f"| Duration | {duration_str} |",
                    "",
                ]
            )

        # ── Saturation Analysis ──
        lines.extend(self._md_saturation_analysis(summary))

        # ── Scenario Details ──
        lines.extend(["## Scenario Details", ""])

        for scenario in scenarios:
            name = scenario["scenario_name"]
            lines.extend(self._md_scenario_section(name, scenario))

        # ── Container Health ──
        lines.extend(self._md_container_health(summary))

        # ── Health Latency ──
        lines.extend(self._md_health_latency(summary))

        # ── Performance Index Thresholds ──
        lines.extend(self._md_performance_index_thresholds(summary))

        # ── Derived Configuration ──
        derived_config = results.get("derived_config", {})
        if derived_config:
            lines.extend(["## Derived Configuration", ""])
            da = derived_config.get("duration_agent_count")
            tq = derived_config.get("total_agents_queued")
            if da and tq:
                lines.append(f"Duration test used **{da} agents** (half of {tq} from stress test).")
            ds = derived_config.get("duration_speed_multiplier")
            if ds and da:
                lines.append(f"With **{da} agents**, reliable up to **{ds}x speed**.")
            lines.append("")

        # ── Charts ──
        lines.extend(
            [
                "## Charts",
                "",
                "See [charts/index.html](charts/index.html) for all charts.",
                "",
            ]
        )

        report_path = self.output_dir / "report.md"
        with open(report_path, "w") as f:
            f.write("\n".join(lines))
        return report_path

    def _md_scenario_section(self, name: str, scenario: dict[str, Any]) -> list[str]:
        """Generate markdown subsection for a scenario."""
        from .statistics import calculate_all_container_stats

        lines: list[str] = []
        display_name = {
            "baseline": "Baseline",
            "stress_test": "Stress Test",
            "speed_scaling": "Speed Scaling",
            "duration_leak": "Duration / Leak Detection",
        }.get(name, name.replace("_", " ").title())

        lines.extend([f"### {display_name}", ""])

        meta = scenario.get("metadata", {})
        samples = scenario.get("samples", [])
        duration = scenario.get("duration_seconds", 0)
        n_samples = len(samples)

        if name == "baseline":
            stats = calculate_all_container_stats(samples)
            if stats:
                lines.extend(
                    [
                        f"**{n_samples} samples** over {_fmt_duration(duration)}.",
                        "",
                        "| Container | Idle Memory (MB) | Idle CPU % |",
                        "|-----------|------------------|-----------|",
                    ]
                )
                for c_name, s in sorted(stats.items(), key=lambda x: -x[1].memory_mean):
                    dn = CONTAINER_CONFIG.get(c_name, {}).get("display_name", c_name)
                    lines.append(f"| {dn} | {s.memory_mean:.0f} | {s.cpu_mean:.1f} |")
                lines.append("")

            # Calibration thresholds
            calibration = meta.get("calibration")
            if calibration is not None:
                health_thresholds = calibration.get("health_thresholds", {})
                if health_thresholds:
                    lines.extend(
                        [
                            "#### Baseline Health Latency Calibration",
                            "",
                            "| Service | Baseline p95 (ms) | Degraded Threshold | "
                            "Unhealthy Threshold |",
                            "|---------|-------------------|-------------------|"
                            "---------------------|",
                        ]
                    )
                    for svc_name in sorted(health_thresholds.keys()):
                        th = health_thresholds[svc_name]
                        lines.append(
                            f"| {svc_name} | {th.get('baseline_p95', 0):.1f} | "
                            f"{th.get('degraded', 0):.0f} | {th.get('unhealthy', 0):.0f} |"
                        )
                    lines.append("")

                rtr_threshold = calibration.get("rtr_threshold")
                rtr_mean = calibration.get("rtr_mean")
                rtr_source = calibration.get("rtr_threshold_source", "unknown")
                if rtr_threshold is not None:
                    mean_str = f" (mean={rtr_mean:.4f}x)" if rtr_mean is not None else ""
                    lines.append(
                        f"RTR threshold: **{rtr_threshold:.4f}x**{mean_str} ({rtr_source})"
                    )
                    lines.append("")

        elif name == "stress_test":
            total_agents = meta.get("total_agents_queued", 0)
            batch_count = meta.get("batch_count", 0)
            trigger = meta.get("trigger", {})
            trigger_str = ""
            if trigger:
                metric = trigger.get("metric", "")
                value = trigger.get("value", 0)
                if metric == "rtr_collapse":
                    trigger_str = f"Stopped by **RTR collapse** at {value:.4f}"
                elif metric == "max_duration":
                    trigger_str = f"Stopped by **time limit** ({value:.0f}s)"
                else:
                    trigger_str = f"Stopped by **{metric}** at {value:.2f}"

            lines.extend(
                [
                    f"**{total_agents} agents** queued in {batch_count} batches "
                    f"over {_fmt_duration(duration)}.",
                    "",
                ]
            )
            if trigger_str:
                lines.append(f"{trigger_str}")
                lines.append("")

            # Priority container peaks
            peak_values = meta.get("peak_values", {})
            if peak_values:
                lines.extend(
                    [
                        "| Container | Peak CPU % | Peak Memory % |",
                        "|-----------|-----------|---------------|",
                    ]
                )
                priority = [
                    "rideshare-simulation",
                    "rideshare-kafka",
                    "rideshare-redis",
                    "rideshare-osrm",
                    "rideshare-stream-processor",
                ]
                for c in priority:
                    if c in peak_values:
                        dn = CONTAINER_CONFIG.get(c, {}).get("display_name", c)
                        pv = peak_values[c]
                        lines.append(
                            f"| {dn} | {pv.get('cpu_percent', 0):.1f} | "
                            f"{pv.get('memory_percent', 0):.1f} |"
                        )
                lines.append("")

        elif name == "speed_scaling":
            step_results = meta.get("step_results", [])
            max_speed = meta.get("max_speed_achieved", 0)
            total_steps = meta.get("total_steps", 0)
            stopped = meta.get("stopped_by_threshold", False)

            lines.extend(
                [
                    f"**{total_steps} steps**, max achieved **{max_speed}x** "
                    f"over {_fmt_duration(duration)}.",
                    "",
                ]
            )
            if stopped:
                lines.append("Stopped by threshold.")
                lines.append("")

            if step_results:
                lines.extend(
                    [
                        "| Step | Speed | Result |",
                        "|------|-------|--------|",
                    ]
                )
                for step in step_results:
                    hit = step.get("threshold_hit", False)
                    trigger = step.get("trigger")
                    if hit and trigger:
                        metric = trigger.get("metric", "")
                        value = trigger.get("value", 0)
                        result = f"{metric} {value:.2f}x"
                    elif hit:
                        result = "THRESHOLD"
                    else:
                        rtr_peak = step.get("rtr_peak")
                        result = f"RTR {rtr_peak:.2f}x" if rtr_peak is not None else "-"
                    lines.append(
                        f"| {step.get('step', '?')} | {step.get('multiplier', '?')}x | {result} |"
                    )
                lines.append("")

        elif name == "duration_leak" or name.startswith("duration_leak_"):
            phase_ts = meta.get("phase_timestamps", {})
            active_dur = phase_ts.get("active_end", 0) - phase_ts.get("active_start", 0)
            drain_dur = meta.get("drain_duration_seconds", 0)
            cooldown_dur = phase_ts.get("cooldown_end", 0) - phase_ts.get("cooldown_start", 0)

            lines.extend(
                [
                    f"**{_fmt_duration(active_dur)} active** + "
                    f"**{_fmt_duration(drain_dur)} drain** + "
                    f"**{_fmt_duration(cooldown_dur)} cooldown**.",
                    "",
                ]
            )

            # Leak slopes (raw data, no binary judgment)
            leak_analysis = meta.get("leak_analysis", {})
            if leak_analysis:
                lines.extend(
                    [
                        "| Container | Slope (MB/min) |",
                        "|-----------|---------------|",
                    ]
                )
                for c, la in sorted(leak_analysis.items()):
                    dn = CONTAINER_CONFIG.get(c, {}).get("display_name", c)
                    rate = la.get("memory_slope_mb_per_min", 0)
                    lines.append(f"| {dn} | {rate:.3f} |")
                lines.append("")

            # Cooldown analysis
            cooldown_analysis = meta.get("cooldown_analysis", {})
            if cooldown_analysis:
                lines.extend(
                    [
                        "| Container | Active End (MB) | Cooldown End (MB) | Released? |",
                        "|-----------|----------------|------------------|-----------|",
                    ]
                )
                for c, ca in sorted(cooldown_analysis.items()):
                    dn = CONTAINER_CONFIG.get(c, {}).get("display_name", c)
                    ae = ca.get("active_end_mb", 0)
                    ce = ca.get("cooldown_end_mb", 0)
                    released = "yes" if ca.get("memory_released", False) else "NO"
                    lines.append(f"| {dn} | {ae:.0f} | {ce:.0f} | {released} |")
                lines.append("")

        return lines

    def _md_container_health(self, summary: TestSummary) -> list[str]:
        """Generate markdown container health table."""
        lines = ["## Container Health", ""]

        if summary.aggregated_container_health:
            lines.extend(
                [
                    "| Container | Baseline | Peak Mem | Peak CPU | Leak Rate |",
                    "|-----------|----------|----------|----------|-----------|",
                ]
            )
            for h in summary.aggregated_container_health:
                baseline = f"{h.baseline_memory_mb:.0f} MB" if h.baseline_memory_mb else "N/A"
                peak_mem = f"{h.peak_memory_mb:.0f} MB ({h.peak_memory_percent:.0f}%)"
                peak_cpu = f"{h.peak_cpu_percent:.0f}%"
                leak = (
                    f"{h.leak_rate_mb_per_min:.2f} MB/min"
                    if h.leak_rate_mb_per_min is not None
                    else "-"
                )
                lines.append(
                    f"| {h.display_name} | {baseline} | {peak_mem} | " f"{peak_cpu} | {leak} |"
                )
            lines.append("")

        elif summary.container_health:
            lines.extend(
                [
                    "| Container | Memory (MB) | Limit (MB) | Usage % | Leak Rate | CPU Peak |",
                    "|-----------|-------------|------------|---------|-----------|----------|",
                ]
            )
            for h in summary.container_health:
                leak = (
                    f"{h.memory_leak_rate_mb_per_min:.2f} MB/min"
                    if h.memory_leak_rate_mb_per_min is not None
                    else "N/A"
                )
                limit = f"{h.memory_limit_mb:.0f}" if h.memory_limit_mb > 0 else "N/A"
                pct = f"{h.memory_percent:.1f}%" if h.memory_percent > 0 else "N/A"
                lines.append(
                    f"| {h.display_name} | {h.memory_current_mb:.1f} | {limit} | "
                    f"{pct} | {leak} | {h.cpu_peak_percent:.1f}% |"
                )
            lines.append("")
        else:
            lines.extend(["No container health data available.", ""])

        return lines

    def _md_health_latency(self, summary: TestSummary) -> list[str]:
        """Generate markdown health latency and suggested thresholds tables."""
        lines: list[str] = []

        if summary.service_health_latency:
            lines.extend(
                [
                    "## Service Health Latency",
                    "",
                    "| Service | Baseline p95 (ms) | Stressed p95 (ms) | Peak (ms) | "
                    "Degraded Threshold | Unhealthy Threshold | Source |",
                    "|---------|-------------------|-------------------|-----------|"
                    "-------------------|---------------------|--------|",
                ]
            )
            for h in summary.service_health_latency:
                baseline = f"{h.baseline_latency_p95:.1f}" if h.baseline_latency_p95 else "N/A"
                stressed = f"{h.stressed_latency_p95:.1f}" if h.stressed_latency_p95 else "N/A"
                peak = f"{h.peak_latency_ms:.1f}" if h.peak_latency_ms else "N/A"
                degraded = f"{h.threshold_degraded:.0f}" if h.threshold_degraded else "N/A"
                unhealthy = f"{h.threshold_unhealthy:.0f}" if h.threshold_unhealthy else "N/A"
                lines.append(
                    f"| {h.service_name} | {baseline} | {stressed} | {peak} | "
                    f"{degraded} | {unhealthy} | {h.threshold_source} |"
                )
            lines.append("")

        if summary.suggested_thresholds:
            lines.extend(
                [
                    "### Suggested Thresholds",
                    "",
                    "| Service | Current Degraded | Suggested Degraded | "
                    "Current Unhealthy | Suggested Unhealthy | Based On |",
                    "|---------|-----------------|-------------------|"
                    "------------------|---------------------|----------|",
                ]
            )
            for t in summary.suggested_thresholds:
                cur_deg = f"{t.current_degraded:.0f}" if t.current_degraded else "N/A"
                sug_deg = f"{t.suggested_degraded:.1f}"
                cur_unh = f"{t.current_unhealthy:.0f}" if t.current_unhealthy else "N/A"
                sug_unh = f"{t.suggested_unhealthy:.1f}"
                lines.append(
                    f"| {t.service_name} | {cur_deg} | {sug_deg} | "
                    f"{cur_unh} | {sug_unh} | p95={t.based_on_p95:.1f}ms ({t.based_on_scenario}) |"
                )
            lines.append("")

        return lines

    def _md_performance_index_thresholds(self, summary: TestSummary) -> list[str]:
        """Generate markdown section for performance index thresholds."""
        pit = summary.performance_index_thresholds
        if pit is None:
            return []

        lines: list[str] = [
            "## Performance Index Thresholds",
            "",
            "Empirically-derived saturation divisors for Prometheus recording rules.",
            "",
            "| Parameter | Value | Source |",
            "|-----------|-------|--------|",
            f"| Kafka Consumer Lag Saturation | {pit.kafka_lag_saturation} | "
            f"{pit.source_scenario} ({pit.source_trigger}) |",
            f"| SimPy Event Queue Saturation | {pit.simpy_queue_saturation} | "
            f"{pit.source_scenario} ({pit.source_trigger}) |",
            f"| CPU Saturation % | {pit.cpu_saturation_percent:.1f} | "
            f"{pit.source_scenario} ({pit.source_trigger}) |",
            f"| Memory Saturation % | {pit.memory_saturation_percent:.1f} | "
            f"{pit.source_scenario} ({pit.source_trigger}) |",
            "",
        ]
        return lines

    def _md_saturation_analysis(self, summary: TestSummary) -> list[str]:
        """Generate markdown saturation analysis section."""
        if summary.saturation_family is None:
            return []

        family = summary.saturation_family
        lines: list[str] = ["## Saturation Analysis", ""]
        lines.extend(
            [
                "| Speed | N* (Knee) | X_max (Peak) | R\u00b2 | Bottleneck | Detection |",
                "|-------|-----------|-------------|------|------------|-----------|",
            ]
        )

        for curve in family.curves:
            speed = f"{curve.speed_multiplier}x"
            if curve.usl_fit is not None:
                n_star = f"{curve.usl_fit.n_star:.0f}"
                x_max = f"{curve.usl_fit.x_max:.1f}"
                r2 = f"{curve.usl_fit.r_squared:.3f}"
            else:
                n_star = "-"
                x_max = "-"
                r2 = "-"

            bottleneck = CONTAINER_CONFIG.get(curve.resource_bottleneck, {}).get(
                "display_name", curve.resource_bottleneck
            )
            method = curve.knee_point.detection_method if curve.knee_point else "none"

            lines.append(f"| {speed} | {n_star} | {x_max} | {r2} | {bottleneck} | {method} |")

        lines.append("")

        if family.best_n_star is not None:
            lines.append(
                f"Best operating point: N*={family.best_n_star:.0f} active trips "
                f"at {family.best_speed_multiplier}x"
            )
            lines.append("")

        return lines

    # ─────────────────────────────────────────────────────────
    #  HTML Report
    # ─────────────────────────────────────────────────────────

    def generate_html(self, results: dict[str, Any], summary: TestSummary) -> Path:
        """Generate HTML dashboard report with inline interactive charts."""
        test_id = results.get("test_id", "unknown")
        started_at = results.get("started_at", "")
        completed_at = results.get("completed_at", "")
        scenarios = results.get("scenarios", [])

        duration_str = _calc_duration_str(started_at, completed_at)
        km = summary.key_metrics

        # Collect inline chart fragments
        chart_fragments = self._collect_chart_fragments()

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Performance Test Report - {test_id}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f8f9fa; color: #333; line-height: 1.6;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 30px 20px; margin-bottom: 30px;
        }}
        header h1 {{ font-size: 2rem; margin-bottom: 10px; }}
        .hero-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px; margin-bottom: 30px;
        }}
        .card {{
            background: white; border-radius: 8px; padding: 18px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;
        }}
        .card h3 {{ color: #666; font-size: 0.8rem; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .card .value {{ font-size: 1.6rem; font-weight: bold; }}
        section {{ margin-bottom: 40px; }}
        section h2 {{
            font-size: 1.5rem; margin-bottom: 20px;
            padding-bottom: 10px; border-bottom: 2px solid #eee;
        }}
        details {{ margin-bottom: 15px; }}
        details summary {{
            cursor: pointer; padding: 12px 15px;
            background: white; border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            font-weight: 600; font-size: 1.1rem;
        }}
        details[open] summary {{ border-radius: 8px 8px 0 0; }}
        details .content {{
            background: white; padding: 15px;
            border-radius: 0 0 8px 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%; border-collapse: collapse;
            background: white; border-radius: 8px;
            overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 15px;
        }}
        th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; color: #666; font-size: 0.85rem; }}
        tr:last-child td {{ border-bottom: none; }}
        .chart-embed {{ margin: 15px 0; }}
        nav {{
            background: white; padding: 10px 20px; margin-bottom: 20px;
            border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        nav a {{ margin-right: 20px; color: #667eea; text-decoration: none; }}
        nav a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>Performance Test Report</h1>
            <p>Test ID: {test_id} | {started_at} | Duration: {duration_str}</p>
        </div>
    </header>

    <div class="container">
        <nav>
            <a href="#metrics">Metrics</a>
            <a href="#scenarios">Scenarios</a>
            <a href="#saturation">Saturation</a>
            <a href="#health">Health</a>
            <a href="#health-latency">Latency</a>
            <a href="charts/index.html">All Charts</a>
        </nav>
"""

        # ── Key Metrics Hero Cards ──
        html += '        <section id="metrics">\n'
        html += '            <div class="hero-cards">\n'

        if km:
            html += f'                <div class="card"><h3>Max Agents</h3><div class="value">{km.max_agents_queued or "N/A"}</div></div>\n'
            html += f'                <div class="card"><h3>Max Speed</h3><div class="value">{f"{km.max_speed_achieved}x" if km.max_speed_achieved else "N/A"}</div></div>\n'
            html += f'                <div class="card"><h3>Positive Slopes</h3><div class="value">{len(km.leak_rates)}</div></div>\n'
            html += f'                <div class="card"><h3>RTR Peak</h3><div class="value">{f"{km.rtr_peak:.1f}x" if km.rtr_peak else "N/A"}</div></div>\n'
            html += f'                <div class="card"><h3>CPU Cores</h3><div class="value">{km.available_cores or "N/A"}</div></div>\n'
            html += f'                <div class="card"><h3>Duration</h3><div class="value">{km.total_duration_str}</div></div>\n'
        else:
            html += f'                <div class="card"><h3>Duration</h3><div class="value">{duration_str}</div></div>\n'

        html += "            </div>\n"
        html += "        </section>\n\n"

        # ── Scenario Details (collapsible) ──
        html += '        <section id="scenarios">\n'
        html += "            <h2>Scenario Details</h2>\n"

        for scenario in scenarios:
            name = scenario["scenario_name"]
            display = {
                "baseline": "Baseline",
                "stress_test": "Stress Test",
                "speed_scaling": "Speed Scaling",
                "duration_leak": "Duration / Leak Detection",
            }.get(name, name)

            html += "            <details open>\n"
            html += f"                <summary>{display}</summary>\n"
            html += '                <div class="content">\n'
            html += self._html_scenario_content(name, scenario, chart_fragments)
            html += "                </div>\n"
            html += "            </details>\n"

        html += "        </section>\n\n"

        # ── Container Health Table ──
        html += '        <section id="health">\n'
        html += "            <h2>Container Health</h2>\n"

        if summary.aggregated_container_health:
            html += self._html_aggregated_health_table(summary.aggregated_container_health)
        elif summary.container_health:
            html += self._html_legacy_health_table(summary)
        else:
            html += "            <p>No container health data available.</p>\n"

        html += "        </section>\n"

        # ── Saturation Analysis ──
        if summary.saturation_family is not None:
            html += '\n        <section id="saturation">\n'
            html += "            <h2>Saturation Analysis</h2>\n"
            html += self._html_saturation_table(summary.saturation_family)
            html += "        </section>\n"

        # ── Service Health Latency ──
        if summary.service_health_latency:
            html += '\n        <section id="health-latency">\n'
            html += "            <h2>Service Health Latency</h2>\n"
            html += self._html_health_latency_table(summary)
            html += "        </section>\n"

        html += "    </div>\n</body>\n</html>\n"

        report_path = self.output_dir / "report.html"
        with open(report_path, "w") as f:
            f.write(html)
        return report_path

    def _collect_chart_fragments(self) -> dict[str, str]:
        """Collect inline HTML fragments from generated Plotly charts.

        Returns:
            Dict mapping chart base name to HTML fragment (without full_html wrapper).
        """
        fragments: dict[str, str] = {}
        # Look in subdirectories
        for subdir in ["overview", "stress", "speed_scaling", "duration", "health", "saturation"]:
            chart_dir = self.charts_dir / subdir
            if not chart_dir.exists():
                continue
            for html_file in chart_dir.glob("*.html"):
                try:
                    fragments[html_file.stem] = (
                        f'<iframe src="charts/{subdir}/{html_file.name}" '
                        f'width="100%" height="500" frameborder="0"></iframe>'
                    )
                except OSError:
                    pass
        return fragments

    def _html_scenario_content(
        self, name: str, scenario: dict[str, Any], chart_fragments: dict[str, str]
    ) -> str:
        """Generate HTML content for a scenario section."""
        meta = scenario.get("metadata", {})
        samples = scenario.get("samples", [])
        duration = scenario.get("duration_seconds", 0)
        html = ""

        if name == "baseline":
            html += (
                f"<p><strong>{len(samples)} samples</strong> over {_fmt_duration(duration)}.</p>\n"
            )
            # Embed baseline_resources chart if available
            if "baseline_resources" in chart_fragments:
                html += f'<div class="chart-embed">{chart_fragments["baseline_resources"]}</div>\n'

            # Calibration thresholds
            calibration = meta.get("calibration")
            if calibration is not None:
                health_thresholds = calibration.get("health_thresholds", {})
                if health_thresholds:
                    html += "<h4>Derived Stop-Condition Thresholds</h4>\n"
                    html += "<table><thead><tr>"
                    html += "<th>Service</th><th>Baseline p95 (ms)</th>"
                    html += "<th>Degraded Threshold</th><th>Unhealthy Threshold</th>"
                    html += "</tr></thead><tbody>\n"
                    for svc_name in sorted(health_thresholds.keys()):
                        th = health_thresholds[svc_name]
                        html += (
                            f"<tr><td>{svc_name}</td>"
                            f"<td>{th.get('baseline_p95', 0):.1f}</td>"
                            f"<td>{th.get('degraded', 0):.0f}</td>"
                            f"<td>{th.get('unhealthy', 0):.0f}</td></tr>\n"
                        )
                    html += "</tbody></table>\n"

                rtr_threshold = calibration.get("rtr_threshold")
                rtr_mean = calibration.get("rtr_mean")
                rtr_source = calibration.get("rtr_threshold_source", "unknown")
                if rtr_threshold is not None:
                    mean_str = f" (mean={rtr_mean:.4f}x)" if rtr_mean is not None else ""
                    html += (
                        f"<p>RTR threshold: <strong>{rtr_threshold:.4f}x</strong>"
                        f"{mean_str} ({rtr_source})</p>\n"
                    )

        elif name == "stress_test":
            total = meta.get("total_agents_queued", 0)
            batches = meta.get("batch_count", 0)
            trigger = meta.get("trigger", {})
            trigger_str = ""
            if trigger:
                metric = trigger.get("metric", "")
                value = trigger.get("value", 0)
                if metric == "rtr_collapse":
                    trigger_str = f" Stopped by <strong>RTR collapse</strong> at {value:.4f}."
                elif metric == "max_duration":
                    trigger_str = f" Stopped by <strong>time limit</strong> ({value:.0f}s)."
                else:
                    trigger_str = f" Stopped by <strong>{metric}</strong> at {value:.2f}."
            html += f"<p><strong>{total} agents</strong> in {batches} batches over {_fmt_duration(duration)}.{trigger_str}</p>\n"

            # Embed key stress charts
            for chart_name in [
                "stress_agent_resource",
                "global_cpu_timeline",
                "stress_rtr_timeline",
            ]:
                if chart_name in chart_fragments:
                    html += f'<div class="chart-embed">{chart_fragments[chart_name]}</div>\n'

        elif name == "speed_scaling":
            max_speed = meta.get("max_speed_achieved", 0)
            steps = meta.get("total_steps", 0)
            stopped = meta.get("stopped_by_threshold", False)
            html += f"<p><strong>{steps} steps</strong>, max <strong>{max_speed}x</strong> over {_fmt_duration(duration)}."
            if stopped:
                html += " Stopped by threshold."
            html += "</p>\n"

            # Step results table
            step_results = meta.get("step_results", [])
            if step_results:
                html += "<table><thead><tr><th>Step</th><th>Speed</th><th>Result</th></tr></thead><tbody>\n"
                for step in step_results:
                    hit = step.get("threshold_hit", False)
                    trigger = step.get("trigger")
                    if hit and trigger:
                        result = f'{trigger.get("metric", "")} {trigger.get("value", 0):.2f}x'
                    elif hit:
                        result = "THRESHOLD"
                    else:
                        rtr_peak = step.get("rtr_peak")
                        result = f"RTR {rtr_peak:.2f}x" if rtr_peak is not None else "-"
                    html += f'<tr><td>{step.get("step", "?")}</td><td>{step.get("multiplier", "?")}x</td><td>{result}</td></tr>\n'
                html += "</tbody></table>\n"

            if "speed_rtr" in chart_fragments:
                html += f'<div class="chart-embed">{chart_fragments["speed_rtr"]}</div>\n'

        elif name == "duration_leak" or name.startswith("duration_leak_"):
            phase_ts = meta.get("phase_timestamps", {})
            active_dur = phase_ts.get("active_end", 0) - phase_ts.get("active_start", 0)
            drain_dur = meta.get("drain_duration_seconds", 0)
            cooldown_dur = phase_ts.get("cooldown_end", 0) - phase_ts.get("cooldown_start", 0)
            html += f"<p><strong>{_fmt_duration(active_dur)}</strong> active + <strong>{_fmt_duration(drain_dur)}</strong> drain + <strong>{_fmt_duration(cooldown_dur)}</strong> cooldown.</p>\n"

            # Embed duration charts
            for chart_name in ["duration_timeline_memory", "duration_phase_comparison"]:
                if chart_name in chart_fragments:
                    html += f'<div class="chart-embed">{chart_fragments[chart_name]}</div>\n'

        return html

    def _html_aggregated_health_table(self, health: list[ContainerHealthAggregated]) -> str:
        """Generate HTML for aggregated container health table."""
        html = "<table><thead><tr>"
        html += "<th>Container</th><th>Baseline</th><th>Peak Memory</th>"
        html += "<th>Peak CPU</th><th>Leak Rate</th>"
        html += "</tr></thead><tbody>\n"

        for h in health:
            baseline = f"{h.baseline_memory_mb:.0f} MB" if h.baseline_memory_mb else "N/A"
            peak_mem = f"{h.peak_memory_mb:.0f} MB ({h.peak_memory_percent:.0f}%)"
            peak_cpu = f"{h.peak_cpu_percent:.0f}%"
            leak = (
                f"{h.leak_rate_mb_per_min:.2f} MB/min"
                if h.leak_rate_mb_per_min is not None
                else "-"
            )

            html += f"<tr><td>{h.display_name}</td><td>{baseline}</td>"
            html += f"<td>{peak_mem}</td><td>{peak_cpu}</td><td>{leak}</td></tr>\n"

        html += "</tbody></table>\n"
        return html

    def _html_legacy_health_table(self, summary: TestSummary) -> str:
        """Generate HTML for legacy container health table."""
        html = "<table><thead><tr>"
        html += "<th>Container</th><th>Memory (MB)</th><th>Limit (MB)</th>"
        html += "<th>Usage %</th><th>Leak Rate</th><th>CPU Peak</th>"
        html += "</tr></thead><tbody>\n"

        for h in summary.container_health:
            leak = (
                f"{h.memory_leak_rate_mb_per_min:.2f} MB/min"
                if h.memory_leak_rate_mb_per_min is not None
                else "N/A"
            )
            limit = f"{h.memory_limit_mb:.0f}" if h.memory_limit_mb > 0 else "N/A"
            pct = f"{h.memory_percent:.1f}%" if h.memory_percent > 0 else "N/A"

            html += f"<tr><td>{h.display_name}</td><td>{h.memory_current_mb:.1f}</td>"
            html += f"<td>{limit}</td><td>{pct}</td><td>{leak}</td>"
            html += f"<td>{h.cpu_peak_percent:.1f}%</td></tr>\n"

        html += "</tbody></table>\n"
        return html

    def _html_health_latency_table(self, summary: TestSummary) -> str:
        """Generate HTML for service health latency table."""
        html = "<table><thead><tr>"
        html += "<th>Service</th><th>Baseline p95</th><th>Stressed p95</th>"
        html += "<th>Peak</th><th>Degraded Threshold</th><th>Unhealthy Threshold</th>"
        html += "<th>Source</th>"
        html += "</tr></thead><tbody>\n"

        for h in summary.service_health_latency:
            baseline = f"{h.baseline_latency_p95:.1f} ms" if h.baseline_latency_p95 else "N/A"
            stressed = f"{h.stressed_latency_p95:.1f} ms" if h.stressed_latency_p95 else "N/A"
            peak = f"{h.peak_latency_ms:.1f} ms" if h.peak_latency_ms else "N/A"
            degraded = f"{h.threshold_degraded:.0f} ms" if h.threshold_degraded else "N/A"
            unhealthy = f"{h.threshold_unhealthy:.0f} ms" if h.threshold_unhealthy else "N/A"

            html += f"<tr><td>{h.service_name}</td><td>{baseline}</td>"
            html += f"<td>{stressed}</td><td>{peak}</td>"
            html += f"<td>{degraded}</td><td>{unhealthy}</td>"
            html += f"<td>{h.threshold_source}</td></tr>\n"

        html += "</tbody></table>\n"

        if summary.suggested_thresholds:
            html += "<h3>Suggested Thresholds</h3>\n"
            html += "<table><thead><tr>"
            html += "<th>Service</th><th>Current Degraded</th><th>Suggested Degraded</th>"
            html += "<th>Current Unhealthy</th><th>Suggested Unhealthy</th><th>Based On</th>"
            html += "</tr></thead><tbody>\n"

            for t in summary.suggested_thresholds:
                cur_deg = f"{t.current_degraded:.0f}" if t.current_degraded else "N/A"
                sug_deg = f"{t.suggested_degraded:.1f}"
                cur_unh = f"{t.current_unhealthy:.0f}" if t.current_unhealthy else "N/A"
                sug_unh = f"{t.suggested_unhealthy:.1f}"

                html += f"<tr><td>{t.service_name}</td><td>{cur_deg}</td><td>{sug_deg}</td>"
                html += (
                    f"<td>{cur_unh}</td><td>{sug_unh}</td>"
                    f"<td>p95={t.based_on_p95:.1f}ms ({t.based_on_scenario})</td></tr>\n"
                )

            html += "</tbody></table>\n"

        return html

    def _html_saturation_table(self, family: SaturationFamily) -> str:
        """Generate HTML table for saturation analysis."""
        html = "<table><thead><tr>"
        html += "<th>Speed</th><th>N* (Knee)</th><th>X_max (Peak)</th>"
        html += "<th>R\u00b2</th><th>Bottleneck</th><th>Detection</th>"
        html += "</tr></thead><tbody>\n"

        for curve in family.curves:
            speed = f"{curve.speed_multiplier}x"
            if curve.usl_fit is not None:
                n_star = f"{curve.usl_fit.n_star:.0f}"
                x_max = f"{curve.usl_fit.x_max:.1f}"
                r2 = f"{curve.usl_fit.r_squared:.3f}"
            else:
                n_star = "-"
                x_max = "-"
                r2 = "-"

            bottleneck = CONTAINER_CONFIG.get(curve.resource_bottleneck, {}).get(
                "display_name", curve.resource_bottleneck
            )
            method = curve.knee_point.detection_method if curve.knee_point else "none"

            html += (
                f"<tr><td>{speed}</td><td>{n_star}</td><td>{x_max}</td>"
                f"<td>{r2}</td><td>{bottleneck}</td><td>{method}</td></tr>\n"
            )

        html += "</tbody></table>\n"

        if family.best_n_star is not None:
            html += (
                f"<p>Best operating point: N*={family.best_n_star:.0f} active trips "
                f"at {family.best_speed_multiplier}x</p>\n"
            )

        return html

    # ─────────────────────────────────────────────────────────
    #  JSON Summary
    # ─────────────────────────────────────────────────────────

    def generate_summary_json(self, results: dict[str, Any], summary: TestSummary) -> Path:
        """Generate structured summary.json."""
        km = summary.key_metrics
        scenarios = results.get("scenarios", [])

        # Build scenario results summary
        scenario_results: list[dict[str, Any]] = []
        for s in scenarios:
            name = s["scenario_name"]
            meta = s.get("metadata", {})
            scenario_results.append(
                {
                    "scenario_name": name,
                    "duration_seconds": s.get("duration_seconds", 0),
                    "sample_count": len(s.get("samples", [])),
                    "aborted": s.get("aborted", False),
                    "key_metadata": _extract_scenario_meta_summary(name, meta),
                }
            )

        summary_dict: dict[str, Any] = {
            "test_id": results.get("test_id", "unknown"),
            "started_at": results.get("started_at"),
            "completed_at": results.get("completed_at"),
        }

        # Key metrics
        if km:
            summary_dict["key_metrics"] = {
                "max_agents_queued": km.max_agents_queued,
                "max_speed_achieved": km.max_speed_achieved,
                "leak_rates": {k: round(v, 3) for k, v in km.leak_rates.items()},
                "rtr_peak": round(km.rtr_peak, 2) if km.rtr_peak else None,
                "stress_trigger": km.stress_trigger,
                "available_cores": km.available_cores,
            }

        summary_dict["scenario_results"] = scenario_results

        # Aggregated container health
        if summary.aggregated_container_health:
            summary_dict["container_health"] = [
                h.to_dict() for h in summary.aggregated_container_health
            ]

        # Saturation analysis
        if summary.saturation_family is not None:
            summary_dict["saturation_family"] = summary.saturation_family.to_dict()

        # Performance index thresholds
        if summary.performance_index_thresholds is not None:
            summary_dict["performance_index_thresholds"] = (
                summary.performance_index_thresholds.to_dict()
            )

        # Full summary data
        summary_dict["summary"] = summary.to_dict()

        summary_path = self.output_dir / "summary.json"
        with open(summary_path, "w") as f:
            json.dump(summary_dict, f, indent=2)
        return summary_path


# ─────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────


def _calc_duration_str(started_at: str, completed_at: str) -> str:
    """Calculate duration string from ISO timestamps."""
    if not started_at or not completed_at:
        return "N/A"
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(completed_at)
        return str(end - start).split(".")[0]
    except ValueError:
        return "N/A"


def _fmt_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    minutes = total // 60
    secs = total % 60
    if minutes < 60:
        return f"{minutes}m {secs}s" if secs else f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


def _extract_scenario_meta_summary(name: str, meta: dict[str, Any]) -> dict[str, Any]:
    """Extract key metadata fields per scenario type for summary.json."""
    if name == "stress_test":
        return {
            "total_agents_queued": meta.get("total_agents_queued"),
            "trigger": meta.get("trigger"),
            "batch_count": meta.get("batch_count"),
            "rtr_peak": meta.get("rtr_peak"),
            "available_cores": meta.get("available_cores"),
        }
    elif name == "speed_scaling":
        return {
            "total_steps": meta.get("total_steps"),
            "max_speed_achieved": meta.get("max_speed_achieved"),
            "stopped_by_threshold": meta.get("stopped_by_threshold"),
        }
    elif name == "duration_leak" or name.startswith("duration_leak_"):
        leak_analysis = meta.get("leak_analysis", {})
        leak_rates = {
            c: la.get("memory_slope_mb_per_min", 0)
            for c, la in leak_analysis.items()
            if la.get("memory_slope_mb_per_min") is not None
            and la.get("memory_slope_mb_per_min", 0) > 0
        }
        return {
            "leak_rates": leak_rates,
            "drain_duration_seconds": meta.get("drain_duration_seconds"),
        }
    return {}
