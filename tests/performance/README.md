# Performance Testing

> Infrastructure capacity testing framework that runs load scenarios against the live Docker stack to measure saturation limits, memory leak behaviour, and speed multiplier ceilings.

## Quick Reference

### Commands

Run from the repository root using `./venv/bin/python3`.

| Command | Description |
|---------|-------------|
| `./venv/bin/python3 -m tests.performance run` | Full 4-scenario pipeline (baseline → stress → speed → duration) |
| `./venv/bin/python3 -m tests.performance run -s baseline` | Baseline only |
| `./venv/bin/python3 -m tests.performance run -s stress` | Stress test only |
| `./venv/bin/python3 -m tests.performance run -s speed --agents 50` | Speed scaling with manual agent count |
| `./venv/bin/python3 -m tests.performance run -s duration --agents 50 --speed 4` | Duration/leak test with explicit parameters |
| `./venv/bin/python3 -m tests.performance run -s stress -s speed` | Stress + speed (agent count derived from stress) |
| `./venv/bin/python3 -m tests.performance check` | Check status of required services |
| `./venv/bin/python3 -m tests.performance analyze <file>` | Re-analyze an existing results JSON without re-running scenarios |

### Prerequisites

The full Docker stack must be running before any scenario executes. Each scenario (except `stress`) does its own `docker compose down -v && up -d` internally, but the stack must be reachable for `check` and `analyze`.

```bash
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-pipeline --profile monitoring up -d
```

### `run` Subcommand Options

| Flag | Default | Description |
|------|---------|-------------|
| `-s / --scenario` | all | Scenario(s) to run. Repeatable. Choices: `baseline`, `stress`, `speed`, `duration` |
| `-a / --agents` | derived from stress | Total agent count for speed/duration (must be even) |
| `-x / --speed` | derived from speed | Speed multiplier for duration test |
| `--baseline-seconds` | 30 | Override baseline measurement duration |
| `--duration-minutes` | 5 | Override duration active phase length |
| `--cooldown-minutes` | 10 | Override cooldown phase length |
| `--stress-max-minutes` | 30 | Cap on stress test wall time |
| `--speed-step-minutes` | 8 | Time per speed-scaling step |
| `--speed-max-multiplier` | 32 | Maximum speed multiplier ceiling |
| `--stop-at-knee` | false | Stop stress at USL knee instead of running to failure |

### Scenario Pipeline

| Order | Name | What it does |
|-------|------|-------------|
| 1 | `baseline` | 30s idle measurement; calibrates dynamic thresholds for downstream scenarios |
| 2 | `stress` | Spawns agents in batches of 19 every 1s until CPU, memory, or RTR ceiling is hit. Reuses baseline containers (no restart). |
| 3 | `speed` | Fixes agent count, doubles speed multiplier each step (2x, 4x, 8x...) until RTR collapse |
| 4 | `duration` | 3-phase lifecycle: active (5 min) → drain → cooldown (10 min) for memory leak detection |

### Service Endpoints Used

| Service | Default URL | Purpose |
|---------|------------|---------|
| Simulation API | `http://localhost:8000` | Agent control and simulation state |
| cAdvisor | `http://localhost:8083` | Container resource metrics |
| Prometheus | `http://localhost:9090` | Simulation telemetry and recording rules |

### Outputs

Results are written to `tests/performance/results/<YYYYMMDD_HHMMSS>/`:

| File | Description |
|------|-------------|
| `results.json` | Raw scenario samples and metadata |
| `summary.json` | Aggregated health, key metrics, suggested thresholds |
| `report.md` | Markdown performance report |
| `report.html` | HTML version of the report |
| `charts/index.html` | Chart gallery |
| `charts/overview/` | CPU and memory heatmaps across all containers |
| `charts/load_scaling/` | Load-scaling bar, line, and USL curve-fit charts |
| `charts/duration/` | Memory/CPU timeline during duration scenario |
| `charts/reset/` | Pre/post-reset comparison charts |

### Stop Conditions

The `stress` and `speed` scenarios terminate when any of the following is detected:

| Condition | Threshold |
|-----------|-----------|
| RTR collapse | RTR rolling avg drops below 0.66 (2/3 of target speed) |
| Per-container CPU | 90% of the container's effective CPU cores |
| Global CPU | 90% of total available Docker CPU cores |
| Container memory | 90% of container memory limit |
| OOM kill | Any container restart count increases |
| Time limit | `stress_max_duration_minutes` (default 30 min) |

