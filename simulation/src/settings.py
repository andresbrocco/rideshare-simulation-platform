from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SimulationSettings(BaseSettings):
    speed_multiplier: int = Field(default=1, ge=1, le=100)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    checkpoint_interval: int = Field(default=300, ge=60)

    model_config = SettingsConfigDict(env_prefix="SIM_")


class KafkaSettings(BaseSettings):
    bootstrap_servers: str
    security_protocol: str = "SASL_SSL"
    sasl_mechanisms: str = "PLAIN"
    sasl_username: str
    sasl_password: str
    schema_registry_url: str
    schema_registry_basic_auth_user_info: str

    model_config = SettingsConfigDict(env_prefix="KAFKA_")

    @field_validator("bootstrap_servers")
    @classmethod
    def validate_bootstrap_servers(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Bootstrap servers cannot be empty")
        return v


class RedisSettings(BaseSettings):
    host: str
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
    host: str
    token: str
    catalog: str = "rideshare"

    model_config = SettingsConfigDict(env_prefix="DATABRICKS_")

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("Databricks host must start with https://")
        return v.rstrip("/")


class AWSSettings(BaseSettings):
    region: str = "us-east-1"
    access_key_id: str | None = None
    secret_access_key: str | None = None

    model_config = SettingsConfigDict(env_prefix="AWS_")


class APISettings(BaseSettings):
    key: str

    model_config = SettingsConfigDict(env_prefix="API_")


class Settings(BaseSettings):
    simulation: SimulationSettings = Field(default_factory=SimulationSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)  # type: ignore[arg-type]
    redis: RedisSettings = Field(default_factory=RedisSettings)  # type: ignore[arg-type]
    osrm: OSRMSettings = Field(default_factory=OSRMSettings)
    databricks: DatabricksSettings = Field(default_factory=DatabricksSettings)  # type: ignore[arg-type]
    aws: AWSSettings = Field(default_factory=AWSSettings)
    api: APISettings = Field(default_factory=APISettings)  # type: ignore[arg-type]

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        case_sensitive=False,
    )


def get_settings() -> Settings:
    """Load and validate settings from environment variables."""
    return Settings()
