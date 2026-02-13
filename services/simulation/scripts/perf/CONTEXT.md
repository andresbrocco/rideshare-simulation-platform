# CONTEXT.md — Performance Benchmarking

## Purpose

Isolated performance benchmarks for individual infrastructure components (OSRM, Kafka, Redis, WebSocket) that the simulation depends on. These scripts test each component independently to establish baseline performance and identify bottlenecks before they manifest in the full simulation.

## Responsibility Boundaries

- **Owns**: Standalone benchmarking of infrastructure components with synthetic workloads
- **Delegates to**: The actual infrastructure services being tested
- **Does not handle**: End-to-end simulation performance testing (that lives in `tests/performance/`)

## Key Concepts

**Isolated Testing**: Each benchmark script runs independently without requiring the simulation to be running. They connect directly to infrastructure services (OSRM, Kafka, Redis, WebSocket API) to measure raw performance characteristics.

**Metrics Focus**: Scripts measure throughput (requests/sec, messages/sec), latency percentiles (p50, p95, p99), and connection capacity rather than business logic correctness.

**RESULTS_TEMPLATE.md**: Provides a structured template for documenting benchmark results including environment setup, identified bottlenecks, and saturation indicators.

## Non-Obvious Details

The WebSocket benchmark (`test_websocket.py`) cannot calculate true end-to-end latency because it requires synchronized clocks between client and server. It measures connection time and message reception rates instead.

Redis benchmark runs two separate tests: publish throughput (single-threaded sequential) and pub/sub lag (with separate publisher and subscriber threads) to capture both producer and consumer perspectives.

Kafka benchmark tracks both "produce latency" (time to queue message locally) and "delivery latency" (end-to-end confirmation time with acks=all) because they reveal different bottlenecks.

## Related Modules

- **[tests/performance](../../../../tests/performance/CONTEXT.md)** — End-to-end simulation performance testing that builds on baselines established by these component benchmarks
- **[infrastructure/docker](../../../../infrastructure/docker/CONTEXT.md)** — Docker Compose infrastructure that provides the services these benchmarks test against
- **[services/kafka](../../../kafka/CONTEXT.md)** — Kafka broker configuration that affects benchmark results; topic partition counts impact throughput