### Key Metrics Reported

- **Max agents sustained** before stress trigger
- **Max speed multiplier** achieved without RTR collapse
- **Memory leak rate** (MB/min slope from duration scenario)
- **Service health latency** (baseline p95 vs stressed p95 vs peak)
- **Suggested Prometheus thresholds** derived from observed latencies

## Common Tasks

### Run Only the Stress Test

```bash
./venv/bin/python3 -m tests.performance run -s stress
```

The stress scenario can run without baseline — stop conditions fall back to static config values.

### Re-Analyze Without Re-Running

```bash
./venv/bin/python3 -m tests.performance analyze \
  tests/performance/results/20260131_061316/results.json
```

Regenerates charts and summary JSON from a previously captured results file. Useful when tuning reporting logic.

### Run a Quick Smoke Test

```bash
./venv/bin/python3 -m tests.performance run \
  -s baseline --baseline-seconds 10
```

Completes in ~25 seconds (10s measurement + 10s warmup + settle).

### Run Duration Test with Known Parameters

Use this when the stress/speed pipeline has already been run and you want to re-run only the leak detection phase:

```bash
./venv/bin/python3 -m tests.performance run \
  -s duration --agents 50 --speed 4 \
  --duration-minutes 10 --cooldown-minutes 5
```

`--agents` must be even (split equally between drivers and riders).

## Configuration

Default values are defined in `tests/performance/config.py`. All settings are dataclass fields — no environment variables are read. Override at runtime via CLI flags.

### Monitored Containers

The framework tracks all containers in the configured Docker profiles:

| Container | Profile | Effective CPU Cores |
|-----------|---------|-------------------|
| `rideshare-simulation` | core | 1.0 (Python GIL) |
| `rideshare-kafka` | core | 1.5 |
| `rideshare-redis` | core | 1.0 |
| `rideshare-osrm` | core | 1.0 |
| `rideshare-stream-processor` | core | 1.0 |
| `rideshare-schema-registry` | core | 0.5 |
| `rideshare-control-panel` | core | 1.0 |
| `rideshare-trino` | data-pipeline | 2.0 |
| `rideshare-airflow-webserver` | data-pipeline | 1.0 |
| `rideshare-airflow-scheduler` | data-pipeline | 1.5 |
| `rideshare-bronze-ingestion` | data-pipeline | 0.5 |
| `rideshare-minio` | data-pipeline | 1.0 |
| `rideshare-prometheus` | monitoring | 1.0 |
| `rideshare-cadvisor` | monitoring | 1.0 |
| `rideshare-grafana` | monitoring | 1.0 |

### Sampling Intervals

| Phase | Interval |
|-------|---------|
| Active | 2s |
| Drain | 4s |
| Cooldown | 8s |
| Warmup | 10s settle before sampling begins |

## Troubleshooting

**`--agents` is required when running speed or duration without stress**

Speed and duration scenarios need an agent count. Either include `-s stress` (which derives it automatically) or pass `--agents <even number>` explicitly.

**Stress scenario exits immediately with "No container metrics available"**

The Prometheus or cAdvisor endpoint is unreachable. Run `./venv/bin/python3 -m tests.performance check` to diagnose which services are down.

**Duration test fails with `agent_count must be even`**

The value passed to `--agents` must be divisible by 2 (agents are split equally between drivers and riders).

**Results contain no `duration_leak` scenario data**

`analyze` re-runs analysis against existing JSON — if the original run did not include a `duration` scenario, the leak analysis section will be empty.

**Prometheus rules not updated after run**

The runner attempts to patch `services/prometheus/rules/performance.yml` with empirically-derived saturation divisors after the stress/speed scenarios complete. If the file is not found at that path, the update is skipped with a warning — no data is lost.

**USL curve fit not appearing in charts**

USL fitting requires at least 8 stress data points and R² > 0.80. Early termination (RTR collapse or OOM) before enough data points are collected will skip the USL fit.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context: RTR, baseline calibration, USL fitting, OOM detection
- [scenarios/CONTEXT.md](scenarios/CONTEXT.md) — Scenario internals
- [analysis/CONTEXT.md](analysis/CONTEXT.md) — Statistical analysis and visualization
- [services/prometheus/rules](../../services/prometheus/rules/CONTEXT.md) — Performance recording rules updated by this framework
