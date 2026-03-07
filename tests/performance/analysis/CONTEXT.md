# CONTEXT.md — Performance Analysis

## Purpose

Post-processing pipeline for performance test results. Consumes raw time-series samples collected during test scenarios and produces statistical summaries, Plotly charts (HTML + PNG), and multi-format reports (Markdown, HTML, JSON). Also derives dynamic stop-condition thresholds from baseline measurements.

## Responsibility Boundaries

- **Owns**: Statistical computation (percentiles, slopes, linear regression), threshold calibration, chart generation, report formatting, and domain data models for findings
- **Delegates to**: `tests/performance/config` for container display names and configuration; `tests/performance/collectors` for raw sample collection (upstream)
- **Does not handle**: Sample collection, scenario orchestration, or writing results back to the simulation

## Key Concepts

- **RTR (Ride-to-Rate)**: A throughput proxy metric present in sample dicts under the `rtr` key. Used to compute stop-condition thresholds.
- **Baseline calibration**: Before stress scenarios run, a baseline scenario's samples are used to derive per-service health latency thresholds (`degraded` = baseline p95 × multiplier, `unhealthy` = baseline p95 × multiplier). Falls back to config-supplied values when no baseline data is available. The source is tracked as `"baseline-derived"` or `"config-fallback"`.
- **Memory slope**: Linear regression (covariance/variance, not scipy) over time-normalized timestamps gives MB/min growth rate per container — the primary leak detection signal.
- **USL (Universal Scalability Law)**: Data models (`USLFit`, `KneePoint`, `SaturationCurve`, `SaturationFamily`) are defined in `findings.py` but the fitting and curve-building functions in `statistics.py` are entirely commented out. The models exist because `report_generator.py` and `visualizations.py` reference them for saturation reporting.

## Non-Obvious Details

- The USL fitting code (`fit_usl_model`, `detect_knee_point`, `build_saturation_curve`, `extract_saturation_points`) is fully commented out in `statistics.py` with a `# DISABLED` block. The corresponding data models remain active in `findings.py` because the report generator still serializes `SaturationFamily` when present.
- `InfrastructureHeadroomThresholds` in `findings.py` documents that only Kafka lag and SimPy queue saturation are calibrated from test results; CPU/memory headroom use self-contained PromQL formulas and are not computed here.
- The `visualizations.py` `ChartGenerator` prioritizes a fixed list of containers (`_PRIORITY_CONTAINERS`) in chart order, with all others sorted alphabetically appended after.
- `ReportGenerator` produces three files per run: `.md`, `.html`, and `summary.json` — paths returned as `ReportPaths`.

## Related Modules

- [tests/performance](../CONTEXT.md) — Shares PID Controller and Performance Tuning domain (baseline calibration)
- [tests/performance/scenarios](../scenarios/CONTEXT.md) — Reverse dependency — Provides BaseScenario, ScenarioResult, BaselineScenario (+8 more)
