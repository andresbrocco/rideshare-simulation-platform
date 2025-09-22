from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SimulationSettings(BaseSettings):
    speed_multiplier: int = Field(default=1, ge=1, le=1024)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["text", "json"] = "text"
    checkpoint_interval: int = Field(default=300, ge=60)
    checkpoint_enabled: bool = Field(default=True)
    resume_from_checkpoint: bool = Field(default=False)

    # GPS-based arrival detection
    arrival_proximity_threshold_m: float = Field(
        default=50.0,
        ge=10.0,
        le=500.0,
        description="Distance in meters at which driver is considered arrived at pickup/dropoff",
    )
    arrival_timeout_multiplier: float = Field(
        default=2.0,
        ge=1.0,
        le=5.0,
        description="Multiplier for OSRM duration as fallback timeout for arrival",
    )

    # OSRM retry configuration
    osrm_max_retries: int = Field(default=3, ge=0, le=10)
    osrm_retry_base_delay: float = Field(default=0.5, ge=0.1, le=5.0)
    osrm_retry_multiplier: float = Field(default=2.0, ge=1.0, le=5.0)

    model_config = SettingsConfigDict(env_prefix="SIM_")


class KafkaSettings(BaseSettings):
    bootstrap_servers: str = "localhost:9092"
    security_protocol: str = "PLAINTEXT"
    sasl_mechanisms: str = "PLAIN"
    sasl_username: str = ""
    sasl_password: str = ""
    schema_registry_url: str = ""
    schema_registry_basic_auth_user_info: str = ""
    schema_validation_enabled: bool = True
    schema_base_path: str = "schemas"

    model_config = SettingsConfigDict(env_prefix="KAFKA_")


class RedisSettings(BaseSettings):
    host: str = "localhost"
    port: int = 6379
    password: str | None = None
    ssl: bool = False

    model_config = SettingsConfigDict(env_prefix="REDIS_")


class OSRMSettings(BaseSettings):
    base_url: str = "http://localhost:5000"

    model_config = SettingsConfigDict(env_prefix="OSRM_")

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("OSRM base URL must start with http:// or https://")
        return v.rstrip("/")


class DatabricksSettings(BaseSettings):
    host: str = ""
    token: str = ""
    catalog: str = "rideshare"

    model_config = SettingsConfigDict(env_prefix="DATABRICKS_")

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        if v and not v.startswith("https://"):
            raise ValueError("Databricks host must start with https://")
        return v.rstrip("/") if v else v


class AWSSettings(BaseSettings):
    region: str = "us-east-1"
    access_key_id: str | None = None
    secret_access_key: str | None = None

    model_config = SettingsConfigDict(env_prefix="AWS_")


class APISettings(BaseSettings):
    key: str = ""

    model_config = SettingsConfigDict(env_prefix="API_")


class CORSSettings(BaseSettings):
    origins: str = "http://localhost:5173,http://localhost:3000"

    model_config = SettingsConfigDict(env_prefix="CORS_")


class PerformanceSettings(BaseSettings):
    enabled: bool = True
    sample_interval_seconds: float = 1.0
    history_window_seconds: int = 60

    model_config = SettingsConfigDict(env_prefix="PERF_")


class MatchingSettings(BaseSettings):
    """Driver ranking and matching configuration."""

    ranking_eta_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    ranking_rating_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    ranking_acceptance_weight: float = Field(default=0.2, ge=0.0, le=1.0)

    model_config = SettingsConfigDict(env_prefix="MATCHING_")

    def __init__(self, **data):
        super().__init__(**data)
        weights_sum = (
            self.ranking_eta_weight + self.ranking_rating_weight + self.ranking_acceptance_weight
        )
        if not (0.99 <= weights_sum <= 1.01):
            raise ValueError(
                f"Ranking weights must sum to 1.0, got {weights_sum}. "
                f"(ETA: {self.ranking_eta_weight}, Rating: {self.ranking_rating_weight}, "
                f"Acceptance: {self.ranking_acceptance_weight})"
            )


class SpawnSettings(BaseSettings):
    """Agent spawn rate configuration for continuous spawning."""

    driver_spawn_rate: float = Field(
        default=2.0,
        ge=0.1,
        le=100.0,
        description="Drivers spawned per simulated second",
    )
    rider_spawn_rate: float = Field(
        default=40.0,
        ge=1.0,
        le=1000.0,
        description="Riders spawned per simulated second",
    )

    model_config = SettingsConfigDict(env_prefix="SPAWN_")


class Settings(BaseSettings):
    simulation: SimulationSettings = Field(default_factory=SimulationSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)  # type: ignore[arg-type]
    redis: RedisSettings = Field(default_factory=RedisSettings)  # type: ignore[arg-type]
    osrm: OSRMSettings = Field(default_factory=OSRMSettings)
    databricks: DatabricksSettings = Field(default_factory=DatabricksSettings)  # type: ignore[arg-type]
    aws: AWSSettings = Field(default_factory=AWSSettings)
    api: APISettings = Field(default_factory=APISettings)  # type: ignore[arg-type]
    cors: CORSSettings = Field(default_factory=CORSSettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)
    matching: MatchingSettings = Field(default_factory=MatchingSettings)
    spawn: SpawnSettings = Field(default_factory=SpawnSettings)

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        case_sensitive=False,
    )


def get_settings() -> Settings:
    """Load and validate settings from environment variables."""
    return Settings()
