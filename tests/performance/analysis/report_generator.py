"""Report generation for performance test results."""

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .findings import OverallStatus, Severity, TestVerdict


@dataclass
class ReportPaths:
    """Paths to generated report files."""

    markdown: Path
    html: Path
    summary_json: Path


class ReportGenerator:
    """Generates reports in multiple formats from test results."""

    def __init__(self, output_dir: Path, charts_dir: Path) -> None:
        """Initialize the report generator.

        Args:
            output_dir: Directory to write report files.
            charts_dir: Directory containing generated charts.
        """
        self.output_dir = output_dir
        self.charts_dir = charts_dir

    def generate_all(self, results: dict[str, Any], verdict: TestVerdict) -> ReportPaths:
        """Generate all report formats.

        Args:
            results: Full test results dictionary.
            verdict: Test verdict with findings.

        Returns:
            ReportPaths with paths to generated files.
        """
        return ReportPaths(
            markdown=self.generate_markdown(results, verdict),
            html=self.generate_html(results, verdict),
            summary_json=self.generate_summary_json(results, verdict),
        )

    def generate_markdown(self, results: dict[str, Any], verdict: TestVerdict) -> Path:
        """Generate Markdown report.

        Args:
            results: Full test results dictionary.
            verdict: Test verdict with findings.

        Returns:
            Path to generated report.md file.
        """
        test_id = results.get("test_id", "unknown")
        started_at = results.get("started_at", "")
        completed_at = results.get("completed_at", "")

        # Calculate duration
        duration_str = "N/A"
        if started_at and completed_at:
            try:
                start = datetime.fromisoformat(started_at)
                end = datetime.fromisoformat(completed_at)
                duration = end - start
                duration_str = str(duration).split(".")[0]  # Remove microseconds
            except ValueError:
                pass

        # Status emoji and color hint
        status_map = {
            OverallStatus.PASS: ("PASS", "green"),
            OverallStatus.WARNING: ("WARNING", "yellow"),
            OverallStatus.FAIL: ("FAIL", "red"),
        }
        status_text, _ = status_map.get(verdict.overall_status, ("UNKNOWN", "gray"))

        lines = [
            "# Performance Test Report",
            "",
            "## Test Summary",
            "",
            "| Property | Value |",
            "|----------|-------|",
            f"| Test ID | `{test_id}` |",
            f"| Started | {started_at} |",
            f"| Completed | {completed_at} |",
            f"| Duration | {duration_str} |",
            f"| Status | **{status_text}** |",
            f"| Scenarios Passed | {verdict.scenarios_passed} |",
            f"| Scenarios Failed | {verdict.scenarios_failed} |",
            f"| OOM Events | {verdict.total_oom_events} |",
            "",
        ]

        # Findings section
        lines.append("## Findings")
        lines.append("")

        if not verdict.findings:
            lines.append("No issues detected.")
            lines.append("")
        else:
            # Group by severity
            critical = [f for f in verdict.findings if f.severity == Severity.CRITICAL]
            warnings = [f for f in verdict.findings if f.severity == Severity.WARNING]
            info = [f for f in verdict.findings if f.severity == Severity.INFO]

            if critical:
                lines.append("### Critical Issues")
                lines.append("")
                for finding in critical:
                    lines.append(f"- **{finding.message}**")
                    if finding.scenario_name:
                        lines.append(f"  - Scenario: {finding.scenario_name}")
                    lines.append(
                        f"  - Value: {finding.metric_value:.2f} (threshold: {finding.threshold:.2f})"
                    )
                    if finding.recommendation:
                        lines.append(f"  - Recommendation: {finding.recommendation}")
                lines.append("")

            if warnings:
                lines.append("### Warnings")
                lines.append("")
                for finding in warnings:
                    lines.append(f"- {finding.message}")
                    if finding.scenario_name:
                        lines.append(f"  - Scenario: {finding.scenario_name}")
                lines.append("")

            if info:
                lines.append("### Info")
                lines.append("")
                for finding in info:
                    lines.append(f"- {finding.message}")
                lines.append("")

        # Container Health Table
        lines.append("## Container Health")
        lines.append("")

        if verdict.container_health:
            lines.append(
                "| Container | Memory (MB) | Limit (MB) | Usage % | Leak Rate | CPU Peak | Status |"
            )
            lines.append(
                "|-----------|-------------|------------|---------|-----------|----------|--------|"
            )

            for health in verdict.container_health:
                leak_str = (
                    f"{health.memory_leak_rate_mb_per_min:.2f} MB/min"
                    if health.memory_leak_rate_mb_per_min is not None
                    else "N/A"
                )
                limit_str = f"{health.memory_limit_mb:.0f}" if health.memory_limit_mb > 0 else "N/A"
                percent_str = (
                    f"{health.memory_percent:.1f}%" if health.memory_percent > 0 else "N/A"
                )

                status_emoji = {"healthy": "OK", "warning": "WARN", "critical": "CRIT"}.get(
                    health.status, health.status
                )

                lines.append(
                    f"| {health.display_name} | {health.memory_current_mb:.1f} | {limit_str} | "
                    f"{percent_str} | {leak_str} | {health.cpu_peak_percent:.1f}% | {status_emoji} |"
                )
            lines.append("")
        else:
            lines.append("No container health data available.")
            lines.append("")

        # Derived Configuration (stress → duration agent count)
        derived_config = results.get("derived_config", {})
        if derived_config:
            lines.append("## Derived Configuration")
            lines.append("")
            duration_agents = derived_config.get("duration_agent_count")
            stress_drivers = derived_config.get("stress_drivers_queued")
            if duration_agents and stress_drivers:
                lines.append(
                    f"The duration test used **{duration_agents} agents**, derived from "
                    f"the stress test which queued {stress_drivers} drivers before reaching "
                    "the resource threshold (duration_agents = stress_drivers // 2)."
                )
                lines.append("")

            duration_speed = derived_config.get("duration_speed_multiplier")
            if duration_speed and duration_agents:
                lines.append(
                    f"With **{duration_agents} agents**, the simulation ran reliably "
                    f"up to **{duration_speed}x speed**."
                )
                lines.append("")

        # Recommendations
        if verdict.recommendations:
            lines.append("## Recommendations")
            lines.append("")
            for rec in verdict.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        # Write file
        report_path = self.output_dir / "report.md"
        with open(report_path, "w") as f:
            f.write("\n".join(lines))

        return report_path

    def generate_html(self, results: dict[str, Any], verdict: TestVerdict) -> Path:
        """Generate HTML dashboard report.

        Args:
            results: Full test results dictionary.
            verdict: Test verdict with findings.

        Returns:
            Path to generated report.html file.
        """
        test_id = results.get("test_id", "unknown")
        started_at = results.get("started_at", "")
        completed_at = results.get("completed_at", "")

        # Calculate duration
        duration_str = "N/A"
        if started_at and completed_at:
            try:
                start = datetime.fromisoformat(started_at)
                end = datetime.fromisoformat(completed_at)
                duration = end - start
                duration_str = str(duration).split(".")[0]
            except ValueError:
                pass

        # Status styling
        status_colors = {
            OverallStatus.PASS: ("#28a745", "PASS"),
            OverallStatus.WARNING: ("#ffc107", "WARNING"),
            OverallStatus.FAIL: ("#dc3545", "FAIL"),
        }
        status_color, status_text = status_colors.get(
            verdict.overall_status, ("#6c757d", "UNKNOWN")
        )

        # Build HTML
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Performance Test Report - {test_id}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f8f9fa;
            color: #333;
            line-height: 1.6;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px 20px;
            margin-bottom: 30px;
        }}
        header h1 {{ font-size: 2rem; margin-bottom: 10px; }}
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .card h3 {{ color: #666; font-size: 0.9rem; margin-bottom: 10px; }}
        .card .value {{ font-size: 1.8rem; font-weight: bold; }}
        .status-pass {{ color: #28a745; }}
        .status-warning {{ color: #ffc107; }}
        .status-fail {{ color: #dc3545; }}
        .findings {{ margin-bottom: 30px; }}
        .finding {{
            background: white;
            border-left: 4px solid;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 0 8px 8px 0;
        }}
        .finding-critical {{ border-color: #dc3545; background: #fff5f5; }}
        .finding-warning {{ border-color: #ffc107; background: #fffbf0; }}
        .finding-info {{ border-color: #17a2b8; background: #f0faff; }}
        .finding h4 {{ margin-bottom: 5px; }}
        .finding .details {{ font-size: 0.9rem; color: #666; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; color: #666; }}
        tr:last-child td {{ border-bottom: none; }}
        .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        .badge-healthy {{ background: #d4edda; color: #155724; }}
        .badge-warning {{ background: #fff3cd; color: #856404; }}
        .badge-critical {{ background: #f8d7da; color: #721c24; }}
        section {{ margin-bottom: 40px; }}
        section h2 {{
            font-size: 1.5rem;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #eee;
        }}
        .recommendations ul {{ list-style: none; }}
        .recommendations li {{
            background: white;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .recommendations li:before {{
            content: "\\2192";
            margin-right: 10px;
            color: #667eea;
        }}
        .chart-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }}
        .chart-card {{ background: white; border-radius: 8px; padding: 15px; }}
        .chart-card img {{ max-width: 100%; height: auto; }}
        nav {{
            background: white;
            padding: 10px 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        nav a {{
            margin-right: 20px;
            color: #667eea;
            text-decoration: none;
        }}
        nav a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>Performance Test Report</h1>
            <p>Test ID: {test_id}</p>
        </div>
    </header>

    <div class="container">
        <nav>
            <a href="#summary">Summary</a>
            <a href="#findings">Findings</a>
            <a href="#health">Container Health</a>
            <a href="#recommendations">Recommendations</a>
            <a href="charts/index.html">Charts</a>
        </nav>

        <section id="summary">
            <div class="summary-cards">
                <div class="card">
                    <h3>Status</h3>
                    <div class="value" style="color: {status_color};">{status_text}</div>
                </div>
                <div class="card">
                    <h3>Duration</h3>
                    <div class="value">{duration_str}</div>
                </div>
                <div class="card">
                    <h3>Scenarios</h3>
                    <div class="value">{verdict.scenarios_passed} / {verdict.scenarios_passed + verdict.scenarios_failed}</div>
                </div>
                <div class="card">
                    <h3>Critical Issues</h3>
                    <div class="value status-fail">{verdict.critical_count}</div>
                </div>
                <div class="card">
                    <h3>Warnings</h3>
                    <div class="value status-warning">{verdict.warning_count}</div>
                </div>
                <div class="card">
                    <h3>OOM Events</h3>
                    <div class="value">{verdict.total_oom_events}</div>
                </div>
            </div>
        </section>

        <section id="findings" class="findings">
            <h2>Findings</h2>
"""

        if not verdict.findings:
            html += "            <p>No issues detected.</p>\n"
        else:
            for finding in verdict.findings:
                severity_class = f"finding-{finding.severity.value}"
                html += f"""            <div class="finding {severity_class}">
                <h4>{finding.message}</h4>
                <div class="details">
                    <span>Category: {finding.category.value}</span>
"""
                if finding.scenario_name:
                    html += (
                        f"                    <span> | Scenario: {finding.scenario_name}</span>\n"
                    )
                html += f"""                    <span> | Value: {finding.metric_value:.2f} (threshold: {finding.threshold:.2f})</span>
                </div>
            </div>
"""

        html += """        </section>

        <section id="health">
            <h2>Container Health</h2>
            <table>
                <thead>
                    <tr>
                        <th>Container</th>
                        <th>Memory (MB)</th>
                        <th>Limit (MB)</th>
                        <th>Usage %</th>
                        <th>Leak Rate</th>
                        <th>CPU Peak</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
"""

        for health in verdict.container_health:
            leak_str = (
                f"{health.memory_leak_rate_mb_per_min:.2f} MB/min"
                if health.memory_leak_rate_mb_per_min is not None
                else "N/A"
            )
            limit_str = f"{health.memory_limit_mb:.0f}" if health.memory_limit_mb > 0 else "N/A"
            percent_str = f"{health.memory_percent:.1f}%" if health.memory_percent > 0 else "N/A"

            badge_class = f"badge-{health.status}"
            status_display = health.status.upper()

            html += f"""                    <tr>
                        <td>{health.display_name}</td>
                        <td>{health.memory_current_mb:.1f}</td>
                        <td>{limit_str}</td>
                        <td>{percent_str}</td>
                        <td>{leak_str}</td>
                        <td>{health.cpu_peak_percent:.1f}%</td>
                        <td><span class="status-badge {badge_class}">{status_display}</span></td>
                    </tr>
"""

        html += """                </tbody>
            </table>
        </section>

        <section id="recommendations" class="recommendations">
            <h2>Recommendations</h2>
"""

        if verdict.recommendations:
            html += "            <ul>\n"
            for rec in verdict.recommendations:
                html += f"                <li>{rec}</li>\n"
            html += "            </ul>\n"
        else:
            html += "            <p>No specific recommendations.</p>\n"

        # Embed key charts if available
        html += """        </section>

        <section id="charts">
            <h2>Key Charts</h2>
            <p><a href="charts/index.html">View all charts</a></p>
            <div class="chart-grid">
"""

        # Try to embed heatmaps
        for chart_name in ["cpu_heatmap.png", "memory_heatmap.png"]:
            # Check in overview subdirectory first, then charts root
            chart_paths = [
                self.charts_dir / "overview" / chart_name,
                self.charts_dir / chart_name,
            ]

            for chart_path in chart_paths:
                if chart_path.exists():
                    try:
                        with open(chart_path, "rb") as img_file:
                            img_data = base64.b64encode(img_file.read()).decode("utf-8")
                            title = chart_name.replace("_", " ").replace(".png", "").title()
                            html += f"""                <div class="chart-card">
                    <h3>{title}</h3>
                    <img src="data:image/png;base64,{img_data}" alt="{title}">
                </div>
"""
                    except OSError:
                        pass
                    break

        html += """            </div>
        </section>
    </div>
</body>
</html>
"""

        report_path = self.output_dir / "report.html"
        with open(report_path, "w") as f:
            f.write(html)

        return report_path

    def generate_summary_json(self, results: dict[str, Any], verdict: TestVerdict) -> Path:
        """Generate machine-readable JSON summary.

        Args:
            results: Full test results dictionary.
            verdict: Test verdict with findings.

        Returns:
            Path to generated summary.json file.
        """
        summary = {
            "test_id": results.get("test_id", "unknown"),
            "started_at": results.get("started_at"),
            "completed_at": results.get("completed_at"),
            "verdict": verdict.to_dict(),
        }

        summary_path = self.output_dir / "summary.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        return summary_path
