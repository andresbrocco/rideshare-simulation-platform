"""Visualization generation for performance test results.

Uses Plotly for interactive HTML charts and kaleido for static PNG export.
"""

from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..config import CONTAINER_CONFIG
from .statistics import calculate_all_container_stats


# Priority containers shown first in charts
_PRIORITY_CONTAINERS = [
    "rideshare-simulation",
    "rideshare-kafka",
    "rideshare-redis",
    "rideshare-osrm",
    "rideshare-stream-processor",
]


def _get_display_name(container: str) -> str:
    """Get display name for a container."""
    return CONTAINER_CONFIG.get(container, {}).get("display_name", container)


def _sort_containers(containers: set[str] | list[str]) -> list[str]:
    """Sort containers with priority containers first."""
    container_set = set(containers)
    sorted_list = [c for c in _PRIORITY_CONTAINERS if c in container_set]
    sorted_list.extend(sorted(c for c in container_set if c not in _PRIORITY_CONTAINERS))
    return sorted_list


def _write_chart(
    fig: go.Figure, base_path: Path, width: int = 1200, height: int = 600
) -> list[str]:
    """Write chart as both HTML and PNG.

    Args:
        fig: Plotly figure.
        base_path: Path without extension (e.g., charts/cpu_heatmap).
        width: PNG width in pixels.
        height: PNG height in pixels.

    Returns:
        List of generated file paths.
    """
    html_path = base_path.with_suffix(".html")
    png_path = base_path.with_suffix(".png")

    fig.write_html(str(html_path))
    fig.write_image(str(png_path), width=width, height=height, scale=2)

    return [str(html_path), str(png_path)]


