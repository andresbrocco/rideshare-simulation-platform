# Performance Testing Framework

> Container resource measurement and performance characterization through sequential test scenarios

## Quick Reference

### Prerequisites

- Docker Compose core profile services running
- Prometheus and cAdvisor running (monitoring profile)

Start required services:
```bash
docker compose -f infrastructure/docker/compose.yml --profile core --profile monitoring up -d
```

### Commands

Run all performance scenarios sequentially:
```bash
./venv/bin/python tests/performance/runner.py run
```

Run specific scenarios:
```bash
# Baseline: measure idle resource usage
./venv/bin/python -m tests.performance run -s baseline

# Stress test: find maximum sustainable agent count
./venv/bin/python -m tests.performance run -s stress

# Stress test with early stop at USL saturation knee
./venv/bin/python -m tests.performance run -s stress --stop-at-knee

# Speed scaling: test doubling speed multiplier until threshold
./venv/bin/python -m tests.performance run -s speed

# Duration/leak: 3-phase lifecycle test at optimal speed
./venv/bin/python -m tests.performance run -s duration
```

Check service status:
```bash
./venv/bin/python tests/performance/runner.py check
```

Re-analyze existing results:
```bash
./venv/bin/python tests/performance/runner.py analyze tests/performance/results/20240213_093022/results.json
```

### Output Directory

Results are written to `tests/performance/results/{test_id}/`:
- `results.json` - Full test data with samples and metadata
- `report.md` / `report.html` - Human-readable summaries
- `charts/` - Per-scenario subdirectories with Plotly visualizations

### Configuration

Key configuration options in `tests/performance/config.py`:

**API Settings:**
```python
base_url: "http://localhost:8000"
api_key: "admin"
timeout: 30.0
```

**Docker Settings:**
```python
cadvisor_url: "http://localhost:8083"
prometheus_url: "http://localhost:9090"
compose_file: "infrastructure/docker/compose.yml"
profiles: ["core", "data-pipeline", "monitoring"]
```

**Sampling Intervals:**
```python
interval_seconds: 2.0           # Normal sampling rate
drain_interval_seconds: 4.0     # During drain phase
cooldown_interval_seconds: 8.0  # During cooldown phase
warmup_seconds: 10.0            # Wait before first sample
```

**Scenario Parameters:**
```python
# Duration test (3-phase: active → drain → cooldown)
duration_active_minutes: 5
duration_cooldown_minutes: 10
duration_drain_timeout_seconds: 600

# Stress test (spawn until threshold)
stress_cpu_threshold_percent: 90.0
stress_memory_threshold_percent: 90.0
stress_spawn_batch_size: 10
stress_spawn_interval_seconds: 3.0

# Speed scaling (double multiplier each step)
speed_scaling_step_duration_minutes: 8
speed_scaling_max_multiplier: 1024
```

**Analysis Thresholds:**
```python
# Memory thresholds
memory_leak_mb_per_min: 1.0
memory_warning_percent: 70.0
memory_critical_percent: 85.0

# CPU thresholds
cpu_warning_percent: 70.0
cpu_critical_percent: 85.0
```

## Test Scenarios

### 1. Baseline
**Purpose:** Measure idle resource usage with simulation stopped.

**Duration:** 30 seconds

**Metrics:**
- Memory baseline for all containers
- CPU baseline for all containers

### 2. Stress Test
**Purpose:** Find maximum sustainable agent count before hitting resource thresholds.

**Strategy:** Spawn agents in batches until CPU ≥90% or Memory ≥90%

**Parameters:**
- Spawn batch size: 10 agents
- Spawn interval: 3 seconds
- Max duration: 30 minutes

**Output:**
- `drivers_queued`: Maximum agent count achieved
- Used to derive agent count for duration test (half of stress max)

### 3. Speed Scaling
**Purpose:** Test simulation stability at increasing speed multipliers.

**Strategy:** Start at 2x speed, double each step, stop when threshold hit

**Parameters:**
- Step duration: 8 minutes per multiplier
- Max multiplier: 1024x
- Agent count: half of stress test max

**Threshold criteria:**
- Simulation cannot keep up with speed (no completed trips)
- CPU or memory exceed limits
- OOM event occurs

**Output:**
- `max_speed_achieved`: Highest stable multiplier
- Used for duration test speed setting

### 4. Duration/Leak Detection
**Purpose:** 3-phase lifecycle test to detect memory leaks and long-running stability issues.

**Phases:**
1. **Active:** Run simulation at optimal speed/agent count
2. **Drain:** Stop spawning, wait for in-flight trips to complete (max 600s)
3. **Cooldown:** Idle simulation for 10 minutes, verify memory returns to baseline

**Parameters:**
- Active duration: 5 minutes
- Cooldown duration: 10 minutes
- Agent count: from stress test (half of max)
- Speed multiplier: from speed scaling test (max stable)

