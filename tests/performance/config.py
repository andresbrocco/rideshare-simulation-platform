"""Configuration dataclasses for performance testing framework."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class APIConfig:
    """Configuration for the Simulation API client."""

    base_url: str = "http://localhost:8000"
    api_key: str = "dev-api-key-change-in-production"
    timeout: float = 30.0


@dataclass
class DockerConfig:
    """Configuration for Docker and cAdvisor."""

    cadvisor_url: str = "http://localhost:8083"
    compose_file: str = "infrastructure/docker/compose.yml"
    profiles: list[str] = field(
        default_factory=lambda: ["core", "data-pipeline", "monitoring", "analytics"]
    )


@dataclass
class SamplingConfig:
    """Configuration for metric sampling."""

    interval_seconds: float = 2.0
    warmup_seconds: float = 10.0
    settle_seconds: float = 5.0
    min_samples: int = 10


@dataclass
class ScenarioConfig:
    """Configuration for test scenarios."""

    # Load scaling test levels (drivers = riders at each level)
    load_levels: list[int] = field(default_factory=lambda: [10, 20, 40, 80])
    load_duration_seconds: int = 60

    # Duration/leak test settings
    duration_minutes: list[int] = field(default_factory=lambda: [1, 2, 4, 8])
    duration_agent_count: int = 40

    # Baseline test settings
    baseline_duration_seconds: int = 30

    # Reset test settings
    reset_load_duration_seconds: int = 30
    reset_post_duration_seconds: int = 30
    reset_tolerance_percent: float = 10.0


# Container configuration - mirrors CONTAINER_CONFIG from metrics.py
# Memory limits are fetched dynamically from cAdvisor
CONTAINER_CONFIG: dict[str, dict[str, str]] = {
    # Core profile
    "rideshare-kafka": {"display_name": "Kafka", "profile": "core"},
    "rideshare-schema-registry": {"display_name": "Schema Registry", "profile": "core"},
    "rideshare-redis": {"display_name": "Redis", "profile": "core"},
    "rideshare-osrm": {"display_name": "OSRM", "profile": "core"},
    "rideshare-simulation": {"display_name": "Simulation", "profile": "core"},
    "rideshare-stream-processor": {"display_name": "Stream Processor", "profile": "core"},
    "rideshare-frontend": {"display_name": "Frontend", "profile": "core"},
    # Data Pipeline profile
    "rideshare-minio": {"display_name": "MinIO", "profile": "data-pipeline"},
    "rideshare-spark-thrift-server": {"display_name": "Spark Thrift", "profile": "data-pipeline"},
    "rideshare-bronze-ingestion-high-volume": {
        "display_name": "Spark: High Volume",
        "profile": "data-pipeline",
    },
    "rideshare-bronze-ingestion-low-volume": {
        "display_name": "Spark: Low Volume",
        "profile": "data-pipeline",
    },
    "rideshare-localstack": {"display_name": "LocalStack", "profile": "data-pipeline"},
    # Monitoring profile
    "rideshare-prometheus": {"display_name": "Prometheus", "profile": "monitoring"},
    "rideshare-cadvisor": {"display_name": "cAdvisor", "profile": "monitoring"},
    "rideshare-grafana": {"display_name": "Grafana", "profile": "monitoring"},
    # Quality Orchestration profile (part of data-pipeline)
    "rideshare-postgres-airflow": {
        "display_name": "Postgres (Airflow)",
        "profile": "data-pipeline",
    },
    "rideshare-airflow-webserver": {"display_name": "Airflow Web", "profile": "data-pipeline"},
    "rideshare-airflow-scheduler": {
        "display_name": "Airflow Scheduler",
        "profile": "data-pipeline",
    },
    # BI/Analytics profile
    "rideshare-postgres-superset": {"display_name": "Postgres (Superset)", "profile": "analytics"},
    "rideshare-redis-superset": {"display_name": "Redis (Superset)", "profile": "analytics"},
    "rideshare-superset": {"display_name": "Superset", "profile": "analytics"},
}


@dataclass
class TestConfig:
    """Main configuration combining all settings."""

    api: APIConfig = field(default_factory=APIConfig)
    docker: DockerConfig = field(default_factory=DockerConfig)
    sampling: SamplingConfig = field(default_factory=SamplingConfig)
    scenarios: ScenarioConfig = field(default_factory=ScenarioConfig)
    output_dir: Path = field(default_factory=lambda: Path("tests/performance/results"))

    def get_compose_base_command(self) -> list[str]:
        """Get the base docker compose command with profiles."""
        cmd = ["docker", "compose", "-f", self.docker.compose_file]
        for profile in self.docker.profiles:
            cmd.extend(["--profile", profile])
        return cmd