class ChartGenerator:
    """Generates charts for performance test analysis.

    Outputs interactive HTML (Plotly) and static PNG (kaleido).
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
        self, duration_scenarios: list[dict[str, Any]], max_containers: int = 5
    ) -> list[str]:
        """Generate timeline charts for memory and CPU over duration tests.

        Limited to priority containers to avoid absurdly tall images.

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
            for sample in scenario.get("samples", []):
                all_containers.update(sample.get("containers", {}).keys())

        sorted_containers = _sort_containers(all_containers)

        # Extract phase timestamps for annotations
        phase_timestamps: dict[str, float] | None = None
        for scenario in duration_scenarios:
            pt = scenario.get("metadata", {}).get("phase_timestamps")
            if pt:
                phase_timestamps = pt
                break

        generated: list[str] = []

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

                fig = make_subplots(
                    rows=len(batch_containers),
                    cols=1,
                    subplot_titles=[_get_display_name(c) for c in batch_containers],
                )

                for row_idx, container in enumerate(batch_containers, 1):
                    for scenario in duration_scenarios:
                        samples = scenario.get("samples", [])
                        if not samples:
                            continue

                        timestamps = []
                        values = []
                        start_time = samples[0]["timestamp"]

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

                # Add phase annotations if available
                if phase_timestamps and duration_scenarios:
                    ref_start = duration_scenarios[0].get("samples", [{}])[0].get("timestamp", 0)
                    _add_phase_annotations(fig, phase_timestamps, ref_start, len(batch_containers))

                fig.update_layout(
                    title=f"{metric.title()} Over Time (Leak Detection){batch_suffix}",
                    height=200 * len(batch_containers),
                )
                fig.update_xaxes(title_text="Time (minutes)")
                fig.update_yaxes(title_text=y_label)

                base_path = self.charts_dir / f"duration_timeline_{metric}{batch_suffix}"
                generated.extend(_write_chart(fig, base_path, height=200 * len(batch_containers)))

        return generated

    def generate_cpu_heatmap(self, scenarios: list[dict[str, Any]]) -> list[str]:
        """Generate CPU usage heatmap across scenarios and all containers."""
        all_containers: set[str] = set()
        for scenario in scenarios:
            for sample in scenario.get("samples", []):
                all_containers.update(sample.get("containers", {}).keys())

        containers = _sort_containers(all_containers)
        scenario_names = [s["scenario_name"] for s in scenarios]

        matrix: list[list[float]] = []
        for scenario in scenarios:
            all_stats = calculate_all_container_stats(scenario.get("samples", []))
            row = [all_stats[c].cpu_mean if c in all_stats else 0 for c in containers]
            matrix.append(row)

        if not matrix:
            return []

        display_names = [_get_display_name(c) for c in containers]

        # Add cell text annotations
        text_matrix = [[f"{v:.1f}" for v in row] for row in matrix]

        fig = go.Figure(
            data=go.Heatmap(
                z=matrix,
                x=display_names,
                y=scenario_names,
                colorscale="RdYlGn_r",
                colorbar_title="CPU %",
                text=text_matrix,
                texttemplate="%{text}",
                textfont={"size": 10},
            )
        )

        fig.update_layout(
            title="Mean CPU % Heatmap",
            xaxis_title="Container",
            yaxis_title="Scenario",
            xaxis_tickangle=-45,
            height=max(400, 100 * len(scenario_names)),
        )

        return _write_chart(
            fig,
            self.charts_dir / "cpu_heatmap",
            width=max(1200, 80 * len(containers)),
            height=max(400, 100 * len(scenario_names)),
        )

    def generate_memory_heatmap(self, scenarios: list[dict[str, Any]]) -> list[str]:
        """Generate memory usage heatmap across scenarios and all containers."""
        all_containers: set[str] = set()
        for scenario in scenarios:
            for sample in scenario.get("samples", []):
                all_containers.update(sample.get("containers", {}).keys())

        containers = _sort_containers(all_containers)
        scenario_names = [s["scenario_name"] for s in scenarios]

        matrix: list[list[float]] = []
        for scenario in scenarios:
            all_stats = calculate_all_container_stats(scenario.get("samples", []))
            row = [all_stats[c].memory_mean if c in all_stats else 0 for c in containers]
            matrix.append(row)

        if not matrix:
            return []

        display_names = [_get_display_name(c) for c in containers]
        text_matrix = [[f"{v:.0f}" for v in row] for row in matrix]

        fig = go.Figure(
            data=go.Heatmap(
                z=matrix,
                x=display_names,
                y=scenario_names,
                colorscale="Blues",
                colorbar_title="Memory (MB)",
                text=text_matrix,
                texttemplate="%{text}",
                textfont={"size": 10},
            )
        )

        fig.update_layout(
            title="Mean Memory (MB) Heatmap",
            xaxis_title="Container",
            yaxis_title="Scenario",
            xaxis_tickangle=-45,
            height=max(400, 100 * len(scenario_names)),
        )

        return _write_chart(
            fig,
            self.charts_dir / "memory_heatmap",
            width=max(1200, 80 * len(containers)),
            height=max(400, 100 * len(scenario_names)),
        )

    def generate_memory_percent_heatmap(self, scenarios: list[dict[str, Any]]) -> list[str]:
        """Generate memory % of limit heatmap across scenarios.

        Shows which containers are close to their limits (normalized view).
        """
        all_containers: set[str] = set()
        for scenario in scenarios:
            for sample in scenario.get("samples", []):
                all_containers.update(sample.get("containers", {}).keys())

        containers = _sort_containers(all_containers)
        scenario_names = [s["scenario_name"] for s in scenarios]

        matrix: list[list[float]] = []
        for scenario in scenarios:
            samples = scenario.get("samples", [])
            all_stats = calculate_all_container_stats(samples)
            row: list[float] = []
            for c in containers:
                if c in all_stats and all_stats[c].memory_limit_mb > 0:
                    pct = (all_stats[c].memory_max / all_stats[c].memory_limit_mb) * 100
                    row.append(min(pct, 100.0))
                else:
                    row.append(0)
            matrix.append(row)

        if not matrix:
            return []

        display_names = [_get_display_name(c) for c in containers]
        text_matrix = [[f"{v:.0f}%" for v in row] for row in matrix]

        fig = go.Figure(
            data=go.Heatmap(
                z=matrix,
                x=display_names,
                y=scenario_names,
                colorscale=[[0, "green"], [0.5, "yellow"], [1.0, "red"]],
                zmin=0,
                zmax=100,
                colorbar_title="% of Limit",
                text=text_matrix,
                texttemplate="%{text}",
                textfont={"size": 10},
            )
        )

        fig.update_layout(
            title="Peak Memory % of Limit Heatmap",
            xaxis_title="Container",
            yaxis_title="Scenario",
            xaxis_tickangle=-45,
            height=max(400, 100 * len(scenario_names)),
        )

        return _write_chart(
            fig,
            self.charts_dir / "memory_percent_heatmap",
            width=max(1200, 80 * len(containers)),
            height=max(400, 100 * len(scenario_names)),
        )

    def generate_baseline_resources(self, baseline_scenario: dict[str, Any]) -> list[str]:
        """Generate grouped bar chart of idle resource usage from baseline.

        Shows memory MB (left axis) and CPU % (right axis) per container.
        """
        samples = baseline_scenario.get("samples", [])
        if not samples:
            return []

        all_stats = calculate_all_container_stats(samples)
        if not all_stats:
            return []

        containers = _sort_containers(set(all_stats.keys()))
        display_names = [_get_display_name(c) for c in containers]
        memory_values = [all_stats[c].memory_mean for c in containers]
        cpu_values = [all_stats[c].cpu_mean for c in containers]

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        fig.add_trace(
            go.Bar(
                x=display_names,
                y=memory_values,
                name="Memory (MB)",
                marker_color="steelblue",
                text=[f"{v:.0f}" for v in memory_values],
                textposition="auto",
            ),
            secondary_y=False,
        )

        fig.add_trace(
            go.Scatter(
                x=display_names,
                y=cpu_values,
                name="CPU %",
                mode="lines+markers",
                marker={"color": "orangered", "size": 8},
                line={"color": "orangered", "width": 2},
            ),
            secondary_y=True,
        )

        fig.update_layout(
            title="Baseline Idle Resource Usage",
            xaxis_title="Container",
            xaxis_tickangle=-45,
        )
        fig.update_yaxes(title_text="Memory (MB)", secondary_y=False)
        fig.update_yaxes(title_text="CPU %", secondary_y=True)

        return _write_chart(fig, self.charts_dir / "baseline_resources")

    def generate_stress_timeline(self, stress_scenario: dict[str, Any]) -> list[str]:
        """Generate timeline charts for stress test showing resource usage over time."""
        samples = stress_scenario.get("samples", [])
        if not samples:
            return []

        metadata = stress_scenario.get("metadata", {})
        trigger = metadata.get("trigger")
        total_agents = metadata.get("total_agents_queued", 0)

        generated: list[str] = []

        for metric in ["memory", "cpu"]:
            metric_key = "memory_percent" if metric == "memory" else "cpu_percent"
            y_label = "Memory %" if metric == "memory" else "CPU %"
            threshold = stress_scenario.get("scenario_params", {}).get(
                f"{metric}_threshold_percent", 90.0
            )

            first_ts = samples[0]["timestamp"]
            stop_time_seconds = samples[-1]["timestamp"] - first_ts

            trigger_time = None
            if trigger and trigger.get("metric") == metric:
                trigger_time = stop_time_seconds

            fig = go.Figure()

            for container in _PRIORITY_CONTAINERS:
                timestamps: list[float] = []
                values: list[float] = []

                for sample in samples:
                    rolling_avgs = sample.get("rolling_averages", {})
                    if container in rolling_avgs:
                        elapsed = sample["timestamp"] - first_ts
                        timestamps.append(elapsed)
                        values.append(rolling_avgs[container].get(metric_key, 0))

                if timestamps:
                    fig.add_trace(
                        go.Scatter(
                            x=timestamps,
                            y=values,
                            mode="lines",
                            name=_get_display_name(container),
                        )
                    )

            fig.add_hline(
                y=threshold,
                line_dash="dash",
                line_color="red",
                annotation_text=f"{threshold}% threshold",
            )

            if trigger_time is not None:
                fig.add_vline(
                    x=trigger_time,
                    line_dash="dot",
                    line_color="darkred",
                    annotation_text=f"Stopped: {trigger.get('container', 'unknown')}",
                )

            # Dynamic y-axis for CPU
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

            generated.extend(_write_chart(fig, self.charts_dir / f"stress_timeline_{metric}"))

        return generated

    def generate_stress_agent_resource(self, stress_scenario: dict[str, Any]) -> list[str]:
        """Generate dual-axis timeline: agents queued vs resource usage.

        X-axis: time. Left Y-axis: total agents queued. Right Y-axis: global CPU %.
        """
        samples = stress_scenario.get("samples", [])
        if not samples:
            return []

        metadata = stress_scenario.get("metadata", {})
        trigger = metadata.get("trigger")
        total_agents = metadata.get("total_agents_queued", 0)
        available_cores = metadata.get("available_cores", 0)
        global_cpu_threshold = metadata.get("global_cpu_threshold", 0)

        first_ts = samples[0]["timestamp"]
        timestamps = [s["timestamp"] - first_ts for s in samples]
        agent_values = [s.get("agents_queued", {}).get("total", 0) for s in samples]
        cpu_values = [s.get("global_cpu_percent", 0.0) for s in samples]

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Agents queued (left axis, line)
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=agent_values,
                mode="lines",
                name="Total Agents",
                line={"color": "royalblue", "width": 2},
            ),
            secondary_y=False,
        )

        # Global CPU % (right axis, area fill)
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=cpu_values,
                mode="lines",
                name="Global CPU %",
                line={"color": "orangered", "width": 1},
                fill="tozeroy",
                fillcolor="rgba(255, 69, 0, 0.15)",
            ),
            secondary_y=True,
        )

        # Threshold line
        if global_cpu_threshold > 0:
            fig.add_hline(
                y=global_cpu_threshold,
                line_dash="dash",
                line_color="red",
                annotation_text=f"CPU Threshold: {global_cpu_threshold:.0f}%",
                secondary_y=True,
            )

        # Capacity ceiling
        if available_cores > 0:
            capacity = available_cores * 100
            fig.add_hline(
                y=capacity,
                line_dash="dot",
                line_color="gray",
                annotation_text=f"Capacity: {capacity}%",
                secondary_y=True,
            )

        # Trigger point
        if trigger:
            trigger_time = timestamps[-1] if timestamps else 0
            fig.add_vline(
                x=trigger_time,
                line_dash="dot",
                line_color="darkred",
                annotation_text=f"Trigger: {trigger.get('metric', '')}",
            )

        fig.update_layout(
            title=f"Stress: Agents vs Resources (Total: {total_agents})",
            xaxis_title="Time (seconds)",
        )
        fig.update_yaxes(title_text="Total Agents Queued", secondary_y=False)
        fig.update_yaxes(title_text="Global CPU %", secondary_y=True)

        return _write_chart(fig, self.charts_dir / "stress_agent_resource")

    def generate_stress_comparison(self, stress_scenario: dict[str, Any]) -> list[str]:
        """Generate bar charts comparing peak resource usage across containers."""
        metadata = stress_scenario.get("metadata", {})
        peak_values = metadata.get("peak_values", {})
        total_agents = metadata.get("total_agents_queued", 0)

        if not peak_values:
            return []

        sorted_containers = _sort_containers(set(peak_values.keys()))
        containers_to_show = sorted_containers[:10]

        generated: list[str] = []

        for metric in ["memory", "cpu"]:
            metric_key = f"{metric}_percent"
            y_label = "Memory %" if metric == "memory" else "CPU %"

            display_names: list[str] = []
            values: list[float] = []
            colors: list[str] = []

            for container in containers_to_show:
                peak = peak_values.get(container, {})
                value = peak.get(metric_key, 0)
                display_names.append(_get_display_name(container))
                values.append(value)
                if value >= 85:
                    colors.append("red")
                elif value >= 70:
                    colors.append("orange")
                else:
                    colors.append("green")

            if not values:
                continue

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

            if metric == "cpu" and values:
                y_max = max(100.0, max(values) * 1.15)
            else:
                y_max = 100.0

            fig.update_layout(
                title=f"Stress Test Peak {metric.title()} Usage (Total Agents: {total_agents})",
                xaxis_title="Container",
                yaxis_title=y_label,
                yaxis_range=[0, y_max],
                xaxis_tickangle=-45,
            )

            generated.extend(_write_chart(fig, self.charts_dir / f"stress_comparison_{metric}"))

        return generated

    def generate_global_cpu_timeline(self, stress_scenario: dict[str, Any]) -> list[str]:
        """Generate timeline chart showing system-level CPU saturation over time."""
        samples = stress_scenario.get("samples", [])
        if not samples:
            return []

        metadata = stress_scenario.get("metadata", {})
        trigger = metadata.get("trigger")
        total_agents = metadata.get("total_agents_queued", 0)
        available_cores = metadata.get("available_cores", 0)
        global_cpu_threshold = metadata.get("global_cpu_threshold", 0)
        capacity_ceiling = available_cores * 100

        first_ts = samples[0]["timestamp"]

        timestamps: list[float] = []
        raw_values: list[float] = []
        rolling_values: list[float] = []

        for sample in samples:
            timestamps.append(sample["timestamp"] - first_ts)
            raw_values.append(sample.get("global_cpu_percent", 0.0))
            rolling_values.append(sample.get("global_cpu_rolling_avg", 0.0))

        if not timestamps:
            return []

        all_values = raw_values + rolling_values + [capacity_ceiling, global_cpu_threshold]
        y_max = max(v for v in all_values if v > 0) * 1.1 if all_values else 100.0

        trigger_time = timestamps[-1] if trigger and trigger.get("metric") == "global_cpu" else None

        fig = go.Figure()

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
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=rolling_values,
                mode="lines",
                name="Global CPU (rolling avg)",
                line={"color": "blue", "width": 3},
            )
        )

        if capacity_ceiling > 0:
            fig.add_hline(
                y=capacity_ceiling,
                line_dash="dot",
                line_color="gray",
                annotation_text=f"Capacity: {available_cores} cores ({capacity_ceiling}%)",
            )
        if global_cpu_threshold > 0:
            fig.add_hline(
                y=global_cpu_threshold,
                line_dash="dash",
                line_color="red",
                annotation_text=f"Threshold: {global_cpu_threshold:.0f}%",
            )
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

        return _write_chart(fig, self.charts_dir / "global_cpu_timeline")

    def generate_stress_rtr_timeline(self, stress_scenario: dict[str, Any]) -> list[str]:
        """Generate timeline chart showing RTR (Real-Time Ratio) over time."""
        samples = stress_scenario.get("samples", [])
        if not samples:
            return []

        metadata = stress_scenario.get("metadata", {})
        total_agents = metadata.get("total_agents_queued", 0)
        rtr_threshold = stress_scenario.get("scenario_params", {}).get("rtr_threshold", 1.5)

        first_ts = samples[0]["timestamp"]

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

        all_vals = rtr_values + rolling_values + [rtr_threshold, 0.95]
        y_max = max(all_vals) * 1.2 if all_vals else 1.5

        fig = go.Figure()

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

        fig.add_hline(
            y=0.95, line_dash="dot", line_color="green", annotation_text="0.95 (keeping pace)"
        )
        fig.add_hline(
            y=rtr_threshold,
            line_dash="dash",
            line_color="darkred",
            annotation_text=f"{rtr_threshold} threshold",
        )

        fig.update_layout(
            title=f"Simulation RTR Timeline (Total Agents: {total_agents})",
            xaxis_title="Time (seconds)",
            yaxis_title="RTR (1.0 = perfect)",
            yaxis_range=[0, y_max],
        )

        return _write_chart(fig, self.charts_dir / "stress_rtr_timeline")

    def generate_speed_scaling_chart(self, speed_scenario: dict[str, Any]) -> list[str]:
        """Generate grouped bar chart of mean CPU and memory per step per priority container."""
        metadata = speed_scenario.get("metadata", {})
        step_results = metadata.get("step_results", [])
        samples = speed_scenario.get("samples", [])

        if not step_results or not samples:
            return []

        # Build per-step, per-container averages
        step_data: list[dict[str, dict[str, float]]] = []
        sample_offset = 0

        for step in step_results:
            step_sample_count = step.get("sample_count", 0)
            step_samples = samples[sample_offset : sample_offset + step_sample_count]
            sample_offset += step_sample_count

            container_avgs: dict[str, dict[str, float]] = {}
            for container in _PRIORITY_CONTAINERS:
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

            fig = go.Figure()

            for container in _PRIORITY_CONTAINERS:
                display_name = _get_display_name(container)
                values = [sd.get(container, {}).get(metric_key, 0.0) for sd in step_data]
                fig.add_trace(go.Bar(name=display_name, x=step_labels, y=values))

            all_vals = [
                sd.get(c, {}).get(metric_key, 0.0) for sd in step_data for c in _PRIORITY_CONTAINERS
            ]
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

            generated.extend(_write_chart(fig, self.charts_dir / f"speed_scaling_{metric}"))

        return generated

    def generate_speed_rtr_chart(self, speed_scenario: dict[str, Any]) -> list[str]:
        """Generate bar chart showing mean RTR at each speed multiplier step.

        Color-coded: green (<1.0), yellow (1.0-threshold), red (>threshold).
        """
        metadata = speed_scenario.get("metadata", {})
        step_results = metadata.get("step_results", [])
        samples = speed_scenario.get("samples", [])

        if not step_results or not samples:
            return []

        rtr_threshold = speed_scenario.get("scenario_params", {}).get("rtr_threshold", 1.5)
        if rtr_threshold == 0:
            rtr_threshold = 1.5

        # Partition samples by step and compute mean RTR
        step_labels: list[str] = []
        rtr_means: list[float] = []
        colors: list[str] = []
        sample_offset = 0

        for step in step_results:
            step_sample_count = step.get("sample_count", 0)
            step_samples = samples[sample_offset : sample_offset + step_sample_count]
            sample_offset += step_sample_count

            rtr_vals = [
                s["rtr"]["rtr"]
                for s in step_samples
                if s.get("rtr") is not None and "rtr" in s.get("rtr", {})
            ]

            mean_rtr = sum(rtr_vals) / len(rtr_vals) if rtr_vals else 0.0
            step_labels.append(f"{step['multiplier']}x")
            rtr_means.append(mean_rtr)

            if mean_rtr < rtr_threshold:
                colors.append("red")
            elif mean_rtr < 0.95:
                colors.append("#FFA500")  # orange/yellow
            else:
                colors.append("green")

        if not rtr_means:
            return []

        fig = go.Figure(
            data=[
                go.Bar(
                    x=step_labels,
                    y=rtr_means,
                    marker_color=colors,
                    text=[f"{v:.2f}x" for v in rtr_means],
                    textposition="auto",
                )
            ]
        )

        fig.add_hline(
            y=0.95, line_dash="dot", line_color="green", annotation_text="0.95 (keeping pace)"
        )
        fig.add_hline(
            y=rtr_threshold,
            line_dash="dash",
            line_color="darkred",
            annotation_text=f"{rtr_threshold} threshold",
        )

        y_max = max(rtr_means) * 1.3 if rtr_means else 1.5
        y_max = max(y_max, 1.1)

        fig.update_layout(
            title="Speed Scaling: Mean RTR Per Step",
            xaxis_title="Speed Multiplier",
            yaxis_title="RTR (1.0 = perfect)",
            yaxis_range=[0, y_max],
        )

        return _write_chart(fig, self.charts_dir / "speed_rtr")

    def generate_duration_phase_comparison(self, duration_scenario: dict[str, Any]) -> list[str]:
        """Generate grouped bar chart comparing memory at end-of-active vs end-of-cooldown.

        Color: green if cooldown < active (memory released), red if retained.
        """
        cooldown_analysis = duration_scenario.get("metadata", {}).get("cooldown_analysis", {})
        if not cooldown_analysis:
            return []

        containers = _sort_containers(set(cooldown_analysis.keys()))
        display_names = [_get_display_name(c) for c in containers]

        active_end_values = [cooldown_analysis[c].get("active_end_mb", 0) for c in containers]
        cooldown_end_values = [cooldown_analysis[c].get("cooldown_end_mb", 0) for c in containers]

        # Color per container: green if released, red if retained
        cooldown_colors = [
            "green" if cooldown_analysis[c].get("memory_released", False) else "red"
            for c in containers
        ]

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=display_names,
                y=active_end_values,
                name="End of Active",
                marker_color="steelblue",
                text=[f"{v:.0f}" for v in active_end_values],
                textposition="auto",
            )
        )
        fig.add_trace(
            go.Bar(
                x=display_names,
                y=cooldown_end_values,
                name="End of Cooldown",
                marker_color=cooldown_colors,
                text=[f"{v:.0f}" for v in cooldown_end_values],
                textposition="auto",
            )
        )

        fig.update_layout(
            title="Duration: Memory at End of Active vs End of Cooldown",
            xaxis_title="Container",
            yaxis_title="Memory (MB)",
            barmode="group",
            xaxis_tickangle=-45,
        )

        return _write_chart(fig, self.charts_dir / "duration_phase_comparison")

    def _create_scenario_subdirs(self) -> dict[str, Path]:
        """Create subdirectories for organizing charts by scenario type."""
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
        """Generate charts organized into scenario subdirectories."""
        subdirs = self._create_scenario_subdirs()
        chart_paths: dict[str, list[str]] = {key: [] for key in subdirs}

        scenarios = results.get("scenarios", [])

        # Overview charts (heatmaps)
        if scenarios:
            original_dir = self.charts_dir
            self.charts_dir = subdirs["overview"]
            chart_paths["overview"].extend(self.generate_cpu_heatmap(scenarios))
            chart_paths["overview"].extend(self.generate_memory_heatmap(scenarios))
            chart_paths["overview"].extend(self.generate_memory_percent_heatmap(scenarios))
            self.charts_dir = original_dir

        # Baseline charts
        baseline_scenarios = [s for s in scenarios if s["scenario_name"] == "baseline"]
        if baseline_scenarios:
            original_dir = self.charts_dir
            self.charts_dir = subdirs["overview"]
            chart_paths["overview"].extend(self.generate_baseline_resources(baseline_scenarios[0]))
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
            chart_paths["duration"].extend(
                self.generate_duration_phase_comparison(duration_scenarios[0])
            )
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
            chart_paths["stress"].extend(self.generate_stress_agent_resource(stress_scenarios[0]))
            self.charts_dir = original_dir

        # Speed scaling charts
        speed_scenarios = [s for s in scenarios if s["scenario_name"] == "speed_scaling"]
        if speed_scenarios:
            original_dir = self.charts_dir
            self.charts_dir = subdirs["speed_scaling"]
            chart_paths["speed_scaling"].extend(
                self.generate_speed_scaling_chart(speed_scenarios[0])
            )
            chart_paths["speed_scaling"].extend(self.generate_speed_rtr_chart(speed_scenarios[0]))
            self.charts_dir = original_dir

        # Generate index page
        index_path = self.generate_index_html(chart_paths)
        if index_path:
            chart_paths["overview"].insert(0, str(index_path))

        return chart_paths

    def generate_index_html(self, chart_paths: dict[str, list[str]]) -> Path | None:
        """Generate HTML navigation page linking all charts."""
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

            seen_bases: set[str] = set()
            for path in paths:
                p = Path(path)
                base_name = p.stem
                if base_name in seen_bases:
                    continue
                seen_bases.add(base_name)

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


