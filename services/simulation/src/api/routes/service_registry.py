"""Centralized service registry — single source of truth for all services.

Every service that can appear as an infrastructure card in any environment
is declared exactly once here, together with its display name, latency
thresholds, and deployment scope.  The compose.yml parsing and static
fallback dicts in ``metrics.py`` are replaced by this module.
"""

from dataclasses import dataclass
from enum import Enum


class Environment(Enum):
    LOCAL = "local"
    PRODUCTION = "production"
    BOTH = "both"


@dataclass(frozen=True, slots=True)
class ServiceDefinition:
    """Metadata for a single infrastructure service."""

    display_name: str
    environment: Environment
    threshold_degraded_ms: float
    threshold_unhealthy_ms: float
    heartbeat_thresholds: tuple[float, float] | None = None
    optional: bool = False


# Default latency thresholds applied when a service doesn't specify its own.
DEFAULT_THRESHOLDS: tuple[float, float] = (100, 500)

SERVICE_REGISTRY: dict[str, ServiceDefinition] = {
    # ── Core real-time path ──────────────────────────────────────────────
    "rideshare-kafka": ServiceDefinition("Kafka", Environment.BOTH, 50, 200),
    "rideshare-schema-registry": ServiceDefinition("Schema Registry", Environment.BOTH, 100, 500),
    "rideshare-redis": ServiceDefinition("Redis", Environment.BOTH, 5, 20),
    "rideshare-osrm": ServiceDefinition("OSRM", Environment.BOTH, 150, 500),
    "rideshare-simulation": ServiceDefinition("Simulation", Environment.BOTH, 100, 500),
    "rideshare-stream-processor": ServiceDefinition("Stream Processor", Environment.BOTH, 50, 150),
    "rideshare-control-panel": ServiceDefinition("Control Panel", Environment.BOTH, 100, 500),
    # ── Data pipeline ────────────────────────────────────────────────────
    "rideshare-bronze-ingestion": ServiceDefinition(
        "Bronze Ingestion",
        Environment.BOTH,
        100,
        500,
    ),
    "rideshare-trino": ServiceDefinition("Trino", Environment.BOTH, 500, 2000),
    "rideshare-hive-metastore": ServiceDefinition("Hive Metastore", Environment.BOTH, 200, 1000),
    "rideshare-postgres-airflow": ServiceDefinition(
        "Postgres (Airflow)",
        Environment.BOTH,
        10,
        50,
    ),
    "rideshare-postgres-metastore": ServiceDefinition(
        "Postgres (Metastore)",
        Environment.BOTH,
        10,
        50,
    ),
    "rideshare-airflow-webserver": ServiceDefinition(
        "Airflow Web",
        Environment.BOTH,
        500,
        2000,
    ),
    "rideshare-airflow-scheduler": ServiceDefinition(
        "Airflow Scheduler",
        Environment.BOTH,
        100,
        500,
        heartbeat_thresholds=(30, 90),
    ),
    # ── Monitoring ───────────────────────────────────────────────────────
    "rideshare-prometheus": ServiceDefinition("Prometheus", Environment.BOTH, 100, 500),
    "rideshare-grafana": ServiceDefinition("Grafana", Environment.BOTH, 200, 1000),
    "rideshare-otel-collector": ServiceDefinition("OTel Collector", Environment.BOTH, 100, 500),
    "rideshare-loki": ServiceDefinition("Loki", Environment.BOTH, 100, 500),
    "rideshare-tempo": ServiceDefinition("Tempo", Environment.BOTH, 100, 500),
    # ── Local-only services ──────────────────────────────────────────────
    "rideshare-minio": ServiceDefinition("MinIO", Environment.LOCAL, 200, 1000),
    "rideshare-localstack": ServiceDefinition("LocalStack", Environment.LOCAL, 200, 1000),
    "rideshare-cadvisor": ServiceDefinition("cAdvisor", Environment.LOCAL, 100, 500),
    "rideshare-kafka-exporter": ServiceDefinition("Kafka Exporter", Environment.LOCAL, 100, 500),
    "rideshare-redis-exporter": ServiceDefinition("Redis Exporter", Environment.LOCAL, 100, 500),
    "rideshare-performance-controller": ServiceDefinition(
        "Performance Controller",
        Environment.LOCAL,
        100,
        500,
    ),
    # ── Production-only services ─────────────────────────────────────────
    "rideshare-otel-collector-logs": ServiceDefinition(
        "OTel Logs Collector",
        Environment.PRODUCTION,
        100,
        500,
    ),
}


def get_services_for_environment(env: str) -> dict[str, ServiceDefinition]:
    """Return registry entries that apply to the given deployment environment."""
    return {
        key: svc
        for key, svc in SERVICE_REGISTRY.items()
        if svc.environment == Environment.BOTH or svc.environment.value == env
    }
