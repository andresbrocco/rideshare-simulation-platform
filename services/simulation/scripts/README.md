# Simulation Scripts

> Developer utilities for load testing the simulation API, benchmarking infrastructure components, monitoring driver state, and exporting the OpenAPI schema.

## Quick Reference

### Commands

All scripts are run from the `services/simulation/` directory.

#### Load Test

Ramps agents up over a configurable window to discover performance limits, then holds at peak load. Outputs a CSV of time-series snapshots.

```bash
./venv/bin/python scripts/load_test.py \
  --max-drivers 500 \
  --max-riders 2000 \
  --ramp-duration 300 \
  --hold-duration 120 \
  --api-url http://localhost:8000 \
  --api-key admin \
  --output load_test_results.csv
```

| Flag | Default | Description |
|------|---------|-------------|
| `--max-drivers` | `500` | Maximum drivers to create |
| `--max-riders` | `2000` | Maximum riders to create |
| `--ramp-duration` | `300` | Seconds for ramp-up phase (10 equal steps) |
| `--hold-duration` | `120` | Seconds to hold at peak load |
| `--api-url` | `http://localhost:8000` | Simulation API base URL |
| `--api-key` | `dev-api-key-change-in-production` | `X-API-Key` header value |
| `--output` | `load_test_results.csv` | CSV output path |

#### Export OpenAPI Schema

Instantiates the FastAPI app with mocked dependencies and writes the schema to `schemas/api/openapi.json`. Safe to run in CI with no services running.

```bash
./venv/bin/python scripts/export-openapi.py
```

No flags. Output is always written to `schemas/api/openapi.json` (four directory levels up from the script).

#### Monitor Driver Status

Polls `/simulation/status` every 5 seconds for 30 samples (2.5 minutes total) and prints a recovery analysis.

```bash
./venv/bin/python scripts/monitor_drivers.py
```

API URL and key are hardcoded constants at the top of the file (`http://localhost:8000`, `dev-api-key-change-in-production`). Edit directly to change targets.

### Performance Benchmarks (`perf/`)

Each benchmark targets a specific infrastructure component directly, independent of the simulation service.

#### OSRM Routing Benchmark

```bash
./venv/bin/python scripts/perf/test_osrm.py \
  --osrm-url http://localhost:5050 \
  --concurrency 10 \
  --requests 100
```

| Flag | Default | Description |
|------|---------|-------------|
| `--osrm-url` | `http://localhost:5050` | OSRM base URL |
| `--concurrency` | `10` | Concurrent request threads |
| `--requests` | `100` | Total route requests |

#### Kafka Producer Benchmark

```bash
./venv/bin/python scripts/perf/test_kafka.py \
  --bootstrap-servers localhost:9092 \
  --topic test-benchmark \
  --messages 10000 \
  --batch-size 16384
```

| Flag | Default | Description |
|------|---------|-------------|
| `--bootstrap-servers` | `localhost:9092` | Kafka bootstrap servers |
| `--topic` | `test-benchmark` | Topic to produce to |
| `--messages` | `10000` | Total messages to produce |
| `--batch-size` | `16384` | Producer batch size (bytes) |

#### Redis Pub/Sub Benchmark

Runs two sub-benchmarks: raw publish throughput and end-to-end pub/sub lag.

```bash
./venv/bin/python scripts/perf/test_redis.py \
  --redis-host localhost \
  --redis-port 6379 \
  --messages 10000 \
  --channel test-channel
```

| Flag | Default | Description |
|------|---------|-------------|
| `--redis-host` | `localhost` | Redis host |
| `--redis-port` | `6379` | Redis port |
| `--messages` | `10000` | Messages for publish benchmark (lag benchmark caps at 1000) |
| `--channel` | `test-channel` | Channel name (lag benchmark appends `-lag`) |

#### WebSocket Benchmark

Spawns concurrent async WebSocket clients and measures connection time and message receipt rate.

```bash
./venv/bin/python scripts/perf/test_websocket.py \
  --ws-url ws://localhost:8000/ws \
  --api-key admin \
  --clients 50 \
  --duration 30
```

| Flag | Default | Description |
|------|---------|-------------|
| `--ws-url` | `ws://localhost:8000/ws` | WebSocket endpoint |
| `--api-key` | `dev-api-key-change-in-production` | Passed as `Sec-WebSocket-Protocol: apikey.<key>` |
| `--clients` | `50` | Concurrent WebSocket clients |
| `--duration` | `30` | Test duration in seconds |

### Prerequisites

- Docker stack running: `docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline up -d`
- For `load_test.py` and `monitor_drivers.py`: simulation API reachable at port `8000`
- For `perf/test_osrm.py`: OSRM reachable at port `5050`
- For `perf/test_kafka.py`: Kafka reachable at port `9092`
- For `perf/test_redis.py`: Redis reachable at port `6379`
- For `perf/test_websocket.py`: simulation API reachable and simulation running
- For `export-openapi.py`: no services needed (uses mocked dependencies)

## Common Tasks

### Run a full load test

```bash
# 1. Verify the simulation API is up
curl -s -H "X-API-Key: admin" http://localhost:8000/simulation/status | python3 -m json.tool

# 2. Run the load test (script will start the simulation automatically if stopped)
cd services/simulation
./venv/bin/python scripts/load_test.py --api-key admin --max-drivers 200 --max-riders 800

# 3. Results are written to load_test_results.csv in the current directory
```

### Regenerate the OpenAPI schema after API changes

```bash
cd services/simulation
./venv/bin/python scripts/export-openapi.py
# Output: schemas/api/openapi.json
```

### Benchmark a specific infrastructure component

```bash
cd services/simulation

# OSRM
./venv/bin/python scripts/perf/test_osrm.py --concurrency 20 --requests 200

# Kafka
./venv/bin/python scripts/perf/test_kafka.py --messages 50000

# Redis
./venv/bin/python scripts/perf/test_redis.py --messages 20000

# WebSocket (simulation must be running with agents)
./venv/bin/python scripts/perf/test_websocket.py --api-key admin --clients 100 --duration 60
```

### Record benchmark results

Fill in `scripts/perf/RESULTS_TEMPLATE.md` after running benchmarks to track performance over time.

## Troubleshooting

**`load_test.py` exits with "Cannot connect to API"**
The simulation API is not reachable at the configured `--api-url`. Verify the Docker stack is running and the correct port is mapped (`8000` by default).

**`export-openapi.py` fails with import errors**
Run from inside `services/simulation/` so the relative `sys.path` insertion resolves correctly. The script adds `../src` relative to its own location.

**`perf/test_kafka.py` errors with "Make sure Kafka is running"**
Kafka must be reachable at `--bootstrap-servers`. In Docker, use `localhost:9092` (the external listener port mapped in `compose.yml`).

**`perf/test_redis.py` reports 0% delivery in the pub/sub lag sub-benchmark**
The subscriber thread has a 0.5s startup delay; if messages are published faster than the subscriber connects, early messages are lost. This is expected for very small message counts — use `--messages 1000` or more.

**`load_test.py` stops early with "SATURATION DETECTED"**
Saturation thresholds are: OSRM p95 > 500ms, memory RSS > 2GB. This is expected behavior when the simulation reaches its performance ceiling. Review the CSV output to identify the bottleneck.

## Related

- [CONTEXT.md](CONTEXT.md) — Script design decisions and non-obvious details
- [services/simulation/src/api](../src/api/CONTEXT.md) — FastAPI endpoints called by load_test.py and monitor_drivers.py
- [schemas/api/](../../../schemas/api/) — Output location for export-openapi.py
