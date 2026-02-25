"""Configuration settings for performance controller."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PrometheusSettings(BaseSettings):
    """Prometheus connection configuration."""

    url: str = "http://prometheus:9090"

    model_config = SettingsConfigDict(env_prefix="PROMETHEUS_")


class SimulationAPISettings(BaseSettings):
    """Simulation REST API configuration."""

    base_url: str = "http://simulation:8000"
    api_key: str = ""

    model_config = SettingsConfigDict(env_prefix="SIMULATION_")


class ControllerSettings(BaseSettings):
    """Controller tuning parameters."""

    poll_interval_seconds: float = Field(
        default=5.0,
        ge=1.0,
        description="Seconds between control loop iterations",
    )
    target_speed: int = Field(
        default=10,
        ge=1,
        description="Desired simulation speed multiplier",
    )
    critical_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Below this index, reduce to 25% of current speed",
    )
    warning_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Below this index, reduce to 50% of current speed",
    )
    healthy_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Above this index for N cycles, increase speed",
    )
    healthy_cycles_required: int = Field(
        default=3,
        ge=1,
        description="Consecutive healthy cycles before speed increase",
    )
    model_config = SettingsConfigDict(env_prefix="CONTROLLER_")


class APISettings(BaseSettings):
    """HTTP API configuration."""

    host: str = "0.0.0.0"
    port: int = 8090

    model_config = SettingsConfigDict(env_prefix="API_")


class Settings(BaseSettings):
    """Root settings container."""

    prometheus: PrometheusSettings = Field(default_factory=PrometheusSettings)
    simulation: SimulationAPISettings = Field(default_factory=SimulationAPISettings)
    controller: ControllerSettings = Field(default_factory=ControllerSettings)
    api: APISettings = Field(default_factory=APISettings)

    log_level: str = Field(default="INFO", description="Logging level")

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        extra="ignore",
    )


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
