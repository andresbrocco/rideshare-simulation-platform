# CONTEXT.md — Performance

## Purpose

Infrastructure capacity testing framework for the rideshare platform. Runs controlled load scenarios against a live Docker stack, collects container resource metrics and simulation telemetry, and produces statistical reports and charts. Answers questions about maximum sustainable load, speed multiplier limits, memory leak presence, and saturation headroom.

## Responsibility Boundaries

- **Owns**: Test scenario orchestration, metric collection, statistical analysis, report and chart generation
- **Delegates to**: Simulation API (agent control), Prometheus (container metrics and simulation state), Docker lifecycle (stack up/down/health)
- **Does not handle**: Pytest-style unit/integration testing — this is a standalone CLI tool invoked via `python -m tests.performance`

## Key Concepts

- **RTR (Real-Time Ratio)**: The ratio of simulated time to wall-clock time. An RTR of 1.0 means the simulation runs at real-time speed. RTR collapse (dropping below ~0.67) is a primary stop condition for stress and speed-scaling scenarios.
- **Baseline calibration**: The `baseline` scenario runs first and establishes mean RTR and health latency values used to set dynamic stop-condition thresholds for subsequent scenarios. If stress or speed runs without baseline data, dynamic thresholds fall back to static config values.
- **Four scenarios in pipeline order**:
  1. `baseline` — short idle measurement; calibrates thresholds
  2. `stress` — spawns agents in batches until CPU/memory/RTR ceiling; uniquely reuses the previous scenario's Docker containers rather than doing a clean restart
  3. `speed` — fixes agent count, doubles speed multiplier each step until threshold hit
  4. `duration` — 3-phase lifecycle (active → drain → cooldown) for memory leak detection
- **USL (Universal Scalability Law) fitting**: During the stress scenario, active trip count vs throughput is curve-fit using USL to predict a saturation knee point. The fit is only trusted when R² > 0.80 and at least 8 data points exist.
- **OOM detection**: Monitors Docker container restart counts between samples; an increase in restart count is treated as an OOM kill and aborts the scenario immediately.

## Non-Obvious Details

- The `stress` scenario sets `requires_clean_restart = False`, meaning it inherits whatever container state the baseline scenario left behind. All other scenarios do a full `docker compose down -v && up -d` before executing.
- CPU percentage in samples is per-container as a fraction of one logical core (not total host CPU), but `global_cpu_percent` sums all containers and is compared against detected Docker CPU core count for saturation decisions.
- `CONTAINER_CPU_CORES` in `config.py` tracks effective CPU parallelism per container separately from Docker resource limits. The simulation container is capped at 1.0 core despite a 2.0 Docker limit because of the Python GIL.
- Health latency thresholds (`degraded`/`unhealthy`) are sourced from `services/prometheus/rules/performance.yml` at analysis time, not hardcoded in this package.
- The `analyze` CLI subcommand can re-run the analysis phase against a previously saved JSON result file without re-running any scenarios, enabling iterative tuning of reporting logic.
- Results are written to `tests/performance/results/` by default. Each run produces a timestamped JSON file plus charts and a markdown report.

## Related Modules

- [tests/performance/analysis](analysis/CONTEXT.md) — Shares Data Quality & Validation domain (baseline calibration)
