from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SimulationSettings(BaseSettings):
    speed_multiplier: float = Field(default=1.0, ge=0.5, le=32.0)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["text", "json"] = "text"
    checkpoint_interval: int = Field(default=300, ge=60)
    checkpoint_enabled: bool = Field(default=True)
    resume_from_checkpoint: bool = Field(default=True)

    # Checkpoint storage backend configuration
    checkpoint_storage_type: Literal["sqlite", "s3"] = Field(
        default="sqlite",
        description="Checkpoint storage backend: sqlite for local, s3 for cloud",
    )
    checkpoint_s3_bucket: str = Field(
        default="rideshare-checkpoints",
        description="S3 bucket name for checkpoint storage (used when storage_type=s3)",
    )
    checkpoint_s3_prefix: str = Field(
        default="simulation",
        description="S3 key prefix for checkpoints (used when storage_type=s3)",
    )

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

    # Mid-trip cancellation
    mid_trip_cancellation_rate: float = Field(
        default=0.002,
        ge=0.0,
        le=1.0,
        description="Probability that a rider cancels during IN_TRANSIT. 0.002 = ~0.2% of trips.",
    )
    driver_mid_trip_cancellation_rate: float = Field(
        default=0.001,
        ge=0.0,
        le=1.0,
        description="Probability that a driver cancels during IN_TRANSIT. 0.001 = ~0.1% of trips.",
    )

    # Real-Time Ratio sliding window
    rtr_window_seconds: float = Field(
        default=10.0,
        ge=1.0,
        le=300.0,
        description="Sliding window length (wall-clock seconds) for RTR calculation.",
    )

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

    @model_validator(mode="after")
    def validate_credentials_provided(self) -> "KafkaSettings":
        missing = []
        if not self.sasl_username:
            missing.append("KAFKA_SASL_USERNAME")
        if not self.sasl_password:
            missing.append("KAFKA_SASL_PASSWORD")
        if not self.schema_registry_basic_auth_user_info:
            missing.append("KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO")
        if missing:
            raise ValueError(f"Required credentials not provided: {', '.join(missing)}")
        return self


class RedisSettings(BaseSettings):
    host: str = "localhost"
    port: int = 6379
    password: str = ""
    ssl: bool = False

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    @model_validator(mode="after")
    def validate_credentials_provided(self) -> "RedisSettings":
        if not self.password:
            raise ValueError("Required credential not provided: REDIS_PASSWORD")
        return self


class OSRMSettings(BaseSettings):
    base_url: str = "http://localhost:5000"

    model_config = SettingsConfigDict(env_prefix="OSRM_")

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("OSRM base URL must start with http:// or https://")
        return v.rstrip("/")


class APISettings(BaseSettings):
    key: str = ""

    model_config = SettingsConfigDict(env_prefix="API_")

    @model_validator(mode="after")
    def validate_credentials_provided(self) -> "APISettings":
        if not self.key:
            raise ValueError("Required credential not provided: API_KEY")
        return self


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
    max_trip_history: int = Field(
        default=10000,
        ge=100,
        description="Maximum number of completed/cancelled trips to retain in memory for metrics",
    )
    retry_interval_seconds: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Sim-seconds between retry attempts for unmatched trips",
    )
    offer_timeout_seconds: int = Field(
        default=10,
        ge=5,
        le=60,
        description="Sim-seconds before a pending offer expires",
    )

    model_config = SettingsConfigDict(env_prefix="MATCHING_")

    def __init__(self, **data: Any) -> None:
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

    driver_immediate_spawn_rate: float = Field(
        default=10.0,
        ge=0.1,
        le=100.0,
        description="Immediate-mode drivers spawned per simulated second",
    )
    driver_scheduled_spawn_rate: float = Field(
        default=50.0,
        ge=0.1,
        le=100.0,
        description="Scheduled-mode drivers spawned per simulated second",
    )
    rider_immediate_spawn_rate: float = Field(
        default=10.0,
        ge=0.1,
        le=100.0,
        description="Immediate-mode riders spawned per simulated second",
    )
    rider_scheduled_spawn_rate: float = Field(
        default=50.0,
        ge=0.1,
        le=100.0,
        description="Scheduled-mode riders spawned per simulated second",
    )

    model_config = SettingsConfigDict(env_prefix="SPAWN_")


class Settings(BaseSettings):
    simulation: SimulationSettings = Field(default_factory=SimulationSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    osrm: OSRMSettings = Field(default_factory=OSRMSettings)
    api: APISettings = Field(default_factory=APISettings)
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
