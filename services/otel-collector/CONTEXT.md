# CONTEXT.md — OTel Collector

## Purpose

Central observability gateway that collects, processes, and routes all three telemetry signal types (metrics, logs, traces) from the platform. Acts as the single ingestion point between application services and the backend observability stores (Prometheus, Loki, Tempo).

## Responsibility Boundaries

- **Owns**: Telemetry fan-out routing, Docker log parsing, label promotion for Loki, memory protection
- **Delegates to**: Prometheus (metric storage), Loki (log storage), Tempo (trace storage)
- **Does not handle**: Application instrumentation, alerting rules, dashboard rendering, or log shipping from non-Docker sources

## Key Concepts

**Three independent pipelines**: Metrics, logs, and traces are processed in separate pipelines with different batching parameters. Metrics use a fast 1s batch timeout so Prometheus scrape-push latency is minimal; logs use the slower 5s/1000-record batch for throughput efficiency.

**Filelog replaces Promtail**: Docker container logs are collected directly by the OTel filelog receiver reading `/var/lib/docker/containers/*/*.log`, not via Promtail. This requires mounting the Docker socket directory into the container.

**Two-phase JSON parsing for logs**: Raw Docker log files are JSON-wrapped (`{"log": "...", "time": "..."}`) around the application's own JSON log bodies. The pipeline first parses the Docker envelope (`docker_parser`), then conditionally parses the inner application JSON (`app_log_parser`) only when the `log` field starts with `{`.

**Loki label promotion**: Loki requires attributes to be explicitly promoted to indexed labels via hint attributes (`loki.attribute.labels`, `loki.resource.labels`). The pipeline promotes `level`, `service`, `service_name`, `container_id` as attribute labels and `service.name`, `deployment.environment` as resource labels. Attributes not listed here are stored as unindexed log metadata only.

**service.name propagation**: Application logs carry `service_name` in their JSON body. The `transform/logs` processor copies this into the `resource.attributes["service.name"]` slot so Loki's resource label extraction picks it up correctly.

## Non-Obvious Details

- The Dockerfile copies `wget` from BusyBox into the OTel image solely to enable Docker health checks (`wget -qO- http://localhost:13133/` pattern) — the OTel contrib image has no wget binary by default.
- The `memory_limiter` processor (180 MiB limit, 50 MiB spike allowance) must be the first processor in every pipeline to protect against OOM when ingestion spikes; ordering matters in OTel pipelines.
- The `app_log_parser` uses a conditional (`if: 'attributes.log != nil and attributes.log matches "^\\{"'`) to avoid parse failures on non-JSON log lines (e.g., Python tracebacks or raw stdout).
- OTel Collector self-metrics are exposed on port 8888 (internal telemetry) separately from the health check endpoint on port 13133.
- Version pinned to `0.96.0` per project specification.

## Related Modules

- [infrastructure/docker](../../infrastructure/docker/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/prometheus](../prometheus/CONTEXT.md) — Reverse dependency — Provides rideshare:infrastructure:headroom, rideshare:performance:*, rideshare:container:*
- [services/tempo](../tempo/CONTEXT.md) — Reverse dependency — Consumed by this module
