"""Report generation for performance test results."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .findings import (
    ContainerHealthAggregated,
    OverallStatus,
    Severity,
    TestVerdict,
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

    def generate_all(self, results: dict[str, Any], verdict: TestVerdict) -> ReportPaths:
        """Generate all report formats."""
        return ReportPaths(
            markdown=self.generate_markdown(results, verdict),
            html=self.generate_html(results, verdict),
            summary_json=self.generate_summary_json(results, verdict),
        )

    # ─────────────────────────────────────────────────────────
    #  Markdown Report
    # ─────────────────────────────────────────────────────────

    def generate_markdown(self, results: dict[str, Any], verdict: TestVerdict) -> Path:
        """Generate Markdown report with key metrics, per-scenario details, and aggregated findings."""
        test_id = results.get("test_id", "unknown")
        started_at = results.get("started_at", "")
        completed_at = results.get("completed_at", "")
        scenarios = results.get("scenarios", [])

        duration_str = _calc_duration_str(started_at, completed_at)
        status_text = verdict.overall_status.value.upper()

        lines: list[str] = [
            "# Performance Test Report",
            "",
        ]

        # ── Key Metrics ──
        km = verdict.key_metrics
        if km:
            lines.extend(
                [
                    "## Key Metrics",
                    "",
                    "| Metric | Value |",
                    "|--------|-------|",
                    f"| Max Agents | {km.max_agents_queued or 'N/A'} |",
                    f"| Max Speed | {f'{km.max_speed_achieved}x' if km.max_speed_achieved else 'N/A'} |",
                    f"| Leaks | {len(km.leak_containers)} ({', '.join(km.leak_containers) if km.leak_containers else 'none'}) |",
                    f"| RTR Peak | {f'{km.rtr_peak:.2f}x' if km.rtr_peak else 'N/A'} |",
                    f"| CPU Cores | {km.available_cores or 'N/A'} |",
                    f"| Duration | {km.total_duration_str} |",
                    f"| Status | **{status_text}** |",
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
                    f"| Status | **{status_text}** |",
                    "",
                ]
            )

        # ── Scenario Details ──
        lines.extend(["## Scenario Details", ""])

        for scenario in scenarios:
            name = scenario["scenario_name"]
            lines.extend(self._md_scenario_section(name, scenario))

        # ── Aggregated Findings ──
        if verdict.aggregated_findings:
            n_crit = verdict.aggregated_critical_count
            n_warn = verdict.aggregated_warning_count
            lines.extend(
                [
                    f"## Findings ({n_crit} critical, {n_warn} warnings)",
                    "",
                ]
            )
            for af in verdict.aggregated_findings:
                icon = "X" if af.severity == Severity.CRITICAL else "!"
                n_sc = len(af.scenarios_exceeded)
                lines.append(
                    f"- **{icon}** {af.display_name} "
                    f"({af.category.value}): {af.worst_value:.1f} "
                    f"({af.worst_scenario}) -- exceeded in {n_sc} scenario(s)"
                )
                if af.recommendation:
                    lines.append(f"  - {af.recommendation}")
            lines.append("")
        elif verdict.findings:
            lines.extend(["## Findings", ""])
            for f in verdict.findings:
                lines.append(f"- **{f.severity.value.upper()}**: {f.message}")
            lines.append("")

        # ── Container Health ──
        lines.extend(self._md_container_health(verdict))

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

        # ── Recommendations ──
        if verdict.recommendations:
            lines.extend(["## Recommendations", ""])
            for rec in verdict.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        # ── Charts ──
        lines.extend(
            ["## Charts", "", "See [charts/index.html](charts/index.html) for all charts.", ""]
        )

        report_path = self.output_dir / "report.md"
        with open(report_path, "w") as f:
            f.write("\n".join(lines))
        return report_path

    def _md_scenario_section(self, name: str, scenario: dict[str, Any]) -> list[str]:
        """Generate markdown subsection for a scenario."""
        from .statistics import calculate_all_container_stats
        from ..config import CONTAINER_CONFIG

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

        elif name == "stress_test":
            total_agents = meta.get("total_agents_queued", 0)
            batch_count = meta.get("batch_count", 0)
            trigger = meta.get("trigger", {})
            trigger_str = ""
            if trigger:
                metric = trigger.get("metric", "")
                value = trigger.get("value", 0)
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
                        result = "PASS"
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

            # Leak verdicts
            leak_analysis = meta.get("leak_analysis", {})
            if leak_analysis:
                lines.extend(
                    [
                        "| Container | Leak Rate (MB/min) | Leak? |",
                        "|-----------|-------------------|-------|",
                    ]
                )
                for c, la in sorted(leak_analysis.items()):
                    dn = CONTAINER_CONFIG.get(c, {}).get("display_name", c)
                    rate = la.get("memory_slope_mb_per_min", 0)
                    detected = "YES" if la.get("memory_leak_detected", False) else "no"
                    lines.append(f"| {dn} | {rate:.3f} | {detected} |")
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

    def _md_container_health(self, verdict: TestVerdict) -> list[str]:
        """Generate markdown container health table."""
        lines = ["## Container Health", ""]

        if verdict.aggregated_container_health:
            lines.extend(
                [
                    "| Container | Baseline | Peak Mem | Peak CPU | Leak Rate | Status |",
                    "|-----------|----------|----------|----------|-----------|--------|",
                ]
            )
            for h in verdict.aggregated_container_health:
                baseline = f"{h.baseline_memory_mb:.0f} MB" if h.baseline_memory_mb else "N/A"
                peak_mem = f"{h.peak_memory_mb:.0f} MB ({h.peak_memory_percent:.0f}%)"
                peak_cpu = f"{h.peak_cpu_percent:.0f}%"
                leak = (
                    f"{h.leak_rate_mb_per_min:.2f} MB/min"
                    if h.leak_rate_mb_per_min is not None
                    else "-"
                )
                status = {"healthy": "OK", "warning": "WARN", "critical": "CRIT"}.get(
                    h.status, h.status
                )
                lines.append(
                    f"| {h.display_name} | {baseline} | {peak_mem} | "
                    f"{peak_cpu} | {leak} | {status} |"
                )
            lines.append("")

        elif verdict.container_health:
            lines.extend(
                [
                    "| Container | Memory (MB) | Limit (MB) | Usage % | Leak Rate | CPU Peak | Status |",
                    "|-----------|-------------|------------|---------|-----------|----------|--------|",
                ]
            )
            for h in verdict.container_health:
                leak = (
                    f"{h.memory_leak_rate_mb_per_min:.2f} MB/min"
                    if h.memory_leak_rate_mb_per_min is not None
                    else "N/A"
                )
                limit = f"{h.memory_limit_mb:.0f}" if h.memory_limit_mb > 0 else "N/A"
                pct = f"{h.memory_percent:.1f}%" if h.memory_percent > 0 else "N/A"
                status = {"healthy": "OK", "warning": "WARN", "critical": "CRIT"}.get(
                    h.status, h.status
                )
                lines.append(
                    f"| {h.display_name} | {h.memory_current_mb:.1f} | {limit} | "
                    f"{pct} | {leak} | {h.cpu_peak_percent:.1f}% | {status} |"
                )
            lines.append("")
        else:
            lines.extend(["No container health data available.", ""])

        return lines

    # ─────────────────────────────────────────────────────────
    #  HTML Report
    # ─────────────────────────────────────────────────────────

    def generate_html(self, results: dict[str, Any], verdict: TestVerdict) -> Path:
        """Generate HTML dashboard report with inline interactive charts."""
        test_id = results.get("test_id", "unknown")
        started_at = results.get("started_at", "")
        completed_at = results.get("completed_at", "")
        scenarios = results.get("scenarios", [])

        duration_str = _calc_duration_str(started_at, completed_at)
        km = verdict.key_metrics

        status_colors = {
            OverallStatus.PASS: ("#28a745", "PASS"),
            OverallStatus.WARNING: ("#ffc107", "WARNING"),
            OverallStatus.FAIL: ("#dc3545", "FAIL"),
        }
        status_color, status_text = status_colors.get(
            verdict.overall_status, ("#6c757d", "UNKNOWN")
        )

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
        .status-pass {{ color: #28a745; }}
        .status-warning {{ color: #ffc107; }}
        .status-fail {{ color: #dc3545; }}
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
        .finding {{
            background: white; border-left: 4px solid;
            padding: 12px 15px; margin-bottom: 8px;
            border-radius: 0 8px 8px 0;
        }}
        .finding-critical {{ border-color: #dc3545; background: #fff5f5; }}
        .finding-warning {{ border-color: #ffc107; background: #fffbf0; }}
        .finding h4 {{ margin-bottom: 3px; }}
        .finding .details {{ font-size: 0.85rem; color: #666; }}
        .severity-badge {{
            display: inline-block; padding: 2px 10px;
            border-radius: 12px; font-size: 0.75rem; font-weight: 600;
        }}
        .badge-critical {{ background: #f8d7da; color: #721c24; }}
        .badge-warning {{ background: #fff3cd; color: #856404; }}
        table {{
            width: 100%; border-collapse: collapse;
            background: white; border-radius: 8px;
            overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 15px;
        }}
        th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; color: #666; font-size: 0.85rem; }}
        tr:last-child td {{ border-bottom: none; }}
        .status-badge {{
            display: inline-block; padding: 3px 10px;
            border-radius: 20px; font-size: 0.75rem; font-weight: 600;
        }}
        .badge-healthy {{ background: #d4edda; color: #155724; }}
        .badge-warning {{ background: #fff3cd; color: #856404; }}
        .badge-critical {{ background: #f8d7da; color: #721c24; }}
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
            <a href="#findings">Findings</a>
            <a href="#health">Health</a>
            <a href="#recommendations">Recommendations</a>
            <a href="charts/index.html">All Charts</a>
        </nav>
"""

        # ── Key Metrics Hero Cards ──
        html += '        <section id="metrics">\n'
        html += '            <div class="hero-cards">\n'
        html += f'                <div class="card"><h3>Status</h3><div class="value" style="color: {status_color};">{status_text}</div></div>\n'

        if km:
            html += f'                <div class="card"><h3>Max Agents</h3><div class="value">{km.max_agents_queued or "N/A"}</div></div>\n'
            html += f'                <div class="card"><h3>Max Speed</h3><div class="value">{f"{km.max_speed_achieved}x" if km.max_speed_achieved else "N/A"}</div></div>\n'
            html += f'                <div class="card"><h3>Leaks</h3><div class="value">{len(km.leak_containers)}</div></div>\n'
            html += f'                <div class="card"><h3>RTR Peak</h3><div class="value">{f"{km.rtr_peak:.1f}x" if km.rtr_peak else "N/A"}</div></div>\n'
            html += f'                <div class="card"><h3>CPU Cores</h3><div class="value">{km.available_cores or "N/A"}</div></div>\n'
            html += f'                <div class="card"><h3>Duration</h3><div class="value">{km.total_duration_str}</div></div>\n'
        else:
            html += f'                <div class="card"><h3>Duration</h3><div class="value">{duration_str}</div></div>\n'
            html += f'                <div class="card"><h3>Critical</h3><div class="value status-fail">{verdict.critical_count}</div></div>\n'
            html += f'                <div class="card"><h3>Warnings</h3><div class="value status-warning">{verdict.warning_count}</div></div>\n'

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

        # ── Aggregated Findings ──
        html += '        <section id="findings">\n'
        html += "            <h2>Findings</h2>\n"

        if verdict.aggregated_findings:
            for af in verdict.aggregated_findings:
                sev_class = (
                    "finding-critical" if af.severity == Severity.CRITICAL else "finding-warning"
                )
                badge_class = (
                    "badge-critical" if af.severity == Severity.CRITICAL else "badge-warning"
                )
                badge_text = af.severity.value.upper()
                n_sc = len(af.scenarios_exceeded)

                html += f'            <div class="finding {sev_class}">\n'
                html += f'                <h4><span class="severity-badge {badge_class}">{badge_text}</span> {af.display_name} ({af.category.value})</h4>\n'
                html += f'                <div class="details">Peak: {af.worst_value:.1f} ({af.worst_scenario}) | Exceeded in {n_sc} scenario(s)</div>\n'
                if af.recommendation:
                    html += f'                <div class="details">{af.recommendation}</div>\n'
                html += "            </div>\n"
        elif not verdict.findings:
            html += "            <p>No issues detected.</p>\n"
        else:
            for finding in verdict.findings:
                sev_class = f"finding-{finding.severity.value}"
                html += f'            <div class="finding {sev_class}"><h4>{finding.message}</h4></div>\n'

        html += "        </section>\n\n"

        # ── Container Health Table ──
        html += '        <section id="health">\n'
        html += "            <h2>Container Health</h2>\n"

        if verdict.aggregated_container_health:
            html += self._html_aggregated_health_table(verdict.aggregated_container_health)
        elif verdict.container_health:
            html += self._html_legacy_health_table(verdict)
        else:
            html += "            <p>No container health data available.</p>\n"

        html += "        </section>\n\n"

        # ── Recommendations ──
        html += '        <section id="recommendations">\n'
        html += "            <h2>Recommendations</h2>\n"
        if verdict.recommendations:
            html += "            <ul>\n"
            for rec in verdict.recommendations:
                html += f"                <li>{rec}</li>\n"
            html += "            </ul>\n"
        else:
            html += "            <p>No specific recommendations.</p>\n"
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
        for subdir in ["overview", "stress", "speed_scaling", "duration"]:
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

        elif name == "stress_test":
            total = meta.get("total_agents_queued", 0)
            batches = meta.get("batch_count", 0)
            trigger = meta.get("trigger", {})
            trigger_str = ""
            if trigger:
                trigger_str = f" Stopped by <strong>{trigger.get('metric', '')}</strong> at {trigger.get('value', 0):.2f}."
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
                        result = "PASS"
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
        html += "<th>Peak CPU</th><th>Leak Rate</th><th>Status</th>"
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
            badge_class = f"badge-{h.status}"
            status_text = h.status.upper()

            html += f"<tr><td>{h.display_name}</td><td>{baseline}</td>"
            html += f"<td>{peak_mem}</td><td>{peak_cpu}</td><td>{leak}</td>"
            html += f'<td><span class="status-badge {badge_class}">{status_text}</span></td></tr>\n'

        html += "</tbody></table>\n"
        return html

    def _html_legacy_health_table(self, verdict: TestVerdict) -> str:
        """Generate HTML for legacy container health table."""
        html = "<table><thead><tr>"
        html += "<th>Container</th><th>Memory (MB)</th><th>Limit (MB)</th>"
        html += "<th>Usage %</th><th>Leak Rate</th><th>CPU Peak</th><th>Status</th>"
        html += "</tr></thead><tbody>\n"

        for h in verdict.container_health:
            leak = (
                f"{h.memory_leak_rate_mb_per_min:.2f} MB/min"
                if h.memory_leak_rate_mb_per_min is not None
                else "N/A"
            )
            limit = f"{h.memory_limit_mb:.0f}" if h.memory_limit_mb > 0 else "N/A"
            pct = f"{h.memory_percent:.1f}%" if h.memory_percent > 0 else "N/A"
            badge_class = f"badge-{h.status}"
            status_text = h.status.upper()

            html += f"<tr><td>{h.display_name}</td><td>{h.memory_current_mb:.1f}</td>"
            html += f"<td>{limit}</td><td>{pct}</td><td>{leak}</td>"
            html += f"<td>{h.cpu_peak_percent:.1f}%</td>"
            html += f'<td><span class="status-badge {badge_class}">{status_text}</span></td></tr>\n'

        html += "</tbody></table>\n"
        return html

    # ─────────────────────────────────────────────────────────
    #  JSON Summary
    # ─────────────────────────────────────────────────────────

    def generate_summary_json(self, results: dict[str, Any], verdict: TestVerdict) -> Path:
        """Generate structured summary.json."""
        km = verdict.key_metrics
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

        summary: dict[str, Any] = {
            "test_id": results.get("test_id", "unknown"),
            "started_at": results.get("started_at"),
            "completed_at": results.get("completed_at"),
        }

        # Key metrics
        if km:
            summary["key_metrics"] = {
                "max_agents_queued": km.max_agents_queued,
                "max_speed_achieved": km.max_speed_achieved,
                "leak_containers": km.leak_containers,
                "rtr_peak": round(km.rtr_peak, 2) if km.rtr_peak else None,
                "stress_trigger": km.stress_trigger,
                "overall_status": verdict.overall_status.value,
                "critical_count": verdict.aggregated_critical_count,
                "warning_count": verdict.aggregated_warning_count,
                "available_cores": km.available_cores,
            }

        summary["scenario_results"] = scenario_results

        # Aggregated findings
        if verdict.aggregated_findings:
            summary["aggregated_findings"] = [af.to_dict() for af in verdict.aggregated_findings]

        # Aggregated container health
        if verdict.aggregated_container_health:
            summary["container_health"] = [h.to_dict() for h in verdict.aggregated_container_health]

        # Backward compat: keep full verdict
        summary["verdict"] = verdict.to_dict()

        summary_path = self.output_dir / "summary.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
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
        leaks = [c for c, la in leak_analysis.items() if la.get("memory_leak_detected")]
        return {
            "leak_containers": leaks,
            "drain_duration_seconds": meta.get("drain_duration_seconds"),
        }
    return {}
