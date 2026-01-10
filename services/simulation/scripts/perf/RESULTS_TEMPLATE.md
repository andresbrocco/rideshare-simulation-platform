# Performance Test Results

## Test Environment

| Property | Value |
|----------|-------|
| Date | YYYY-MM-DD |
| Machine | [CPU, RAM] |
| Docker Resources | [CPUs, Memory] |
| OS | [macOS/Linux version] |

## Test Parameters

| Parameter | Value |
|-----------|-------|
| Max Drivers | |
| Max Riders | |
| Ramp Duration | |
| Hold Duration | |

## Results Summary

### Agent Capacity

| Metric | Value |
|--------|-------|
| Max Drivers Achieved | |
| Max Riders Achieved | |
| Saturation Point | |

### Event Throughput

| Event Type | Rate (events/sec) |
|------------|-------------------|
| GPS Pings | |
| Trip Events | |
| Driver Status | |
| **Total** | |

### Latency

| Component | Avg (ms) | p95 (ms) | p99 (ms) |
|-----------|----------|----------|----------|
| OSRM | | | |
| Kafka | | | |
| Redis | | | |

### Resource Usage

| Resource | Peak Value |
|----------|------------|
| Memory (RSS) | |
| CPU | |
| Active Trips | |

## Bottleneck Analysis

### Identified Bottlenecks

1. **[Component]**: [Description of bottleneck]
   - Impact: [How it affects performance]
   - Threshold: [When it becomes problematic]

### Saturation Indicators

- [ ] OSRM latency > 500ms
- [ ] Memory usage > 2GB
- [ ] Event rate declining
- [ ] WebSocket lag increasing

## Recommendations

### Immediate Optimizations

1. [Recommendation]
2. [Recommendation]

### Future Improvements

1. [Improvement]
2. [Improvement]

## Raw Data

See `load_test_results.csv` for detailed time-series data.

## Individual Component Benchmarks

### OSRM Benchmark

```
./venv/bin/python scripts/perf/test_osrm.py --concurrency 10 --requests 100
```

| Metric | Value |
|--------|-------|
| Throughput | req/sec |
| Avg Latency | ms |
| p95 Latency | ms |

### Redis Benchmark

```
./venv/bin/python scripts/perf/test_redis.py --messages 10000
```

| Metric | Value |
|--------|-------|
| Publish Throughput | msg/sec |
| Avg Pub/Sub Lag | ms |

### Kafka Benchmark

```
./venv/bin/python scripts/perf/test_kafka.py --messages 10000
```

| Metric | Value |
|--------|-------|
| Throughput | msg/sec |
| Delivery Latency | ms |

### WebSocket Benchmark

```
./venv/bin/python scripts/perf/test_websocket.py --clients 50 --duration 30
```

| Metric | Value |
|--------|-------|
| Max Connections | |
| Avg Message Rate | msg/sec/client |
| Connection Time | ms |
