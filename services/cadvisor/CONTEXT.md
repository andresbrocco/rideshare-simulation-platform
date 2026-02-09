# CONTEXT.md — cAdvisor

## Purpose

Container resource metrics exporter that collects CPU, memory, network, and disk I/O metrics from every running Docker container. Prometheus scrapes cAdvisor to power infrastructure-level dashboards and alerting for the rideshare simulation platform.

## Responsibility Boundaries

- **Owns**: Container metric collection and exposition (CPU, memory, network, disk I/O per container), container metadata discovery via Docker socket
- **Delegates to**: Prometheus for metric scraping, storage, and querying; Grafana for dashboard visualization and alerting
- **Does not handle**: Application-level metrics (those come via OTel Collector), log collection, trace collection, metric storage

## Key Concepts

**Stock Image**: cAdvisor runs as the unmodified `ghcr.io/google/cadvisor:v0.53.0` image with no custom configuration files. All behavior is controlled by volume mounts and Docker Compose settings.

**Privileged Mode**: The container runs in privileged mode to access host-level system metrics. Required volume mounts include `/` (rootfs, read-only), `/var/run` (Docker socket), `/sys` (kernel metrics), `/var/lib/docker` (container metadata), `/dev/disk` (disk stats), and `/dev/kmsg` (kernel messages).

**Prometheus Scrape Target**: cAdvisor exposes metrics on port 8080 (mapped to 8083 on host). Prometheus scrapes this endpoint at the configured interval to collect `container_*` prefixed metrics.

## Non-Obvious Details

The host port mapping is 8083→8080 because port 8080 is already used by Trino in the data-pipeline profile. The Prometheus scrape config targets cAdvisor at `cadvisor:8080` (internal Docker network port, not the host-mapped port).

cAdvisor automatically discovers and monitors all containers on the Docker host, including itself. No per-container configuration is needed.

## Related Modules

- **[services/prometheus](../prometheus/CONTEXT.md)** — Scrapes cAdvisor metrics for storage and querying
- **[services/grafana](../grafana/CONTEXT.md)** — Visualizes container resource metrics from Prometheus
- **[infrastructure/docker](../../infrastructure/docker/CONTEXT.md)** — Deployment orchestration; defines cAdvisor service in monitoring profile