**Leak Detection:**
- Memory growth rate during active phase (>1.0 MB/min triggers warning)
- Memory reset after cooldown (should return within 10% of baseline)

## Common Tasks

### Run Full Test Suite
```bash
# Start services
docker compose -f infrastructure/docker/compose.yml --profile core --profile monitoring up -d

# Wait for services to be ready
sleep 30

# Run tests
./venv/bin/python tests/performance/runner.py run

# View results
open tests/performance/results/$(ls -t tests/performance/results | head -1)/report.html
```

### Customize Thresholds for a Specific Container
```python
# In config.py
thresholds = ThresholdConfig(
    container_overrides={
        "rideshare-simulation": {
            "memory_warning_percent": 75.0,
            "memory_critical_percent": 90.0,
            "cpu_warning_percent": 80.0,
        }
    }
)
```

### Add a New Container to Track
```python
# In config.py - add to CONTAINER_CONFIG
CONTAINER_CONFIG = {
    "rideshare-new-service": {
        "display_name": "New Service",
        "profile": "core"
    },
    # ...
}

# If multi-threaded, also add to CONTAINER_CPU_CORES
CONTAINER_CPU_CORES = {
    "rideshare-new-service": 2.0,  # 2 effective cores
    # ...
}
```

### Debug Why a Scenario Failed
```bash
# Check service status first
./venv/bin/python tests/performance/runner.py check

# Look for OOM events in results.json
jq '.scenarios[].oom_events' tests/performance/results/20240213_093022/results.json

# Check container logs around failure time
docker compose -f infrastructure/docker/compose.yml logs rideshare-simulation --since 5m
```

## Troubleshooting

### "Prometheus unavailable" error
**Symptom:** `check` command shows Prometheus as unavailable

**Solution:**
```bash
# Verify monitoring profile is running
docker compose -f infrastructure/docker/compose.yml --profile monitoring ps

# Restart Prometheus
docker compose -f infrastructure/docker/compose.yml --profile monitoring restart prometheus

# Check Prometheus logs
docker compose -f infrastructure/docker/compose.yml logs prometheus

# Verify Prometheus is scraping targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {scrapeUrl, health}'
```

### "Simulation API unavailable" error
**Symptom:** `check` command shows Simulation API as unavailable

**Solution:**
```bash
# Verify core profile is running
docker compose -f infrastructure/docker/compose.yml --profile core ps

# Check simulation logs
docker compose -f infrastructure/docker/compose.yml logs simulation

# Test API manually
curl -H "X-API-Key: admin" http://localhost:8000/api/status
```

### Stress test exits immediately without spawning agents
**Symptom:** Stress scenario completes in <1 minute with 0 agents

**Root cause:** Simulation may be in wrong state or API unreachable

**Solution:**
```bash
# Reset simulation state
curl -X POST -H "X-API-Key: admin" http://localhost:8000/api/reset

# Verify simulation is in READY state
curl -H "X-API-Key: admin" http://localhost:8000/api/status | jq '.state'
```

### Speed scaling test stops at 2x despite low resource usage
**Symptom:** `max_speed_achieved: 2` but CPU/memory are <50%

**Root cause:** Simulation cannot generate events fast enough (event processing bottleneck)

**Solution:**
- This is expected behavior when event loop cannot keep up
- Indicates CPU saturation in single-threaded Python code despite low overall CPU%
- Check `threshold_hit` reason in results.json metadata

### Duration test shows memory leak but cooldown phase not present
**Symptom:** High leak rate but no cooldown samples in results

**Root cause:** OOM during drain phase (trips took >600s to complete)

**Solution:**
```bash
# Increase drain timeout
# In config.py:
duration_drain_timeout_seconds: 1200  # Double timeout

# Or reduce agent count for duration test
# Manually override in runner.py
duration_agent_count = stress_drivers // 3  # Use 1/3 instead of 1/2
```

### Charts not generating after test run
**Symptom:** `results.json` exists but `charts/` directory empty

**Solution:**
```bash
# Re-run analysis to regenerate charts
./venv/bin/python tests/performance/runner.py analyze tests/performance/results/20240213_093022/results.json

# Check for Plotly import errors
./venv/bin/python -c "import plotly; print(plotly.__version__)"
```

### Results show high CPU% but container has multi-core limit
**Symptom:** CPU% exceeds 100 for containers with >1 core Docker limit

**Context:** cAdvisor reports CPU as percentage of single core (200% = 2 full cores used)

**Solution:** This is expected. Thresholds account for effective cores via `get_cpu_cores_for_container()`:
```python
# For rideshare-kafka with 1.5 cores:
# - stress_cpu_threshold = 90.0 * 1.5 = 135%
# - warning_percent = 70.0% (of 150% = 105%)
```

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture and scenario design patterns
- `services/simulation/README.md` — Simulation API reference
- `infrastructure/docker/compose.yml` — Service definitions and profiles
