"""Configuration dataclasses for performance testing framework."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class APIConfig:
    """Configuration for the Simulation API client."""

    base_url: str = "http://localhost:8000"
    api_key: str = "admin"
    timeout: float = 30.0


@dataclass
class DockerConfig:
    """Configuration for Docker and cAdvisor."""

    cadvisor_url: str = "http://localhost:8083"
    compose_file: str = "infrastructure/docker/compose.yml"
    profiles: list[str] = field(default_factory=lambda: ["core", "data-pipeline", "monitoring"])
    available_cpu_cores: int | None = None  # Auto-detected from Docker if None


@dataclass
class SamplingConfig:
    """Configuration for metric sampling."""

    interval_seconds: float = 2.0
    drain_interval_seconds: float = 4.0
    cooldown_interval_seconds: float = 8.0
    warmup_seconds: float = 10.0
    settle_seconds: float = 5.0
    min_samples: int = 10


@dataclass
class ScenarioConfig:
    """Configuration for test scenarios."""

    # Duration/leak test settings (3-phase: active → drain → cooldown)
    duration_active_minutes: int = 5
    duration_cooldown_minutes: int = 10
    duration_drain_timeout_seconds: int = 600

    # Baseline test settings
    baseline_duration_seconds: int = 30

    # Stress test settings
    stress_cpu_threshold_percent: float = 90.0  # Per-container (used by analysis findings)
    stress_global_cpu_threshold_percent: float = 90.0  # % of total available cores
    stress_memory_threshold_percent: float = 90.0
    stress_rolling_window_seconds: int = 10
    stress_spawn_batch_size: int = 18
    stress_spawn_interval_seconds: float = 1.0
    stress_max_duration_minutes: int = 30

    # Speed scaling test settings
    speed_scaling_step_duration_minutes: int = 8
    speed_scaling_max_multiplier: int = 1024


@dataclass
class ThresholdConfig:
    """Configurable thresholds for performance analysis."""

    # Memory thresholds
    memory_leak_mb_per_min: float = 1.0
    memory_warning_percent: float = 70.0
    memory_critical_percent: float = 85.0

    # CPU thresholds
    cpu_leak_percent_per_min: float = 5.0
    cpu_warning_percent: float = 70.0
    cpu_critical_percent: float = 85.0

    # Per-container overrides (container_name -> {threshold_name: value})
    container_overrides: dict[str, dict[str, float]] = field(default_factory=dict)

    def get_memory_leak_threshold(self, container: str) -> float:
        """Get memory leak threshold for container."""
        overrides = self.container_overrides.get(container, {})
        return overrides.get("memory_leak_mb_per_min", self.memory_leak_mb_per_min)

    def get_memory_warning_percent(self, container: str) -> float:
        """Get memory warning threshold for container."""
        overrides = self.container_overrides.get(container, {})
        return overrides.get("memory_warning_percent", self.memory_warning_percent)

    def get_memory_critical_percent(self, container: str) -> float:
        """Get memory critical threshold for container."""
        overrides = self.container_overrides.get(container, {})
        return overrides.get("memory_critical_percent", self.memory_critical_percent)

    def get_cpu_warning_percent(self, container: str) -> float:
        """Get CPU warning threshold for container."""
        overrides = self.container_overrides.get(container, {})
        return overrides.get("cpu_warning_percent", self.cpu_warning_percent)

    def get_cpu_critical_percent(self, container: str) -> float:
        """Get CPU critical threshold for container."""
        overrides = self.container_overrides.get(container, {})
        return overrides.get("cpu_critical_percent", self.cpu_critical_percent)

    def get_stress_cpu_threshold(self, container: str, base_threshold: float) -> float:
        """Effective stress CPU threshold = base_threshold * effective_cores."""
        cores = get_cpu_cores_for_container(container)
        return base_threshold * cores


@dataclass
class AnalysisConfig:
    """Configuration for analysis and visualization."""

    # None = analyze all containers; otherwise filter to these
    focus_containers: list[str] | None = None
    # Configurable thresholds
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    # Maximum containers per chart (for readability)
    max_containers_per_chart: int = 10
    # Priority containers shown first in summaries/charts
    priority_containers: list[str] = field(
        default_factory=lambda: [
            "rideshare-simulation",
            "rideshare-kafka",
            "rideshare-redis",
            "rideshare-osrm",
            "rideshare-stream-processor",
        ]
    )

    @property
    def leak_threshold_mb_per_min(self) -> float:
        """Backward compatibility: delegate to thresholds."""
        return self.thresholds.memory_leak_mb_per_min

    @property
    def cpu_leak_threshold_per_min(self) -> float:
        """Backward compatibility: delegate to thresholds."""
        return self.thresholds.cpu_leak_percent_per_min


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
    "rideshare-control-panel": {"display_name": "Control Panel", "profile": "core"},
    # Data Pipeline profile
    "rideshare-minio": {"display_name": "MinIO", "profile": "data-pipeline"},
    "rideshare-bronze-ingestion": {"display_name": "Bronze Ingestion", "profile": "data-pipeline"},
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

# Effective CPU parallelism per container (accounts for Docker limits AND threading model)
CONTAINER_CPU_CORES: dict[str, float] = {
    "rideshare-simulation": 1.0,  # Python GIL — single-threaded despite 2.0 Docker cores
    "rideshare-kafka": 1.5,  # Docker limit, JVM multi-threaded
    "rideshare-schema-registry": 0.5,  # Docker limit
    "rideshare-stream-processor": 1.0,  # Docker limit, Python
    "rideshare-bronze-ingestion": 0.5,  # Docker limit
    "rideshare-airflow-webserver": 1.0,  # Docker limit
    "rideshare-airflow-scheduler": 1.5,  # Docker limit
    "rideshare-trino": 2.0,  # Docker limit, JVM multi-threaded
    "rideshare-spark-thrift-server": 2.0,  # Docker limit, JVM multi-threaded
}
# Unlisted containers default to 1.0 core


def get_cpu_cores_for_container(container: str) -> float:
    """Get effective CPU core count for a container."""
    return CONTAINER_CPU_CORES.get(container, 1.0)


def get_containers_for_profiles(profiles: list[str]) -> list[str]:
    """Get all container names for the given profiles.

    Args:
        profiles: List of profile names (e.g., ["core", "data-pipeline"]).

    Returns:
        List of container names belonging to those profiles.
    """
    return [name for name, config in CONTAINER_CONFIG.items() if config["profile"] in profiles]


@dataclass
class TestConfig:
    """Main configuration combining all settings."""

    api: APIConfig = field(default_factory=APIConfig)
    docker: DockerConfig = field(default_factory=DockerConfig)
    sampling: SamplingConfig = field(default_factory=SamplingConfig)
    scenarios: ScenarioConfig = field(default_factory=ScenarioConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    output_dir: Path = field(default_factory=lambda: Path("tests/performance/results"))

    def get_compose_base_command(self) -> list[str]:
        """Get the base docker compose command with profiles."""
        cmd = ["docker", "compose", "-f", self.docker.compose_file]
        for profile in self.docker.profiles:
            cmd.extend(["--profile", profile])
        return cmd

    def get_all_containers(self) -> list[str]:
        """Get all container names for the configured profiles."""
        return get_containers_for_profiles(self.docker.profiles)
