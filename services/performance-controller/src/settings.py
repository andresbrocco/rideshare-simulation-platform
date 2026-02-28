"""Configuration settings for performance controller."""

from pydantic import Field, model_validator
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
    max_speed: float = Field(
        default=32.0,
        gt=0,
        description="Maximum simulation speed multiplier",
    )
    min_speed: float = Field(
        default=0.5,
        gt=0,
        description="Minimum simulation speed multiplier (1/2x)",
    )
    target: float = Field(
        default=0.66,
        ge=0.0,
        le=1.0,
        description="Infrastructure headroom setpoint — stable equilibrium target",
    )
    k_up: float = Field(
        default=0.15,
        gt=0.0,
        description="Gain for speed increases (small = gentle ramp-up)",
    )
    k_down: float = Field(
        default=1.5,
        gt=0.0,
        description="Gain for speed decreases (large = aggressive cut-down)",
    )
    smoothness: float = Field(
        default=12.0,
        gt=0.0,
        description="Sigmoid steepness blending k_up and k_down",
    )
    ki: float = Field(
        default=0.02,
        ge=0.0,
        description="Integral gain for steady-state error correction",
    )
    kd: float = Field(
        default=0.1,
        ge=0.0,
        description="Derivative gain for oscillation dampening",
    )
    integral_max: float = Field(
        default=5.0,
        gt=0.0,
        description="Anti-windup clamp for error integral (error-seconds)",
    )
    model_config = SettingsConfigDict(env_prefix="CONTROLLER_")

    @model_validator(mode="after")
    def validate_speed_bounds(self) -> "ControllerSettings":
        if self.min_speed > self.max_speed:
            raise ValueError(
                f"min_speed ({self.min_speed}) must be <= max_speed ({self.max_speed})"
            )
        if self.k_down <= self.k_up:
            raise ValueError(
                f"k_down ({self.k_down}) must be > k_up ({self.k_up}) "
                "to ensure asymmetric response (fast cut, gentle ramp)"
            )
        return self


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
