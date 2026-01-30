# Performance Testing Framework

A performance testing framework to measure container resource usage, detect memory leaks, and generate resource scaling formulas for the rideshare simulation platform.

## Prerequisites

1. **Docker Compose profiles running:**
   ```bash
   docker compose -f infrastructure/docker/compose.yml \
     --profile core --profile data-pipeline --profile monitoring --profile analytics up -d
   ```

2. **Python dependencies (use simulation venv):**
   ```bash
   ./services/simulation/venv/bin/pip install -r tests/performance/requirements.txt
   ```

## Usage

Run from the project root directory using the simulation venv.

### Run All Tests
```bash
./services/simulation/venv/bin/python -m tests.performance.runner run
```

### Run Specific Scenarios
```bash
# Baseline only (0 agents)
./services/simulation/venv/bin/python -m tests.performance.runner run -s baseline

# Load scaling only (10, 20, 40, 80 agents)
./services/simulation/venv/bin/python -m tests.performance.runner run -s load

# Duration/leak tests only (1, 2, 4, 8 minutes)
./services/simulation/venv/bin/python -m tests.performance.runner run -s duration

# Reset behavior only
./services/simulation/venv/bin/python -m tests.performance.runner run -s reset
```

### Check Service Status
```bash
./services/simulation/venv/bin/python -m tests.performance.runner check
```

### Re-analyze Existing Results
```bash
./services/simulation/venv/bin/python -m tests.performance.runner analyze tests/performance/results/<timestamp>/results.json
```

## Test Scenarios

### Baseline (0 agents)
- Measures resource usage with no agents active
- 10s warmup, 30s sampling at 2s intervals
- Establishes baseline for comparison

### Load Scaling (10/20/40/80 agents)
- Spawns N drivers + N riders with `mode=immediate`
- Each agent level gets a clean environment restart
- 5s settle time, 60s sampling
- Generates scaling formulas (linear, power, log, exponential)

### Duration/Leak Detection (1/2/4/8 minutes)
- Fixed load (40 agents) for extended periods
- Detects memory leaks via slope analysis
- Flags leak if slope > 1 MB/min

### Reset Behavior
- Verifies memory returns to baseline after reset
- Compares pre-load, under-load, and post-reset metrics
- Passes if post-reset within 10% of baseline

## Test Protocol

All scenarios follow this protocol:

1. **Step 0: Clean Environment**
   ```bash
   docker compose ... down -v  # Remove volumes for clean state
   docker compose ... up -d    # Start fresh
   # Wait for all services healthy
   ```

2. **Warmup/Settle periods** (configurable)
3. **Metric sampling** every 2 seconds via cAdvisor
4. **OOM detection** via container restart counts

## Output

Results are saved to `tests/performance/results/<timestamp>/`:

### JSON Structure (`results.json`)
```json
{
  "test_id": "20260130_143022",
  "started_at": "2026-01-30T14:30:22Z",
  "completed_at": "2026-01-30T14:45:18Z",
  "config": { ... },
  "scenarios": [
    {
      "scenario_name": "load_scaling_40",
      "scenario_params": {"drivers": 40, "riders": 40},
      "samples": [...],
      "oom_events": [],
      "aborted": false
    }
  ],
  "analysis": {
    "rideshare-simulation": {
      "best_fit": {
        "fit_type": "linear",
        "formula": "memory_mb = 2.45 * agents + 312.5",
        "r_squared": 0.987
      }
    }
  }
}
```

### Generated Charts (`charts/`)
- `load_scaling_bar.html` + `.png` - Memory by container at each load level
- `load_scaling_line.html` + `.png` - Memory vs agents with trend line
- `duration_timeline.html` + `.png` - Memory over time for leak detection
- `reset_comparison.html` + `.png` - Before/after reset comparison
- `cpu_heatmap.html` + `.png` - CPU usage across scenarios/containers
- `curve_fits.html` + `.png` - Scatter plot with all fit models

## Configuration

Edit `config.py` to customize:

- `APIConfig`: Simulation API URL and credentials
- `DockerConfig`: cAdvisor URL, compose file path
- `SamplingConfig`: Interval, warmup, settle times
- `ScenarioConfig`: Load levels, duration times, tolerances

## OOM Handling

- OOM events are detected via `docker inspect` restart count changes
- When OOM occurs:
  1. Event is logged with timestamp and container
  2. Scenario is marked as aborted
  3. Testing continues with next scenario
- Memory warnings logged when usage exceeds 95%

## Interpreting Results

### Scaling Formula
The best-fit formula predicts memory usage based on agent count:
- **Linear**: `memory = slope * agents + intercept` - Good for stable systems
- **Power**: `memory = a * agents^b + c` - Sub-linear growth is efficient
- **Exponential**: Watch out! Memory grows faster than agent count

### Leak Detection
Memory slope in MB/min:
- `< 0.5`: Normal fluctuation
- `0.5 - 1.0`: Monitor closely
- `> 1.0`: Potential leak, investigate

### Reset Effectiveness
Post-reset memory should be within 10% of baseline:
- **PASS**: Memory properly released
- **FAIL**: Memory not fully released, possible leak

## Troubleshooting

### cAdvisor not available
```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d
```

### Simulation API not available
```bash
docker compose -f infrastructure/docker/compose.yml --profile core up -d
```

### Tests timing out
- Increase `timeout` in config
- Check container health with `runner.py check`
- View logs: `docker compose ... logs simulation`

### OOM errors during tests
- Reduce `load_levels` in config
- Increase container memory limits in `compose.yml`
- Run fewer scenarios at once
