"""Visualization generation for performance test results."""

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..config import CONTAINER_CONFIG
from .statistics import calculate_all_container_stats


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

        # Duration/leak timeline
        duration_scenarios = [
            s
            for s in scenarios
            if s["scenario_name"] == "duration_leak"
            or s["scenario_name"].startswith("duration_leak_")
        ]
        if duration_scenarios:
            generated.extend(self.generate_duration_timeline(duration_scenarios))

        # Heatmaps (across all scenarios) - both CPU and Memory
        if scenarios:
            generated.extend(self.generate_cpu_heatmap(scenarios))
            generated.extend(self.generate_memory_heatmap(scenarios))

        # Stress test charts
        stress_scenarios = [s for s in scenarios if s["scenario_name"] == "stress_test"]
        if stress_scenarios:
            generated.extend(self.generate_stress_timeline(stress_scenarios[0]))
            generated.extend(self.generate_stress_comparison(stress_scenarios[0]))
            generated.extend(self.generate_global_cpu_timeline(stress_scenarios[0]))

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

    def generate_stress_timeline(self, stress_scenario: dict[str, Any]) -> list[str]:
        """Generate timeline charts for stress test showing resource usage over time.

        Args:
            stress_scenario: Stress test scenario result.

        Returns:
            List of generated file paths.
        """
        samples = stress_scenario.get("samples", [])
        if not samples:
            return []

        metadata = stress_scenario.get("metadata", {})
        trigger = metadata.get("trigger")
        total_agents = metadata.get("total_agents_queued", 0)

        # Priority containers to display
        priority = [
            "rideshare-simulation",
            "rideshare-kafka",
            "rideshare-redis",
            "rideshare-osrm",
            "rideshare-stream-processor",
        ]

        generated: list[str] = []

        for metric in ["memory", "cpu"]:
            metric_key = "memory_percent" if metric == "memory" else "cpu_percent"
            y_label = "Memory %" if metric == "memory" else "CPU %"
            threshold = stress_scenario.get("scenario_params", {}).get(
                f"{metric}_threshold_percent", 90.0
            )

            # Determine the stop time (either trigger time or last sample)
            first_ts = samples[0]["timestamp"] if samples else 0
            last_ts = samples[-1]["timestamp"] if samples else 0
            stop_time_seconds = last_ts - first_ts

            # Find trigger time if the trigger matches this metric
            trigger_time = None
            if trigger and trigger.get("metric") == metric:
                trigger_time = stop_time_seconds

            # Plotly figure
            fig = go.Figure()

            # Add traces for each priority container
            for container in priority:
                timestamps: list[float] = []
                values: list[float] = []

                for sample in samples:
                    rolling_avgs = sample.get("rolling_averages", {})
                    if container in rolling_avgs:
                        elapsed = sample["timestamp"] - first_ts
                        timestamps.append(elapsed)
                        values.append(rolling_avgs[container].get(metric_key, 0))

                if timestamps:
                    display_name = CONTAINER_CONFIG.get(container, {}).get(
                        "display_name", container
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=timestamps,
                            y=values,
                            mode="lines",
                            name=display_name,
                        )
                    )

            # Add threshold line
            fig.add_hline(
                y=threshold,
                line_dash="dash",
                line_color="red",
                annotation_text=f"{threshold}% threshold",
            )

            # Add vertical marker where test stopped if trigger occurred
            if trigger_time is not None and trigger.get("metric") == metric:
                fig.add_vline(
                    x=trigger_time,
                    line_dash="dot",
                    line_color="darkred",
                    annotation_text=f"Stopped: {trigger.get('container', 'unknown')}",
                )

            # Dynamic y-axis for CPU (can exceed 100% on multi-core), fixed for memory
            all_trace_values: list[float] = []
            for trace in fig.data:
                if hasattr(trace, "y") and trace.y is not None:
                    all_trace_values.extend(v for v in trace.y if isinstance(v, (int, float)))
            if metric == "cpu" and all_trace_values:
                timeline_y_max = max(100.0, max(all_trace_values) * 1.15, threshold * 1.1)
            else:
                timeline_y_max = max(100.0, threshold * 1.1)

            fig.update_layout(
                title=f"Stress Test {metric.title()} Timeline (Total Agents: {total_agents})",
                xaxis_title="Time (seconds)",
                yaxis_title=y_label,
                yaxis_range=[0, timeline_y_max],
            )

            html_path = self.charts_dir / f"stress_timeline_{metric}.html"
            fig.write_html(str(html_path))

            # Matplotlib version
            fig_mpl, ax = plt.subplots(figsize=(12, 6))

            for container in priority:
                timestamps = []
                values = []

                for sample in samples:
                    rolling_avgs = sample.get("rolling_averages", {})
                    if container in rolling_avgs:
                        elapsed = sample["timestamp"] - first_ts
                        timestamps.append(elapsed)
                        values.append(rolling_avgs[container].get(metric_key, 0))

                if timestamps:
                    display_name = CONTAINER_CONFIG.get(container, {}).get(
                        "display_name", container
                    )
                    ax.plot(timestamps, values, label=display_name)

            # Add threshold line
            ax.axhline(y=threshold, color="red", linestyle="--", label=f"{threshold}% threshold")

            # Add vertical marker where test stopped
            if trigger_time is not None and trigger.get("metric") == metric:
                ax.axvline(
                    x=trigger_time,
                    color="darkred",
                    linestyle=":",
                    label=f"Stopped: {trigger.get('container', 'unknown')}",
                )

            ax.set_xlabel("Time (seconds)")
            ax.set_ylabel(y_label)
            ax.set_title(f"Stress Test {metric.title()} Timeline (Total Agents: {total_agents})")
            ax.set_ylim(0, timeline_y_max)
            ax.legend(loc="upper left", fontsize="small")
            ax.grid(alpha=0.3)

            png_path = self.charts_dir / f"stress_timeline_{metric}.png"
            fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
            plt.close(fig_mpl)

            generated.extend([str(html_path), str(png_path)])

        return generated

    def generate_stress_comparison(self, stress_scenario: dict[str, Any]) -> list[str]:
        """Generate bar charts comparing peak resource usage across containers.

        Args:
            stress_scenario: Stress test scenario result.

        Returns:
            List of generated file paths.
        """
        metadata = stress_scenario.get("metadata", {})
        peak_values = metadata.get("peak_values", {})
        total_agents = metadata.get("total_agents_queued", 0)

        if not peak_values:
            return []

        # Get all containers with peak values, prioritize key containers
        priority = [
            "rideshare-simulation",
            "rideshare-kafka",
            "rideshare-redis",
            "rideshare-osrm",
            "rideshare-stream-processor",
        ]

        sorted_containers = [c for c in priority if c in peak_values]
        sorted_containers.extend([c for c in sorted(peak_values.keys()) if c not in priority])

        # Limit to top containers for readability
        max_containers = 10
        containers_to_show = sorted_containers[:max_containers]

        generated: list[str] = []

        for metric in ["memory", "cpu"]:
            metric_key = f"{metric}_percent"
            y_label = "Memory %" if metric == "memory" else "CPU %"

            # Extract values and assign colors based on thresholds
            display_names: list[str] = []
            values: list[float] = []
            colors: list[str] = []

            for container in containers_to_show:
                peak = peak_values.get(container, {})
                value = peak.get(metric_key, 0)
                display_name = CONTAINER_CONFIG.get(container, {}).get("display_name", container)

                display_names.append(display_name)
                values.append(value)

                # Color based on threshold
                if value >= 85:
                    colors.append("red")
                elif value >= 70:
                    colors.append("orange")
                else:
                    colors.append("green")

            if not values:
                continue

            # Plotly bar chart
            fig = go.Figure(
                data=[
                    go.Bar(
                        x=display_names,
                        y=values,
                        marker_color=colors,
                        text=[f"{v:.1f}%" for v in values],
                        textposition="auto",
                    )
                ]
            )

            # Dynamic y-axis for CPU (can exceed 100% on multi-core), fixed for memory
            if metric == "cpu" and values:
                y_max = max(100.0, max(values) * 1.15)
            else:
                y_max = 100.0

            fig.update_layout(
                title=f"Stress Test Peak {metric.title()} Usage (Total Agents: {total_agents})",
                xaxis_title="Container",
                yaxis_title=y_label,
                yaxis_range=[0, y_max],
            )

            html_path = self.charts_dir / f"stress_comparison_{metric}.html"
            fig.write_html(str(html_path))

            # Matplotlib bar chart
            fig_mpl, ax = plt.subplots(figsize=(12, 6))

            x_pos = np.arange(len(display_names))
            bars = ax.bar(x_pos, values, color=colors)

            # Add value labels on bars
            for i, (bar, val) in enumerate(zip(bars, values)):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 1,
                    f"{val:.1f}%",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )

            ax.set_xlabel("Container")
            ax.set_ylabel(y_label)
            ax.set_title(f"Stress Test Peak {metric.title()} Usage (Total Agents: {total_agents})")
            ax.set_xticks(x_pos)
            ax.set_xticklabels(display_names, rotation=45, ha="right", fontsize=9)
            ax.set_ylim(0, y_max)
            ax.grid(axis="y", alpha=0.3)

            # Add legend for color meaning
            from matplotlib.patches import Patch

            legend_elements = [
                Patch(facecolor="green", label="<70% (normal)"),
                Patch(facecolor="orange", label="70-85% (elevated)"),
                Patch(facecolor="red", label=">=85% (critical)"),
            ]
            ax.legend(handles=legend_elements, loc="upper right", fontsize="small")

            png_path = self.charts_dir / f"stress_comparison_{metric}.png"
            fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
            plt.close(fig_mpl)

            generated.extend([str(html_path), str(png_path)])

        return generated

    def generate_global_cpu_timeline(self, stress_scenario: dict[str, Any]) -> list[str]:
        """Generate timeline chart showing system-level CPU saturation over time.

        Shows raw global CPU sum, rolling average, capacity ceiling, and threshold.

        Args:
            stress_scenario: Stress test scenario result.

        Returns:
            List of generated file paths.
        """
        samples = stress_scenario.get("samples", [])
        if not samples:
            return []

        metadata = stress_scenario.get("metadata", {})
        trigger = metadata.get("trigger")
        total_agents = metadata.get("total_agents_queued", 0)
        available_cores = metadata.get("available_cores", 0)
        global_cpu_threshold = metadata.get("global_cpu_threshold", 0)
        capacity_ceiling = available_cores * 100  # Max possible CPU %

        first_ts = samples[0]["timestamp"]

        # Extract raw global CPU and rolling average
        timestamps: list[float] = []
        raw_values: list[float] = []
        rolling_values: list[float] = []

        for sample in samples:
            elapsed = sample["timestamp"] - first_ts
            timestamps.append(elapsed)
            raw_values.append(sample.get("global_cpu_percent", 0.0))
            rolling_values.append(sample.get("global_cpu_rolling_avg", 0.0))

        if not timestamps:
            return []

        # Determine y-axis max
        all_values = raw_values + rolling_values + [capacity_ceiling, global_cpu_threshold]
        y_max = max(v for v in all_values if v > 0) * 1.1 if all_values else 100.0

        # Trigger time
        stop_time = timestamps[-1] if timestamps else 0
        trigger_time = stop_time if trigger and trigger.get("metric") == "global_cpu" else None

        generated: list[str] = []

        # --- Plotly version ---
        fig = go.Figure()

        # Raw global CPU (light, thin)
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=raw_values,
                mode="lines",
                name="Global CPU (raw)",
                line={"color": "lightblue", "width": 1},
                opacity=0.6,
            )
        )

        # Rolling average (bold blue)
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=rolling_values,
                mode="lines",
                name="Global CPU (rolling avg)",
                line={"color": "blue", "width": 3},
            )
        )

        # Capacity ceiling (gray dotted)
        if capacity_ceiling > 0:
            fig.add_hline(
                y=capacity_ceiling,
                line_dash="dot",
                line_color="gray",
                annotation_text=f"Capacity: {available_cores} cores ({capacity_ceiling}%)",
            )

        # Threshold (red dashed)
        if global_cpu_threshold > 0:
            fig.add_hline(
                y=global_cpu_threshold,
                line_dash="dash",
                line_color="red",
                annotation_text=f"Threshold: {global_cpu_threshold:.0f}%",
            )

        # Trigger marker
        if trigger_time is not None:
            fig.add_vline(
                x=trigger_time,
                line_dash="dot",
                line_color="darkred",
                annotation_text="Global CPU threshold hit",
            )

        fig.update_layout(
            title=f"Global CPU Saturation Timeline (Total Agents: {total_agents})",
            xaxis_title="Time (seconds)",
            yaxis_title="Aggregate CPU %",
            yaxis_range=[0, y_max],
        )

        html_path = self.charts_dir / "global_cpu_timeline.html"
        fig.write_html(str(html_path))

        # --- Matplotlib version ---
        fig_mpl, ax = plt.subplots(figsize=(12, 6))

        ax.plot(
            timestamps,
            raw_values,
            color="lightblue",
            linewidth=1,
            alpha=0.6,
            label="Global CPU (raw)",
        )
        ax.plot(
            timestamps, rolling_values, color="blue", linewidth=3, label="Global CPU (rolling avg)"
        )

        if capacity_ceiling > 0:
            ax.axhline(
                y=capacity_ceiling,
                color="gray",
                linestyle=":",
                label=f"Capacity: {available_cores} cores ({capacity_ceiling}%)",
            )

        if global_cpu_threshold > 0:
            ax.axhline(
                y=global_cpu_threshold,
                color="red",
                linestyle="--",
                label=f"Threshold: {global_cpu_threshold:.0f}%",
            )

        if trigger_time is not None:
            ax.axvline(
                x=trigger_time, color="darkred", linestyle=":", label="Global CPU threshold hit"
            )

        ax.set_xlabel("Time (seconds)")
        ax.set_ylabel("Aggregate CPU %")
        ax.set_title(f"Global CPU Saturation Timeline (Total Agents: {total_agents})")
        ax.set_ylim(0, y_max)
        ax.legend(loc="upper left", fontsize="small")
        ax.grid(alpha=0.3)

        png_path = self.charts_dir / "global_cpu_timeline.png"
        fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
        plt.close(fig_mpl)

        generated.extend([str(html_path), str(png_path)])
        return generated

    def generate_stress_rtr_timeline(self, stress_scenario: dict[str, Any]) -> list[str]:
        """Generate timeline chart showing RTR (Real-Time Ratio) over time.

        Shows instantaneous RTR as scatter points, rolling average as a line,
        the configured threshold, and a 1.0x reference line.

        Args:
            stress_scenario: Stress test scenario result.

        Returns:
            List of generated file paths.
        """
        samples = stress_scenario.get("samples", [])
        if not samples:
            return []

        metadata = stress_scenario.get("metadata", {})
        total_agents = metadata.get("total_agents_queued", 0)
        rtr_threshold = stress_scenario.get("scenario_params", {}).get("rtr_threshold", 1.5)

        first_ts = samples[0]["timestamp"]

        # Extract RTR data
        rtr_timestamps: list[float] = []
        rtr_values: list[float] = []
        rolling_timestamps: list[float] = []
        rolling_values: list[float] = []

        for sample in samples:
            elapsed = sample["timestamp"] - first_ts
            rtr_data = sample.get("rtr")
            if rtr_data is not None and "rtr" in rtr_data:
                rtr_timestamps.append(elapsed)
                rtr_values.append(rtr_data["rtr"])
            rolling_avg = sample.get("rtr_rolling_avg")
            if rolling_avg is not None:
                rolling_timestamps.append(elapsed)
                rolling_values.append(rolling_avg)

        if not rtr_timestamps and not rolling_timestamps:
            return []

        # Determine y-axis max
        all_vals = rtr_values + rolling_values + [rtr_threshold, 1.0]
        y_max = max(all_vals) * 1.2 if all_vals else 3.0

        generated: list[str] = []

        # --- Plotly version ---
        fig = go.Figure()

        # Instantaneous RTR (scatter)
        if rtr_timestamps:
            fig.add_trace(
                go.Scatter(
                    x=rtr_timestamps,
                    y=rtr_values,
                    mode="markers",
                    name="RTR (instantaneous)",
                    marker={"color": "lightcoral", "size": 5, "opacity": 0.6},
                )
            )

        # Rolling average (bold line)
        if rolling_timestamps:
            fig.add_trace(
                go.Scatter(
                    x=rolling_timestamps,
                    y=rolling_values,
                    mode="lines",
                    name="RTR (rolling avg)",
                    line={"color": "red", "width": 3},
                )
            )

        # 1.0x reference line (keeping pace)
        fig.add_hline(
            y=1.0,
            line_dash="dot",
            line_color="green",
            annotation_text="1.0x (keeping pace)",
        )

        # Threshold line
        fig.add_hline(
            y=rtr_threshold,
            line_dash="dash",
            line_color="darkred",
            annotation_text=f"{rtr_threshold}x threshold",
        )

        fig.update_layout(
            title=f"Simulation RTR Timeline (Total Agents: {total_agents})",
            xaxis_title="Time (seconds)",
            yaxis_title="Real-Time Ratio (higher = more behind)",
            yaxis_range=[0, y_max],
        )

        html_path = self.charts_dir / "stress_rtr_timeline.html"
        fig.write_html(str(html_path))

        # --- Matplotlib version ---
        fig_mpl, ax = plt.subplots(figsize=(12, 6))

        if rtr_timestamps:
            ax.scatter(
                rtr_timestamps,
                rtr_values,
                color="lightcoral",
                s=15,
                alpha=0.6,
                label="RTR (instantaneous)",
                zorder=2,
            )

        if rolling_timestamps:
            ax.plot(
                rolling_timestamps,
                rolling_values,
                color="red",
                linewidth=3,
                label="RTR (rolling avg)",
                zorder=3,
            )

        # 1.0x reference
        ax.axhline(
            y=1.0,
            color="green",
            linestyle=":",
            label="1.0x (keeping pace)",
            zorder=1,
        )

        # Threshold
        ax.axhline(
            y=rtr_threshold,
            color="darkred",
            linestyle="--",
            label=f"{rtr_threshold}x threshold",
            zorder=1,
        )

        ax.set_xlabel("Time (seconds)")
        ax.set_ylabel("Real-Time Ratio (higher = more behind)")
        ax.set_title(f"Simulation RTR Timeline (Total Agents: {total_agents})")
        ax.set_ylim(0, y_max)
        ax.legend(loc="upper left", fontsize="small")
        ax.grid(alpha=0.3)

        png_path = self.charts_dir / "stress_rtr_timeline.png"
        fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
        plt.close(fig_mpl)

        generated.extend([str(html_path), str(png_path)])
        return generated

    def _create_scenario_subdirs(self) -> dict[str, Path]:
        """Create subdirectories for organizing charts by scenario type.

        Returns:
            Dictionary mapping scenario type to its directory path.
        """
        subdirs = {
            "overview": self.charts_dir / "overview",
            "duration": self.charts_dir / "duration",
            "stress": self.charts_dir / "stress",
            "speed_scaling": self.charts_dir / "speed_scaling",
        }

        for subdir in subdirs.values():
            subdir.mkdir(parents=True, exist_ok=True)

        return subdirs

    def generate_charts_by_scenario(self, results: dict[str, Any]) -> dict[str, list[str]]:
        """Generate charts organized into scenario subdirectories.

        Args:
            results: Full test results dict.

        Returns:
            Dictionary mapping scenario type to list of generated chart paths.
        """
        subdirs = self._create_scenario_subdirs()
        chart_paths: dict[str, list[str]] = {key: [] for key in subdirs}

        scenarios = results.get("scenarios", [])

        # Overview charts (heatmaps)
        if scenarios:
            # Temporarily change charts_dir for overview charts
            original_dir = self.charts_dir
            self.charts_dir = subdirs["overview"]
            chart_paths["overview"].extend(self.generate_cpu_heatmap(scenarios))
            chart_paths["overview"].extend(self.generate_memory_heatmap(scenarios))
            self.charts_dir = original_dir

        # Duration/leak charts
        duration_scenarios = [
            s
            for s in scenarios
            if s["scenario_name"] == "duration_leak"
            or s["scenario_name"].startswith("duration_leak_")
        ]
        if duration_scenarios:
            original_dir = self.charts_dir
            self.charts_dir = subdirs["duration"]
            chart_paths["duration"].extend(self.generate_duration_timeline(duration_scenarios))
            self.charts_dir = original_dir

        # Stress test charts
        stress_scenarios = [s for s in scenarios if s["scenario_name"] == "stress_test"]
        if stress_scenarios:
            original_dir = self.charts_dir
            self.charts_dir = subdirs["stress"]
            chart_paths["stress"].extend(self.generate_stress_timeline(stress_scenarios[0]))
            chart_paths["stress"].extend(self.generate_stress_comparison(stress_scenarios[0]))
            chart_paths["stress"].extend(self.generate_global_cpu_timeline(stress_scenarios[0]))
            chart_paths["stress"].extend(self.generate_stress_rtr_timeline(stress_scenarios[0]))
            self.charts_dir = original_dir

        # Speed scaling charts
        speed_scenarios = [s for s in scenarios if s["scenario_name"] == "speed_scaling"]
        if speed_scenarios:
            original_dir = self.charts_dir
            self.charts_dir = subdirs["speed_scaling"]
            chart_paths["speed_scaling"].extend(
                self.generate_speed_scaling_chart(speed_scenarios[0])
            )
            self.charts_dir = original_dir

        # Generate index page
        index_path = self.generate_index_html(chart_paths)
        if index_path:
            chart_paths["overview"].insert(0, str(index_path))

        return chart_paths

    def generate_index_html(self, chart_paths: dict[str, list[str]]) -> Path | None:
        """Generate HTML navigation page linking all charts.

        Args:
            chart_paths: Dictionary mapping scenario type to list of chart paths.

        Returns:
            Path to generated index.html, or None if no charts.
        """
        total_charts = sum(len(paths) for paths in chart_paths.values())
        if total_charts == 0:
            return None

        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Performance Test Charts</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; }
        .chart-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 15px;
        }
        .chart-card {
            background: white;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .chart-card a {
            color: #007bff;
            text-decoration: none;
            display: block;
            margin: 5px 0;
        }
        .chart-card a:hover { text-decoration: underline; }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            margin-left: 8px;
        }
        .badge-html { background: #e3f2fd; color: #1976d2; }
        .badge-png { background: #f3e5f5; color: #7b1fa2; }
        .section-empty { color: #999; font-style: italic; }
    </style>
</head>
<body>
    <h1>Performance Test Charts</h1>
"""

        section_titles = {
            "overview": "Overview",
            "duration": "Duration/Leak Tests",
            "stress": "Stress Tests",
            "speed_scaling": "Speed Scaling Tests",
        }

        for section_key, section_title in section_titles.items():
            paths = chart_paths.get(section_key, [])
            html_content += f"    <h2>{section_title}</h2>\n"

            if not paths:
                html_content += '    <p class="section-empty">No charts generated</p>\n'
                continue

            html_content += '    <div class="chart-grid">\n'

            # Group by base name (html and png pairs)
            seen_bases: set[str] = set()
            for path in paths:
                p = Path(path)
                base_name = p.stem
                if base_name in seen_bases:
                    continue
                seen_bases.add(base_name)

                # Find all variants
                html_path = p.with_suffix(".html")
                png_path = p.with_suffix(".png")

                html_content += '        <div class="chart-card">\n'
                html_content += (
                    f"            <strong>{base_name.replace('_', ' ').title()}</strong><br>\n"
                )

                rel_dir = p.parent.name
                if html_path.exists() or str(html_path) in paths:
                    html_content += f'            <a href="{rel_dir}/{html_path.name}">Interactive <span class="badge badge-html">HTML</span></a>\n'
                if png_path.exists() or str(png_path) in paths:
                    html_content += f'            <a href="{rel_dir}/{png_path.name}">Static <span class="badge badge-png">PNG</span></a>\n'

                html_content += "        </div>\n"

            html_content += "    </div>\n"

        html_content += """</body>
</html>
"""

        index_path = self.charts_dir / "index.html"
        with open(index_path, "w") as f:
            f.write(html_content)

        return index_path

    def generate_speed_scaling_chart(self, speed_scenario: dict[str, Any]) -> list[str]:
        """Generate grouped bar chart of mean CPU and memory per step per priority container.

        Args:
            speed_scenario: Speed scaling scenario result.

        Returns:
            List of generated file paths.
        """
        metadata = speed_scenario.get("metadata", {})
        step_results = metadata.get("step_results", [])
        samples = speed_scenario.get("samples", [])

        if not step_results or not samples:
            return []

        priority = [
            "rideshare-simulation",
            "rideshare-kafka",
            "rideshare-redis",
            "rideshare-osrm",
            "rideshare-stream-processor",
        ]

        # Build per-step, per-container averages from samples
        # We need to partition samples by step using step_results sample counts
        step_data: list[dict[str, dict[str, float]]] = []
        sample_offset = 0

        for step in step_results:
            step_sample_count = step.get("sample_count", 0)
            step_samples = samples[sample_offset : sample_offset + step_sample_count]
            sample_offset += step_sample_count

            container_avgs: dict[str, dict[str, float]] = {}
            for container in priority:
                cpu_vals: list[float] = []
                mem_vals: list[float] = []

                for s in step_samples:
                    c_data = s.get("containers", {}).get(container, {})
                    if c_data:
                        cpu_vals.append(c_data.get("cpu_percent", 0.0))
                        mem_vals.append(c_data.get("memory_percent", 0.0))

                if cpu_vals:
                    container_avgs[container] = {
                        "cpu_mean": sum(cpu_vals) / len(cpu_vals),
                        "memory_mean": sum(mem_vals) / len(mem_vals),
                    }

            step_data.append(container_avgs)

        if not step_data:
            return []

        generated: list[str] = []
        step_labels = [f"{s['multiplier']}x" for s in step_results]

        for metric in ["cpu", "memory"]:
            metric_key = f"{metric}_mean"
            y_label = "CPU %" if metric == "cpu" else "Memory %"

            # Plotly grouped bar chart
            fig = go.Figure()

            for container in priority:
                display_name = CONTAINER_CONFIG.get(container, {}).get("display_name", container)
                values = [sd.get(container, {}).get(metric_key, 0.0) for sd in step_data]
                fig.add_trace(go.Bar(name=display_name, x=step_labels, y=values))

            # Dynamic y-axis for CPU
            all_vals = [sd.get(c, {}).get(metric_key, 0.0) for sd in step_data for c in priority]
            if metric == "cpu" and all_vals:
                chart_y_max = max(100.0, max(all_vals) * 1.15)
            else:
                chart_y_max = 100.0

            fig.update_layout(
                title=f"Speed Scaling: Mean {metric.title()} Per Step",
                xaxis_title="Speed Multiplier",
                yaxis_title=y_label,
                yaxis_range=[0, chart_y_max],
                barmode="group",
            )

            html_path = self.charts_dir / f"speed_scaling_{metric}.html"
            fig.write_html(str(html_path))

            # Matplotlib version
            fig_mpl, ax = plt.subplots(figsize=(12, 6))

            x = np.arange(len(step_labels))
            width = 0.15
            offset = -(len(priority) - 1) * width / 2

            for i, container in enumerate(priority):
                display_name = CONTAINER_CONFIG.get(container, {}).get("display_name", container)
                values = [sd.get(container, {}).get(metric_key, 0.0) for sd in step_data]
                ax.bar(
                    x + offset + i * width,
                    values,
                    width,
                    label=display_name,
                )

            ax.set_xlabel("Speed Multiplier")
            ax.set_ylabel(y_label)
            ax.set_title(f"Speed Scaling: Mean {metric.title()} Per Step")
            ax.set_xticks(x)
            ax.set_xticklabels(step_labels)
            ax.set_ylim(0, chart_y_max)
            ax.legend(fontsize="small")
            ax.grid(axis="y", alpha=0.3)

            png_path = self.charts_dir / f"speed_scaling_{metric}.png"
            fig_mpl.savefig(png_path, dpi=150, bbox_inches="tight")
            plt.close(fig_mpl)

            generated.extend([str(html_path), str(png_path)])

        return generated
