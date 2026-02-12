"""Configuration settings for stream processor."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class KafkaSettings(BaseSettings):
    """Kafka consumer configuration."""

    bootstrap_servers: str = "localhost:9092"
    security_protocol: str = "PLAINTEXT"
    sasl_mechanism: str = "PLAIN"
    sasl_username: str = ""
    sasl_password: str = ""
    group_id: str = "stream-processor"
    auto_offset_reset: str = "latest"
    enable_auto_commit: bool = False
    auto_commit_interval_ms: int = 5000
    session_timeout_ms: int = 30000
    max_poll_interval_ms: int = 300000
    batch_commit_size: int = 100
    # Consumer fetch optimization - batch reads from Kafka
    fetch_min_bytes: int = 10240  # 10KB minimum before returning
    fetch_max_wait_ms: int = 100  # Max wait for fetch_min_bytes
    max_partition_fetch_bytes: int = 1048576  # 1MB max per partition

    model_config = SettingsConfigDict(env_prefix="KAFKA_")


class RedisSettings(BaseSettings):
    """Redis connection configuration."""

    host: str = "localhost"
    port: int = 6379
    password: str | None = None
    db: int = 0

    model_config = SettingsConfigDict(env_prefix="REDIS_")


class APISettings(BaseSettings):
    """HTTP API configuration."""

    host: str = "0.0.0.0"
    port: int = 8080

    model_config = SettingsConfigDict(env_prefix="API_")


class ProcessorSettings(BaseSettings):
    """Stream processor configuration."""

    # Window settings for GPS aggregation
    window_size_ms: int = Field(
        default=100,
        ge=50,
        le=5000,
        description="Window duration in milliseconds for GPS aggregation",
    )

    # Aggregation strategy: "latest" keeps only most recent, "sample" keeps 1-in-N
    aggregation_strategy: str = Field(
        default="latest",
        pattern="^(latest|sample)$",
        description="GPS aggregation strategy",
    )

    # For "sample" strategy: emit 1-in-N messages
    sample_rate: int = Field(
        default=10,
        ge=1,
        description="For sample strategy, emit every Nth message",
    )

    # Topics to consume (comma-separated)
    topics: str = Field(
        default="gps_pings,trips,driver_status,surge_updates",
        description="Kafka topics to consume",
    )

    # Per-topic enable/disable flags
    gps_enabled: bool = True
    trips_enabled: bool = True
    driver_status_enabled: bool = True
    surge_enabled: bool = True

    # Retry settings
    max_retries: int = 3
    retry_backoff_base_ms: int = 100

    model_config = SettingsConfigDict(env_prefix="PROCESSOR_")

    def get_topics_list(self) -> list[str]:
        """Parse topics string into list."""
        return [t.strip() for t in self.topics.split(",") if t.strip()]


class Settings(BaseSettings):
    """Root settings container."""

    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    processor: ProcessorSettings = Field(default_factory=ProcessorSettings)
    api: APISettings = Field(default_factory=APISettings)

    log_level: str = Field(default="INFO", description="Logging level")

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        extra="ignore",
    )


def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