def _add_phase_annotations(
    fig: go.Figure,
    phase_timestamps: dict[str, float],
    reference_start: float,
    num_rows: int,
) -> None:
    """Add phase shaded regions (active/drain/cooldown) to duration timeline.

    Args:
        fig: Plotly figure with subplots.
        phase_timestamps: Dict with active_start, active_end, drain_start, etc.
        reference_start: The first sample timestamp (used as t=0 reference).
        num_rows: Number of subplot rows.
    """
    phases = [
        ("active_start", "active_end", "rgba(0, 200, 0, 0.08)", "Active"),
        ("drain_start", "drain_end", "rgba(255, 200, 0, 0.08)", "Drain"),
        ("cooldown_start", "cooldown_end", "rgba(0, 100, 255, 0.08)", "Cooldown"),
    ]

    for start_key, end_key, color, label in phases:
        start_ts = phase_timestamps.get(start_key)
        end_ts = phase_timestamps.get(end_key)
        if start_ts is None or end_ts is None:
            continue

        x0 = (start_ts - reference_start) / 60
        x1 = (end_ts - reference_start) / 60

        for row in range(1, num_rows + 1):
            fig.add_vrect(
                x0=x0,
                x1=x1,
                fillcolor=color,
                layer="below",
                line_width=0,
                row=row,
                col=1,
            )

        # Add label on first row only
        fig.add_annotation(
            x=(x0 + x1) / 2,
            y=1.02,
            text=label,
            showarrow=False,
            xref="x",
            yref="paper",
            font={"size": 10, "color": "gray"},
        )
