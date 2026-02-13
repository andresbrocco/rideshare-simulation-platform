# cAdvisor

> Container resource metrics exporter for Docker infrastructure monitoring

## Quick Reference

### Ports

| Port | Purpose |
|------|---------|
| 8083 | Host-mapped metrics endpoint (internal: 8080) |

### Health Check

```bash
# Check cAdvisor health
curl http://localhost:8083/healthz

# View metrics endpoint
curl http://localhost:8083/metrics
```

### Commands

```bash
# Start cAdvisor with monitoring profile
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d cadvisor

# View cAdvisor logs
docker compose -f infrastructure/docker/compose.yml logs -f cadvisor

# Check cAdvisor status
docker compose -f infrastructure/docker/compose.yml ps cadvisor

# Stop cAdvisor
docker compose -f infrastructure/docker/compose.yml --profile monitoring down
```

### Configuration

**Stock Image**: Runs unmodified `ghcr.io/google/cadvisor:v0.53.0` with no custom config files.

**Required Volume Mounts**:
- `/` → `/rootfs:ro` - Root filesystem (read-only)
- `/var/run/docker.sock` - Docker socket for container discovery
- `/sys` - Kernel metrics
- `/var/lib/docker` - Container metadata
- `/dev/disk` - Disk statistics
- `/dev/kmsg` - Kernel messages (via devices)

**Privileged Mode**: Required for host-level system metrics access.

### Prometheus Integration

cAdvisor is scraped by Prometheus at 15-second intervals:

```yaml
# services/prometheus/prometheus.yml
- job_name: 'cadvisor'
  scrape_interval: 15s
  static_configs:
    - targets: ['cadvisor:8080']
```

**Metric Prefix**: All cAdvisor metrics use `container_*` prefix (e.g., `container_cpu_usage_seconds_total`, `container_memory_usage_bytes`).

## Common Tasks

### Verify Container Metrics Collection

```bash
# Check if cAdvisor is exposing metrics
curl http://localhost:8083/metrics | grep container_cpu_usage_seconds_total

# View metrics for a specific container
curl http://localhost:8083/metrics | grep 'name="rideshare-simulation"'
```

### Verify Prometheus Scraping

```bash
# Check if Prometheus is scraping cAdvisor
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="cadvisor")'

# Query container metrics in Prometheus
curl 'http://localhost:9090/api/v1/query?query=container_memory_usage_bytes' | jq .
```

### View Container Resource Usage

```bash
# Get CPU usage for all containers
curl 'http://localhost:9090/api/v1/query?query=rate(container_cpu_usage_seconds_total[1m])' | jq .

# Get memory usage for all containers
curl 'http://localhost:9090/api/v1/query?query=container_memory_usage_bytes' | jq .
```

## Troubleshooting

### cAdvisor Not Starting

**Symptom**: Container exits immediately or fails health check.

**Check**:
```bash
# View startup logs
docker compose -f infrastructure/docker/compose.yml logs cadvisor

# Verify Docker socket access
ls -la /var/run/docker.sock

# Ensure no port conflict on 8083
lsof -i :8083
```

### Metrics Not Appearing

**Symptom**: `/metrics` endpoint returns empty or minimal data.

**Solution**:
- cAdvisor automatically discovers containers; no configuration needed
- Wait 15-30 seconds for first scrape interval
- Verify containers are running: `docker ps`
- Check privileged mode is enabled in compose.yml

### Port 8083 Conflict

**Note**: Port 8083 is used (instead of 8080) because Trino uses 8080 in the data-pipeline profile.

If port 8083 is unavailable:
1. Stop conflicting service: `lsof -ti :8083 | xargs kill`
2. Or change host port in compose.yml: `"<new_port>:8080"`
3. Update any hardcoded references to port 8083

### High Memory Usage

cAdvisor has a 256MB memory limit. If this is exceeded:

```bash
# Check current memory usage
docker stats rideshare-cadvisor

# View OOM events
docker compose -f infrastructure/docker/compose.yml logs cadvisor | grep -i "out of memory"
```

**Solution**: Increase `mem_limit` in compose.yml if monitoring many containers.

## Related

- [CONTEXT.md](CONTEXT.md) - Architecture and design decisions
- [../../prometheus/README.md](../prometheus/README.md) - Prometheus scrape configuration
- [../../grafana/README.md](../grafana/README.md) - Dashboard visualization
- [../../infrastructure/docker/compose.yml](../../infrastructure/docker/compose.yml) - Docker Compose service definition
