"""Visualization generation for performance test results."""

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..config import CONTAINER_CONFIG
from .resource_model import ResourceModelFitter
from .statistics import calculate_all_container_stats, calculate_stats


class ChartGenerator:
    """Generates charts for performance test analysis.

    Outputs both interactive HTML (Plotly) and static PNG (Matplotlib).
    """

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.charts_dir = output_dir / "charts"
        self.charts_dir.mkdir(parents=True, exist_ok=True)

    def generate_all_charts(self, results: dict[str, Any]) -> list[str]:
        """Generate all charts from test results.

        Args:
            results: Full test results dict.

        Returns:
            List of generated chart file paths.
        """
        generated: list[str] = []

        scenarios = results.get("scenarios", [])

        # Load scaling charts
        load_scenarios = [s for s in scenarios if s["scenario_name"].startswith("load_scaling_")]
        if load_scenarios:
            generated.extend(self.generate_load_scaling_bar(load_scenarios))
            generated.extend(self.generate_load_scaling_line(load_scenarios))
            generated.extend(self.generate_curve_fits(load_scenarios))

        # Duration/leak timeline
        duration_scenarios = [
            s for s in scenarios if s["scenario_name"].startswith("duration_leak_")
        ]
        if duration_scenarios:
            generated.extend(self.generate_duration_timeline(duration_scenarios))

        # Reset comparison
        reset_scenarios = [s for s in scenarios if s["scenario_name"] == "reset_behavior"]
        if reset_scenarios:
            generated.extend(self.generate_reset_comparison(reset_scenarios[0]))

        # CPU heatmap (across all scenarios)
        if scenarios:
            generated.extend(self.generate_cpu_heatmap(scenarios))

        return generated

    def generate_load_scaling_bar(self, load_scenarios: list[dict[str, Any]]) -> list[str]:
        """Generate bar chart of memory usage at each load level.

        Args:
            load_scenarios: List of load scaling scenario results.

        Returns:
            List of generated file paths.
        """
        # Focus containers
        focus = [
            "rideshare-simulation",
            "rideshare-kafka",
            "rideshare-redis",
            "rideshare-osrm",
            "rideshare-stream-processor",
        ]

        # Build data
        data_rows: list[dict[str, Any]] = []

        for scenario in sorted(load_scenarios, key=lambda s: s["scenario_params"]["total_agents"]):
            agent_count = scenario["scenario_params"]["total_agents"]
            samples = scenario.get("samples", [])
            all_stats = calculate_all_container_stats(samples)

            for container in focus:
                if container in all_stats:
                    stats = all_stats[container]
                    display_name = CONTAINER_CONFIG.get(container, {}).get(
                        "display_name", container
                    )
                    data_rows.append(
                        {
                            "Agents": agent_count,
                            "Container": display_name,
                            "Memory (MB)": stats.memory_mean,
                            "Memory Max (MB)": stats.memory_max,
                        }
                    )

        if not data_rows:
            return []

        df = pd.DataFrame(data_rows)

        # Plotly interactive chart
        fig = px.bar(
            df,
            x="Agents",
            y="Memory (MB)",
            color="Container",
            barmode="group",
            title="Memory Usage by Agent Count",
            error_y=df["Memory Max (MB)"] - df["Memory (MB)"],
        )
        fig.update_layout(
            xaxis_title="Total Agents",
            yaxis_title="Memory (MB)",
            legend_title="Service",
        )

        html_path = self.charts_dir / "load_scaling_bar.html"
        fig.write_html(str(html_path))

        # Matplotlib static chart
        fig_mpl, ax = plt.subplots(figsize=(12, 6))
        agent_counts = sorted(df["Agents"].unique())
        containers = df["Container"].unique()
        x = np.arange(len(agent_counts))
        width = 0.15
        multiplier = 0

        for container in containers:
            container_data = df[df["Container"] == container]
            memories = [
                (
                    container_data[container_data["Agents"] == ac]["Memory (MB)"].values[0]
                    if ac in container_data["Agents"].values
                    else 0
                )
                for ac in agent_counts
            ]
            offset = width * multiplier
            ax.bar(x + offset, memories, width, label=container)
            multiplier += 1

        ax.set_xlabel("Total Agents")
        ax.set_ylabel("Memory (MB)")
        ax.set_title("Memory Usage by Agent Count")
        ax.set_xticks(x + width * (len(containers) - 1) / 2)
        ax.set_xticklabels(agent_counts)
        ax.legend(loc="upper left", fontsize="small")
        ax.grid(axis="y", alpha=0.3)

        png_path = self.charts_dir / "load_scaling_bar.png"
        fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
        plt.close(fig_mpl)

        return [str(html_path), str(png_path)]

    def generate_load_scaling_line(self, load_scenarios: list[dict[str, Any]]) -> list[str]:
        """Generate line chart of memory vs agents with trend.

        Args:
            load_scenarios: List of load scaling scenario results.

        Returns:
            List of generated file paths.
        """
        container = "rideshare-simulation"

        # Extract data points
        data_points: list[tuple[int, float]] = []

        for scenario in load_scenarios:
            agent_count = scenario["scenario_params"]["total_agents"]
            samples = scenario.get("samples", [])
            stats = calculate_stats(samples, container)
            if stats:
                data_points.append((agent_count, stats.memory_mean))

        if not data_points:
            return []

        data_points.sort()
        x = [p[0] for p in data_points]
        y = [p[1] for p in data_points]

        # Fit trend line
        fitter = ResourceModelFitter()
        best_fit = fitter.get_best_fit(x, y)

        # Plotly chart
        fig = go.Figure()

        # Actual data
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="markers+lines",
                name="Actual",
                marker=dict(size=10),
            )
        )

        # Trend line
        if best_fit:
            x_trend = np.linspace(min(x), max(x) * 1.2, 50)
            if best_fit.fit_type.value == "linear":
                coeffs = best_fit.coefficients
                y_trend = coeffs["slope"] * x_trend + coeffs["intercept"]
                fig.add_trace(
                    go.Scatter(
                        x=x_trend,
                        y=y_trend,
                        mode="lines",
                        name=f"Trend ({best_fit.formula})",
                        line=dict(dash="dash"),
                    )
                )

        fig.update_layout(
            title=f"Memory Scaling - {CONTAINER_CONFIG.get(container, {}).get('display_name', container)}",
            xaxis_title="Total Agents",
            yaxis_title="Memory (MB)",
        )

        html_path = self.charts_dir / "load_scaling_line.html"
        fig.write_html(str(html_path))

        # Matplotlib version
        fig_mpl, ax = plt.subplots(figsize=(10, 6))
        ax.plot(x, y, "o-", markersize=8, label="Actual")

        if best_fit and best_fit.fit_type.value == "linear":
            coeffs = best_fit.coefficients
            y_trend_mpl = [coeffs["slope"] * xi + coeffs["intercept"] for xi in x]
            ax.plot(x, y_trend_mpl, "--", label=f"Trend: {best_fit.formula}")

        ax.set_xlabel("Total Agents")
        ax.set_ylabel("Memory (MB)")
        ax.set_title("Memory Scaling - Simulation")
        ax.legend()
        ax.grid(alpha=0.3)

        png_path = self.charts_dir / "load_scaling_line.png"
        fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
        plt.close(fig_mpl)

        return [str(html_path), str(png_path)]

    def generate_duration_timeline(self, duration_scenarios: list[dict[str, Any]]) -> list[str]:
        """Generate timeline of memory over duration tests.

        Args:
            duration_scenarios: List of duration test results.

        Returns:
            List of generated file paths.
        """
        container = "rideshare-simulation"

        fig = make_subplots(
            rows=len(duration_scenarios),
            cols=1,
            subplot_titles=[s["scenario_name"] for s in duration_scenarios],
        )

        for i, scenario in enumerate(duration_scenarios, 1):
            samples = scenario.get("samples", [])
            if not samples:
                continue

            timestamps = []
            memory_values = []
            start_time = samples[0]["timestamp"] if samples else 0

            for sample in samples:
                containers = sample.get("containers", {})
                if container in containers:
                    elapsed = (sample["timestamp"] - start_time) / 60  # minutes
                    timestamps.append(elapsed)
                    memory_values.append(containers[container]["memory_used_mb"])

            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=memory_values,
                    mode="lines",
                    name=scenario["scenario_name"],
                ),
                row=i,
                col=1,
            )

        fig.update_layout(
            title="Memory Over Time (Leak Detection)",
            height=300 * len(duration_scenarios),
            showlegend=False,
        )
        fig.update_xaxes(title_text="Time (minutes)")
        fig.update_yaxes(title_text="Memory (MB)")

        html_path = self.charts_dir / "duration_timeline.html"
        fig.write_html(str(html_path))

        # Matplotlib version
        fig_mpl, axes = plt.subplots(
            len(duration_scenarios),
            1,
            figsize=(12, 4 * len(duration_scenarios)),
            squeeze=False,
        )

        for i, scenario in enumerate(duration_scenarios):
            ax = axes[i, 0]
            samples = scenario.get("samples", [])
            if not samples:
                continue

            start_time = samples[0]["timestamp"]
            timestamps = []
            memory_values = []

            for sample in samples:
                containers = sample.get("containers", {})
                if container in containers:
                    elapsed = (sample["timestamp"] - start_time) / 60
                    timestamps.append(elapsed)
                    memory_values.append(containers[container]["memory_used_mb"])

            ax.plot(timestamps, memory_values)
            ax.set_title(scenario["scenario_name"])
            ax.set_xlabel("Time (minutes)")
            ax.set_ylabel("Memory (MB)")
            ax.grid(alpha=0.3)

        plt.tight_layout()
        png_path = self.charts_dir / "duration_timeline.png"
        fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
        plt.close(fig_mpl)

        return [str(html_path), str(png_path)]

    def generate_reset_comparison(self, reset_scenario: dict[str, Any]) -> list[str]:
        """Generate comparison chart for reset behavior.

        Args:
            reset_scenario: Reset behavior scenario result.

        Returns:
            List of generated file paths.
        """
        # Find analysis data in samples
        analysis = None
        for sample in reset_scenario.get("samples", []):
            if "analysis" in sample:
                analysis = sample["analysis"]
                break

        if not analysis:
            return []

        # Build bar chart data
        categories = ["Baseline", "Load Peak", "Post-Reset"]
        values = [
            analysis["baseline_avg_mb"],
            analysis["load_peak_mb"],
            analysis["post_reset_avg_mb"],
        ]
        colors = ["green", "red", "blue"]

        # Plotly
        fig = go.Figure(
            data=[
                go.Bar(
                    x=categories,
                    y=values,
                    marker_color=colors,
                    text=[f"{v:.1f} MB" for v in values],
                    textposition="auto",
                )
            ]
        )

        passed = analysis.get("passed", False)
        status = "PASS" if passed else "FAIL"
        diff = analysis.get("diff_percent", 0)

        fig.update_layout(
            title=f"Reset Behavior - {analysis['container']} ({status}: {diff:+.1f}%)",
            yaxis_title="Memory (MB)",
        )

        html_path = self.charts_dir / "reset_comparison.html"
        fig.write_html(str(html_path))

        # Matplotlib
        fig_mpl, ax = plt.subplots(figsize=(8, 6))
        ax.bar(categories, values, color=colors)
        ax.set_ylabel("Memory (MB)")
        ax.set_title(f"Reset Behavior - {analysis['container']} ({status}: {diff:+.1f}%)")

        for i, v in enumerate(values):
            ax.text(i, v + 1, f"{v:.1f}", ha="center")

        png_path = self.charts_dir / "reset_comparison.png"
        fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
        plt.close(fig_mpl)

        return [str(html_path), str(png_path)]

    def generate_cpu_heatmap(self, scenarios: list[dict[str, Any]]) -> list[str]:
        """Generate CPU usage heatmap across scenarios and containers.

        Args:
            scenarios: List of all scenario results.

        Returns:
            List of generated file paths.
        """
        # Build matrix data
        containers = list(CONTAINER_CONFIG.keys())[:10]  # Top 10 containers
        scenario_names = [s["scenario_name"] for s in scenarios[:8]]  # Top 8 scenarios

        matrix: list[list[float]] = []

        for scenario in scenarios[:8]:
            samples = scenario.get("samples", [])
            all_stats = calculate_all_container_stats(samples)
            row = []
            for container in containers:
                if container in all_stats:
                    row.append(all_stats[container].cpu_mean)
                else:
                    row.append(0)
            matrix.append(row)

        if not matrix:
            return []

        # Get display names
        display_names = [
            CONTAINER_CONFIG.get(c, {}).get("display_name", c)[:15] for c in containers
        ]

        # Plotly heatmap
        fig = go.Figure(
            data=go.Heatmap(
                z=matrix,
                x=display_names,
                y=scenario_names,
                colorscale="RdYlGn_r",
                colorbar_title="CPU %",
            )
        )

        fig.update_layout(
            title="CPU Usage Heatmap",
            xaxis_title="Container",
            yaxis_title="Scenario",
        )

        html_path = self.charts_dir / "cpu_heatmap.html"
        fig.write_html(str(html_path))

        # Matplotlib heatmap
        fig_mpl, ax = plt.subplots(figsize=(12, 8))
        im = ax.imshow(matrix, cmap="RdYlGn_r", aspect="auto")

        ax.set_xticks(np.arange(len(display_names)))
        ax.set_yticks(np.arange(len(scenario_names)))
        ax.set_xticklabels(display_names, rotation=45, ha="right")
        ax.set_yticklabels(scenario_names)

        plt.colorbar(im, ax=ax, label="CPU %")
        ax.set_title("CPU Usage Heatmap")

        png_path = self.charts_dir / "cpu_heatmap.png"
        fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
        plt.close(fig_mpl)

        return [str(html_path), str(png_path)]

    def generate_curve_fits(self, load_scenarios: list[dict[str, Any]]) -> list[str]:
        """Generate scatter plot with curve fits.

        Args:
            load_scenarios: List of load scaling scenario results.

        Returns:
            List of generated file paths.
        """
        container = "rideshare-simulation"

        # Extract data points
        data_points: list[tuple[int, float]] = []

        for scenario in load_scenarios:
            agent_count = scenario["scenario_params"]["total_agents"]
            samples = scenario.get("samples", [])
            stats = calculate_stats(samples, container)
            if stats:
                data_points.append((agent_count, stats.memory_mean))

        if len(data_points) < 2:
            return []

        data_points.sort()
        x = np.array([p[0] for p in data_points])
        y = np.array([p[1] for p in data_points])

        # Fit all models
        fitter = ResourceModelFitter()
        all_fits = fitter.fit_all(x.tolist(), y.tolist())

        if not all_fits:
            return []

        # Plotly chart with all fits
        fig = go.Figure()

        # Actual data
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="markers",
                name="Actual Data",
                marker=dict(size=12),
            )
        )

        # Add each fit
        x_smooth = np.linspace(min(x), max(x) * 1.1, 100)
        colors = ["red", "blue", "green", "orange"]

        for i, fit_result in enumerate(all_fits[:4]):
            # Recalculate predictions for smooth line
            predictions = fit_result.predictions
            if len(predictions) == len(x):
                # Interpolate for smooth line
                from scipy.interpolate import interp1d

                interp = interp1d(x, predictions, kind="linear", fill_value="extrapolate")
                y_smooth = interp(x_smooth)

                fig.add_trace(
                    go.Scatter(
                        x=x_smooth,
                        y=y_smooth,
                        mode="lines",
                        name=f"{fit_result.fit_type.value} (R²={fit_result.r_squared:.3f})",
                        line=dict(color=colors[i], dash="dash" if i > 0 else "solid"),
                    )
                )

        fig.update_layout(
            title=f"Curve Fits - {CONTAINER_CONFIG.get(container, {}).get('display_name', container)}",
            xaxis_title="Total Agents",
            yaxis_title="Memory (MB)",
        )

        html_path = self.charts_dir / "curve_fits.html"
        fig.write_html(str(html_path))

        # Matplotlib version
        fig_mpl, ax = plt.subplots(figsize=(10, 6))
        ax.scatter(x, y, s=100, zorder=5, label="Actual Data")

        for i, fit_result in enumerate(all_fits[:4]):
            predictions = fit_result.predictions
            linestyle = "-" if i == 0 else "--"
            ax.plot(
                x,
                predictions,
                linestyle=linestyle,
                color=colors[i],
                label=f"{fit_result.fit_type.value} (R²={fit_result.r_squared:.3f})",
            )

        ax.set_xlabel("Total Agents")
        ax.set_ylabel("Memory (MB)")
        ax.set_title("Curve Fits - Simulation")
        ax.legend()
        ax.grid(alpha=0.3)

        png_path = self.charts_dir / "curve_fits.png"
        fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
        plt.close(fig_mpl)

        return [str(html_path), str(png_path)]
