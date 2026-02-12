# Performance Testing Framework

A performance testing framework to measure container resource usage, detect memory leaks, and find resource thresholds for the rideshare simulation platform.

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

This runs all four scenarios in sequence:
1. **Baseline** - Measure idle resource usage
2. **Stress Test** - Find maximum sustainable agent count
3. **Duration/Leak** - 3-phase lifecycle observation (active + drain + cooldown)
4. **Speed Scaling** - Double speed multiplier each step until threshold

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

### Stress Test
- Spawns agents in batches until CPU or memory threshold reached
- CPU thresholds are per-container: scaled by effective cores (e.g., 90% * 1.5 cores = 135%)
- Determines maximum sustainable agent count
- Records which container and metric triggered the stop
- Provides the agent count used for duration and speed scaling tests

### Duration/Leak Detection (3-phase)
Runs through an explicit lifecycle with per-phase sampling rates:

| Phase | Duration | Sampling | What happens |
|-------|----------|----------|--------------|
| **Active** | 5 min | 2s | Agents running, trips cycling |
| **Drain** | Variable | 4s | `pause()` called, wait for DRAINING -> PAUSED |
| **Cooldown** | 10 min | 8s | System idle, observe resource release |

- Analyzes memory/CPU slope per phase per container
- Compares memory at cooldown end vs active end to detect resource retention
- Flags leak if active phase slope > 1 MB/min

### Speed Scaling
- Doubles speed multiplier each step: 2x, 4x, 8x, ..., up to 1024x
- Agent count inversely proportional to speed: `base_count // multiplier`
- Each step: reset, set speed, spawn agents, collect 8 minutes of samples
- Stops when resource threshold hit or max multiplier reached

## Execution Flow

```
START
  |
  v
+--------------+
|  1. Baseline |  (30s, 0 agents)
|    Measure   |
| idle resources|
+------+-------+
       |
       v
+--------------+
| 2. Stress    |  (until threshold)
|    Test      |
|  Find max    |
|  agents      |
+------+-------+
       |
       +---- OOM or < 2 agents? -----> FAIL (save partial results)
       |
       v
+----------------------------------+
| Extract drivers_queued from      |
| stress test metadata             |
| duration_agents = drivers // 2   |
+----------------------------------+
       |
       v
+--------------+
| 3. Duration  |  (5m active + drain + 10m cooldown)
|    Leak Test |
|  3-phase     |
|  lifecycle   |
+------+-------+
       |
       v
+--------------+
| 4. Speed     |  (2x -> 1024x, 8m/step)
|    Scaling   |
|  Test speed  |
|  limits      |
+------+-------+
       |
       v
+--------------+
|   Analysis   |
|   & Reports  |
+--------------+
```

## Test Protocol

All scenarios follow this protocol:

1. **Step 0: Clean Environment**
   ```bash
   docker compose ... down -v  # Remove volumes for clean state
   docker compose ... up -d    # Start fresh
   # Wait for all services healthy
   ```

2. **Warmup/Settle periods** (configurable)
3. **Metric sampling** every 2s via cAdvisor (per-phase rates for duration test)
4. **OOM detection** via container restart counts

## CPU Measurement

CPU values from cAdvisor are **not clamped** at 100%. Multi-core containers (e.g., Kafka at 1.5 cores, Trino at 2.0 cores) can report usage above 100%. Stress test thresholds are scaled accordingly:

| Container | Effective Cores | Threshold (at 90% base) |
|-----------|----------------|------------------------|
| simulation | 1.0 | 90% |
| kafka | 1.5 | 135% |
| trino | 2.0 | 180% |

## Output

Results are saved to `tests/performance/results/<timestamp>/`:

### JSON Structure (`results.json`)
```json
{
  "test_id": "20260130_143022",
  "started_at": "2026-01-30T14:30:22Z",
  "completed_at": "2026-01-30T14:45:18Z",
  "config": { ... },
  "derived_config": {
    "duration_agent_count": 25,
    "stress_drivers_queued": 50
  },
  "scenarios": [
    {
      "scenario_name": "baseline",
      "scenario_params": {...},
      "samples": [...],
      "oom_events": [],
      "aborted": false
    },
    {
      "scenario_name": "stress_test",
      "metadata": {
        "drivers_queued": 50,
        "trigger": {"container": "rideshare-simulation", "metric": "memory", "value": 91.2}
      }
    },
    {
      "scenario_name": "duration_leak",
      "metadata": {
        "phase_timestamps": {"active_start": ..., "active_end": ..., ...},
        "phase_sample_counts": {"active": 150, "drain": 12, "cooldown": 75},
        "cooldown_analysis": {"rideshare-simulation": {"delta_mb": -12.5, "memory_released": true}}
      }
    },
    {
      "scenario_name": "speed_scaling",
      "metadata": {
        "step_results": [{"multiplier": 2, "agent_count": 25, "threshold_hit": false}, ...],
        "max_speed_achieved": 64,
        "stopped_by_threshold": true
      }
    }
  ],
  "analysis": {...}
}
```

### Generated Charts (`charts/`)
- `overview/cpu_heatmap.html` + `.png` - CPU usage across scenarios/containers
- `overview/memory_heatmap.html` + `.png` - Memory usage across scenarios/containers
- `duration/duration_timeline_*.html` + `.png` - Memory over time for leak detection
- `stress/stress_timeline_*.html` + `.png` - Resource usage during stress test
- `stress/stress_comparison_*.html` + `.png` - Peak usage by container
- `speed_scaling/speed_scaling_*.html` + `.png` - Mean CPU/memory per speed step

## Configuration

Edit `config.py` to customize:

- `APIConfig`: Simulation API URL and credentials
- `DockerConfig`: cAdvisor URL, compose file path
- `SamplingConfig`: Interval, warmup, settle times, per-phase intervals
- `ScenarioConfig`: Duration times, stress thresholds, speed scaling settings

## OOM Handling

- OOM events are detected via `docker inspect` restart count changes
- When OOM occurs:
  1. Event is logged with timestamp and container
  2. Scenario is marked as aborted
  3. If stress test OOMs, duration and speed scaling tests cannot run (insufficient data)
- Memory warnings logged when usage exceeds 95%

## Interpreting Results

### Stress Test Threshold
The stress test stops when any container reaches its CPU or memory threshold:
- CPU thresholds are per-container (scaled by effective cores)
- Records which container/metric triggered the stop
- The number of drivers queued determines the duration and speed scaling agent counts
- If < 2 drivers queued, the test fails (insufficient capacity)

### Leak Detection
Memory slope in MB/min (from active phase):
- `< 0.5`: Normal fluctuation
- `0.5 - 1.0`: Monitor closely
- `> 1.0`: Potential leak, investigate

### Cooldown Analysis
Compares memory at cooldown end vs active end:
- Negative delta: Memory released (healthy)
- Positive delta: Memory retained (potential concern)

### Speed Scaling
- Higher max speed = better performance headroom
- If threshold hit early, indicates CPU-bound workload at speed

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
- Increase container memory limits in `compose.yml`
- If stress test OOMs immediately, check baseline memory usage
