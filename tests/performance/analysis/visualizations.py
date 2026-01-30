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
            generated.extend(self.generate_curve_fits(load_scenarios, results))

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

        # Heatmaps (across all scenarios) - both CPU and Memory
        if scenarios:
            generated.extend(self.generate_cpu_heatmap(scenarios))
            generated.extend(self.generate_memory_heatmap(scenarios))

        return generated

    def generate_load_scaling_bar(
        self, load_scenarios: list[dict[str, Any]], max_containers: int = 10
    ) -> list[str]:
        """Generate bar charts of memory usage at each load level for all containers.

        Generates charts in batches if there are more containers than max_containers.

        Args:
            load_scenarios: List of load scaling scenario results.
            max_containers: Maximum containers per chart (default 10).

        Returns:
            List of generated file paths.
        """
        # Discover all containers from samples
        all_containers: set[str] = set()
        for scenario in load_scenarios:
            samples = scenario.get("samples", [])
            for sample in samples:
                all_containers.update(sample.get("containers", {}).keys())

        # Sort with priority containers first
        priority = [
            "rideshare-simulation",
            "rideshare-kafka",
            "rideshare-redis",
            "rideshare-osrm",
            "rideshare-stream-processor",
        ]
        sorted_containers = [c for c in priority if c in all_containers]
        sorted_containers.extend([c for c in sorted(all_containers) if c not in priority])

        generated: list[str] = []

        # Generate charts in batches
        for batch_idx in range(0, len(sorted_containers), max_containers):
            batch_containers = sorted_containers[batch_idx : batch_idx + max_containers]
            batch_suffix = (
                f"_{batch_idx // max_containers + 1}"
                if len(sorted_containers) > max_containers
                else ""
            )

            # Build data for this batch
            data_rows: list[dict[str, Any]] = []

            for scenario in sorted(
                load_scenarios, key=lambda s: s["scenario_params"]["total_agents"]
            ):
                agent_count = scenario["scenario_params"]["total_agents"]
                samples = scenario.get("samples", [])
                all_stats = calculate_all_container_stats(samples)

                for container in batch_containers:
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
                continue

            df = pd.DataFrame(data_rows)

            # Plotly interactive chart
            fig = px.bar(
                df,
                x="Agents",
                y="Memory (MB)",
                color="Container",
                barmode="group",
                title=f"Memory Usage by Agent Count{batch_suffix}",
                error_y=df["Memory Max (MB)"] - df["Memory (MB)"],
            )
            fig.update_layout(
                xaxis_title="Total Agents",
                yaxis_title="Memory (MB)",
                legend_title="Service",
            )

            html_path = self.charts_dir / f"load_scaling_bar{batch_suffix}.html"
            fig.write_html(str(html_path))

            # Matplotlib static chart
            fig_mpl, ax = plt.subplots(figsize=(14, 6))
            agent_counts = sorted(df["Agents"].unique())
            containers = df["Container"].unique()
            x = np.arange(len(agent_counts))
            width = 0.8 / len(containers) if containers.size > 0 else 0.15
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
            ax.set_title(f"Memory Usage by Agent Count{batch_suffix}")
            ax.set_xticks(x + width * (len(containers) - 1) / 2)
            ax.set_xticklabels(agent_counts)
            ax.legend(loc="upper left", fontsize="small", ncol=2)
            ax.grid(axis="y", alpha=0.3)

            png_path = self.charts_dir / f"load_scaling_bar{batch_suffix}.png"
            fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
            plt.close(fig_mpl)

            generated.extend([str(html_path), str(png_path)])

        return generated

    def generate_load_scaling_line(self, load_scenarios: list[dict[str, Any]]) -> list[str]:
        """Generate line charts of memory/CPU vs agents for priority containers.

        Args:
            load_scenarios: List of load scaling scenario results.

        Returns:
            List of generated file paths.
        """
        # Priority containers for individual line charts
        priority = [
            "rideshare-simulation",
            "rideshare-kafka",
            "rideshare-redis",
        ]

        generated: list[str] = []

        for container in priority:
            for metric in ["memory", "cpu"]:
                # Extract data points
                data_points: list[tuple[int, float]] = []

                for scenario in load_scenarios:
                    agent_count = scenario["scenario_params"]["total_agents"]
                    samples = scenario.get("samples", [])
                    stats = calculate_stats(samples, container)
                    if stats:
                        value = stats.memory_mean if metric == "memory" else stats.cpu_mean
                        data_points.append((agent_count, value))

                if not data_points:
                    continue

                data_points.sort()
                x = [p[0] for p in data_points]
                y = [p[1] for p in data_points]

                # Fit trend line
                fitter = ResourceModelFitter()
                best_fit = fitter.get_best_fit(x, y)

                display_name = CONTAINER_CONFIG.get(container, {}).get("display_name", container)
                y_label = "Memory (MB)" if metric == "memory" else "CPU %"
                title = f"{metric.title()} Scaling - {display_name}"

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
                    title=title,
                    xaxis_title="Total Agents",
                    yaxis_title=y_label,
                )

                safe_name = container.replace("rideshare-", "")
                html_path = self.charts_dir / f"load_scaling_line_{safe_name}_{metric}.html"
                fig.write_html(str(html_path))

                # Matplotlib version
                fig_mpl, ax = plt.subplots(figsize=(10, 6))
                ax.plot(x, y, "o-", markersize=8, label="Actual")

                if best_fit and best_fit.fit_type.value == "linear":
                    coeffs = best_fit.coefficients
                    y_trend_mpl = [coeffs["slope"] * xi + coeffs["intercept"] for xi in x]
                    ax.plot(x, y_trend_mpl, "--", label=f"Trend: {best_fit.formula}")

                ax.set_xlabel("Total Agents")
                ax.set_ylabel(y_label)
                ax.set_title(title)
                ax.legend()
                ax.grid(alpha=0.3)

                png_path = self.charts_dir / f"load_scaling_line_{safe_name}_{metric}.png"
                fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
                plt.close(fig_mpl)

                generated.extend([str(html_path), str(png_path)])

        return generated

    def generate_duration_timeline(
        self, duration_scenarios: list[dict[str, Any]], max_containers: int = 8
    ) -> list[str]:
        """Generate timeline charts for memory and CPU over duration tests.

        Generates charts for priority containers, with batching if needed.

        Args:
            duration_scenarios: List of duration test results.
            max_containers: Maximum containers per chart.

        Returns:
            List of generated file paths.
        """
        if not duration_scenarios:
            return []

        # Discover all containers
        all_containers: set[str] = set()
        for scenario in duration_scenarios:
            samples = scenario.get("samples", [])
            for sample in samples:
                all_containers.update(sample.get("containers", {}).keys())

        # Sort with priority first
        priority = [
            "rideshare-simulation",
            "rideshare-kafka",
            "rideshare-redis",
            "rideshare-osrm",
            "rideshare-stream-processor",
        ]
        sorted_containers = [c for c in priority if c in all_containers]
        sorted_containers.extend([c for c in sorted(all_containers) if c not in priority])

        generated: list[str] = []

        # Generate charts for both metrics
        for metric in ["memory", "cpu"]:
            y_label = "Memory (MB)" if metric == "memory" else "CPU %"
            metric_key = "memory_used_mb" if metric == "memory" else "cpu_percent"

            # Generate in batches
            for batch_idx in range(0, len(sorted_containers), max_containers):
                batch_containers = sorted_containers[batch_idx : batch_idx + max_containers]
                batch_suffix = (
                    f"_{batch_idx // max_containers + 1}"
                    if len(sorted_containers) > max_containers
                    else ""
                )

                # Create subplots: one row per container
                fig = make_subplots(
                    rows=len(batch_containers),
                    cols=1,
                    subplot_titles=[
                        CONTAINER_CONFIG.get(c, {}).get("display_name", c) for c in batch_containers
                    ],
                )

                for row_idx, container in enumerate(batch_containers, 1):
                    for scenario in duration_scenarios:
                        samples = scenario.get("samples", [])
                        if not samples:
                            continue

                        timestamps = []
                        values = []
                        start_time = samples[0]["timestamp"] if samples else 0

                        for sample in samples:
                            containers = sample.get("containers", {})
                            if container in containers:
                                elapsed = (sample["timestamp"] - start_time) / 60
                                timestamps.append(elapsed)
                                values.append(containers[container][metric_key])

                        if timestamps:
                            fig.add_trace(
                                go.Scatter(
                                    x=timestamps,
                                    y=values,
                                    mode="lines",
                                    name=scenario["scenario_name"],
                                    showlegend=(row_idx == 1),
                                ),
                                row=row_idx,
                                col=1,
                            )

                fig.update_layout(
                    title=f"{metric.title()} Over Time (Leak Detection){batch_suffix}",
                    height=200 * len(batch_containers),
                )
                fig.update_xaxes(title_text="Time (minutes)")
                fig.update_yaxes(title_text=y_label)

                html_path = self.charts_dir / f"duration_timeline_{metric}{batch_suffix}.html"
                fig.write_html(str(html_path))

                # Matplotlib version
                fig_mpl, axes = plt.subplots(
                    len(batch_containers),
                    1,
                    figsize=(12, 3 * len(batch_containers)),
                    squeeze=False,
                )

                for row_idx, container in enumerate(batch_containers):
                    ax = axes[row_idx, 0]
                    display_name = CONTAINER_CONFIG.get(container, {}).get(
                        "display_name", container
                    )

                    for scenario in duration_scenarios:
                        samples = scenario.get("samples", [])
                        if not samples:
                            continue

                        start_time = samples[0]["timestamp"]
                        timestamps = []
                        values = []

                        for sample in samples:
                            containers = sample.get("containers", {})
                            if container in containers:
                                elapsed = (sample["timestamp"] - start_time) / 60
                                timestamps.append(elapsed)
                                values.append(containers[container][metric_key])

                        if timestamps:
                            ax.plot(timestamps, values, label=scenario["scenario_name"])

                    ax.set_title(display_name)
                    ax.set_xlabel("Time (minutes)")
                    ax.set_ylabel(y_label)
                    ax.grid(alpha=0.3)
                    if row_idx == 0:
                        ax.legend(fontsize="small")

                plt.tight_layout()
                png_path = self.charts_dir / f"duration_timeline_{metric}{batch_suffix}.png"
                fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
                plt.close(fig_mpl)

                generated.extend([str(html_path), str(png_path)])

        return generated

    def generate_reset_comparison(self, reset_scenario: dict[str, Any]) -> list[str]:
        """Generate comparison charts for reset behavior (all containers).

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

        all_containers = analysis.get("all_containers", {})

        if not all_containers:
            return []

        # Priority containers for individual charts
        priority = [
            "rideshare-simulation",
            "rideshare-kafka",
            "rideshare-redis",
        ]

        generated: list[str] = []

        for container in priority:
            if container not in all_containers:
                continue

            data = all_containers[container]
            display_name = CONTAINER_CONFIG.get(container, {}).get("display_name", container)
            safe_name = container.replace("rideshare-", "")

            # Memory chart
            categories = ["Baseline", "Load Peak", "Post-Reset"]
            mem_values = [
                data["baseline_mem_avg_mb"],
                data["load_mem_peak_mb"],
                data["post_reset_mem_avg_mb"],
            ]
            colors = ["green", "red", "blue"]

            passed = data.get("mem_passed", False)
            status = "PASS" if passed else "FAIL"
            diff = data.get("mem_diff_percent", 0)

            # Plotly memory
            fig = go.Figure(
                data=[
                    go.Bar(
                        x=categories,
                        y=mem_values,
                        marker_color=colors,
                        text=[f"{v:.1f} MB" for v in mem_values],
                        textposition="auto",
                    )
                ]
            )
            fig.update_layout(
                title=f"Reset Behavior - {display_name} Memory ({status}: {diff:+.1f}%)",
                yaxis_title="Memory (MB)",
            )

            html_path = self.charts_dir / f"reset_comparison_{safe_name}_memory.html"
            fig.write_html(str(html_path))

            # Matplotlib memory
            fig_mpl, ax = plt.subplots(figsize=(8, 6))
            ax.bar(categories, mem_values, color=colors)
            ax.set_ylabel("Memory (MB)")
            ax.set_title(f"Reset Behavior - {display_name} Memory ({status}: {diff:+.1f}%)")
            for i, v in enumerate(mem_values):
                ax.text(i, v + 1, f"{v:.1f}", ha="center")

            png_path = self.charts_dir / f"reset_comparison_{safe_name}_memory.png"
            fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
            plt.close(fig_mpl)

            generated.extend([str(html_path), str(png_path)])

            # CPU chart
            cpu_values = [
                data["baseline_cpu_avg_percent"],
                data["load_cpu_peak_percent"],
                data["post_reset_cpu_avg_percent"],
            ]

            cpu_passed = data.get("cpu_passed", False)
            cpu_status = "PASS" if cpu_passed else "FAIL"
            cpu_diff = data.get("cpu_diff_percent", 0)

            # Plotly CPU
            fig = go.Figure(
                data=[
                    go.Bar(
                        x=categories,
                        y=cpu_values,
                        marker_color=colors,
                        text=[f"{v:.1f}%" for v in cpu_values],
                        textposition="auto",
                    )
                ]
            )
            fig.update_layout(
                title=f"Reset Behavior - {display_name} CPU ({cpu_status}: {cpu_diff:+.1f}%)",
                yaxis_title="CPU %",
            )

            html_path = self.charts_dir / f"reset_comparison_{safe_name}_cpu.html"
            fig.write_html(str(html_path))

            # Matplotlib CPU
            fig_mpl, ax = plt.subplots(figsize=(8, 6))
            ax.bar(categories, cpu_values, color=colors)
            ax.set_ylabel("CPU %")
            ax.set_title(f"Reset Behavior - {display_name} CPU ({cpu_status}: {cpu_diff:+.1f}%)")
            for i, v in enumerate(cpu_values):
                ax.text(i, v + 1, f"{v:.1f}", ha="center")

            png_path = self.charts_dir / f"reset_comparison_{safe_name}_cpu.png"
            fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
            plt.close(fig_mpl)

            generated.extend([str(html_path), str(png_path)])

        return generated

    def generate_cpu_heatmap(self, scenarios: list[dict[str, Any]]) -> list[str]:
        """Generate CPU usage heatmap across scenarios and all containers.

        Args:
            scenarios: List of all scenario results.

        Returns:
            List of generated file paths.
        """
        # Discover all containers
        all_containers: set[str] = set()
        for scenario in scenarios:
            samples = scenario.get("samples", [])
            for sample in samples:
                all_containers.update(sample.get("containers", {}).keys())

        # Sort with priority first
        priority = [
            "rideshare-simulation",
            "rideshare-kafka",
            "rideshare-redis",
            "rideshare-osrm",
            "rideshare-stream-processor",
        ]
        containers = [c for c in priority if c in all_containers]
        containers.extend([c for c in sorted(all_containers) if c not in priority])

        scenario_names = [s["scenario_name"] for s in scenarios]

        matrix: list[list[float]] = []

        for scenario in scenarios:
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

        # Get display names (truncate for readability)
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
            title="CPU Usage Heatmap (All Containers)",
            xaxis_title="Container",
            yaxis_title="Scenario",
            height=max(400, 50 * len(scenario_names)),
        )

        html_path = self.charts_dir / "cpu_heatmap.html"
        fig.write_html(str(html_path))

        # Matplotlib heatmap
        fig_mpl, ax = plt.subplots(
            figsize=(max(12, len(containers) * 0.8), max(8, len(scenario_names) * 0.5))
        )
        im = ax.imshow(matrix, cmap="RdYlGn_r", aspect="auto")

        ax.set_xticks(np.arange(len(display_names)))
        ax.set_yticks(np.arange(len(scenario_names)))
        ax.set_xticklabels(display_names, rotation=45, ha="right", fontsize=8)
        ax.set_yticklabels(scenario_names, fontsize=8)

        plt.colorbar(im, ax=ax, label="CPU %")
        ax.set_title("CPU Usage Heatmap (All Containers)")

        png_path = self.charts_dir / "cpu_heatmap.png"
        fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
        plt.close(fig_mpl)

        return [str(html_path), str(png_path)]

    def generate_memory_heatmap(self, scenarios: list[dict[str, Any]]) -> list[str]:
        """Generate memory usage heatmap across scenarios and all containers.

        Args:
            scenarios: List of all scenario results.

        Returns:
            List of generated file paths.
        """
        # Discover all containers
        all_containers: set[str] = set()
        for scenario in scenarios:
            samples = scenario.get("samples", [])
            for sample in samples:
                all_containers.update(sample.get("containers", {}).keys())

        # Sort with priority first
        priority = [
            "rideshare-simulation",
            "rideshare-kafka",
            "rideshare-redis",
            "rideshare-osrm",
            "rideshare-stream-processor",
        ]
        containers = [c for c in priority if c in all_containers]
        containers.extend([c for c in sorted(all_containers) if c not in priority])

        scenario_names = [s["scenario_name"] for s in scenarios]

        matrix: list[list[float]] = []

        for scenario in scenarios:
            samples = scenario.get("samples", [])
            all_stats = calculate_all_container_stats(samples)
            row = []
            for container in containers:
                if container in all_stats:
                    row.append(all_stats[container].memory_mean)
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
                colorscale="Blues",
                colorbar_title="Memory (MB)",
            )
        )

        fig.update_layout(
            title="Memory Usage Heatmap (All Containers)",
            xaxis_title="Container",
            yaxis_title="Scenario",
            height=max(400, 50 * len(scenario_names)),
        )

        html_path = self.charts_dir / "memory_heatmap.html"
        fig.write_html(str(html_path))

        # Matplotlib heatmap
        fig_mpl, ax = plt.subplots(
            figsize=(max(12, len(containers) * 0.8), max(8, len(scenario_names) * 0.5))
        )
        im = ax.imshow(matrix, cmap="Blues", aspect="auto")

        ax.set_xticks(np.arange(len(display_names)))
        ax.set_yticks(np.arange(len(scenario_names)))
        ax.set_xticklabels(display_names, rotation=45, ha="right", fontsize=8)
        ax.set_yticklabels(scenario_names, fontsize=8)

        plt.colorbar(im, ax=ax, label="Memory (MB)")
        ax.set_title("Memory Usage Heatmap (All Containers)")

        png_path = self.charts_dir / "memory_heatmap.png"
        fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
        plt.close(fig_mpl)

        return [str(html_path), str(png_path)]

    def generate_curve_fits(
        self, load_scenarios: list[dict[str, Any]], results: dict[str, Any]
    ) -> list[str]:
        """Generate scatter plots with curve fits for priority containers.

        Uses pre-computed fits from results["analysis"]["container_fits"] when available.

        Args:
            load_scenarios: List of load scaling scenario results.
            results: Full results dict with analysis section.

        Returns:
            List of generated file paths.
        """
        # Priority containers to generate curve fit charts for
        priority = [
            "rideshare-simulation",
            "rideshare-kafka",
            "rideshare-redis",
        ]

        container_fits = results.get("analysis", {}).get("container_fits", {})
        generated: list[str] = []

        for container in priority:
            for metric in ["memory", "cpu"]:
                # Extract data points
                data_points: list[tuple[int, float]] = []

                for scenario in load_scenarios:
                    agent_count = scenario["scenario_params"]["total_agents"]
                    samples = scenario.get("samples", [])
                    stats = calculate_stats(samples, container)
                    if stats:
                        value = stats.memory_mean if metric == "memory" else stats.cpu_mean
                        data_points.append((agent_count, value))

                if len(data_points) < 2:
                    continue

                data_points.sort()
                x = np.array([p[0] for p in data_points])
                y = np.array([p[1] for p in data_points])

                # Try to use pre-computed fits, otherwise compute fresh
                fit_data = container_fits.get(container, {}).get(metric, {})
                if fit_data and "error" not in fit_data:
                    # Use pre-computed fit info for display
                    pass

                # Fit all models (always compute for visualization)
                fitter = ResourceModelFitter()
                all_fits = fitter.fit_all(x.tolist(), y.tolist())

                if not all_fits:
                    continue

                display_name = CONTAINER_CONFIG.get(container, {}).get("display_name", container)
                y_label = "Memory (MB)" if metric == "memory" else "CPU %"
                title = f"Curve Fits - {display_name} ({metric.title()})"

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
                    predictions = fit_result.predictions
                    if len(predictions) == len(x):
                        from scipy.interpolate import interp1d

                        interp_func = interp1d(
                            x, predictions, kind="linear", fill_value="extrapolate"
                        )
                        y_smooth = interp_func(x_smooth)

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
                    title=title,
                    xaxis_title="Total Agents",
                    yaxis_title=y_label,
                )

                safe_name = container.replace("rideshare-", "")
                html_path = self.charts_dir / f"curve_fits_{safe_name}_{metric}.html"
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
                ax.set_ylabel(y_label)
                ax.set_title(title)
                ax.legend()
                ax.grid(alpha=0.3)

                png_path = self.charts_dir / f"curve_fits_{safe_name}_{metric}.png"
                fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
                plt.close(fig_mpl)

                generated.extend([str(html_path), str(png_path)])

        return generated
