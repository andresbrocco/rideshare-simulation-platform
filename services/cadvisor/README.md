# cAdvisor Configuration

cAdvisor v0.53.0 container resource metrics exporter for the rideshare simulation platform.

## Purpose

This directory documents the cAdvisor service. cAdvisor runs as a stock image with no custom configuration files — all settings are defined via volume mounts and Docker Compose.

## Configuration

**Image**: `ghcr.io/google/cadvisor:v0.53.0`
**Port**: 8083→8080
**Mode**: Privileged (required for host system access)
**Config Files**: None (stock image)

| Setting | Value |
|---------|-------|
| Host port | 8083 |
| Container port | 8080 |
| Privileged mode | yes |
| Restart policy | unless-stopped |

### Volume Mounts

| Host Path | Container Path | Mode | Purpose |
|-----------|---------------|------|---------|
| `/` | `/rootfs` | ro | Host filesystem metrics |
| `/var/run` | `/var/run` | rw | Docker socket access |
| `/sys` | `/sys` | ro | Kernel metrics |
| `/var/lib/docker` | `/var/lib/docker` | ro | Container metadata |
| `/dev/disk` | `/dev/disk` | ro | Disk I/O stats |
| `/dev/kmsg` | `/dev/kmsg` | - | Kernel messages |

## Usage

### Start cAdvisor

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d cadvisor
```

### Health Check

```bash
curl http://localhost:8083/healthz
```

### Web UI

Open [http://localhost:8083/containers/](http://localhost:8083/containers/) to browse container resource usage in the built-in web interface.

### View Raw Metrics

```bash
curl -s http://localhost:8083/metrics | head -50
```

### Query Specific Container Metrics

```bash
# CPU usage for a specific container
curl -s http://localhost:8083/metrics | grep 'container_cpu_usage_seconds_total{.*name="rideshare-simulation"'
```

## Troubleshooting

### cAdvisor not starting

cAdvisor requires privileged mode. Verify the container is running:

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring ps cadvisor
docker compose -f infrastructure/docker/compose.yml --profile monitoring logs cadvisor
```

### Metrics not appearing in Prometheus

Verify Prometheus can reach cAdvisor on the internal network:

```bash
docker exec rideshare-prometheus wget -q -O- http://cadvisor:8080/healthz
```

Check the Prometheus targets page at [http://localhost:9090/targets](http://localhost:9090/targets) to verify cAdvisor is listed and healthy.

### Port conflict on 8083

Port 8083 is the host mapping for cAdvisor (container port 8080). If port 8083 is in use, modify the port mapping in `infrastructure/docker/compose.yml`.

## References

- [cAdvisor GitHub Repository](https://github.com/google/cadvisor)
- [cAdvisor Runtime Options](https://github.com/google/cadvisor/blob/master/docs/runtime_options.md)
- [Prometheus Container Metrics](https://prometheus.io/docs/guides/cadvisor/)
