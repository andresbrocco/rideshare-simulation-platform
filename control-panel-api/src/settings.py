from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class APISettings(BaseSettings):
    key: str

    model_config = SettingsConfigDict(env_prefix="API_")


class KafkaSettings(BaseSettings):
    bootstrap_servers: str = "localhost:9092"
    security_protocol: str = "PLAINTEXT"
    sasl_mechanisms: str = "PLAIN"
    sasl_username: str | None = None
    sasl_password: str | None = None

    model_config = SettingsConfigDict(env_prefix="KAFKA_")


class RedisSettings(BaseSettings):
    host: str = "localhost"
    port: int = 6379
    password: str | None = None

    model_config = SettingsConfigDict(env_prefix="REDIS_")


class CORSSettings(BaseSettings):
    origins: str = Field(default="http://localhost:5173,http://localhost:3000")

    model_config = SettingsConfigDict(env_prefix="CORS_")


class Settings(BaseSettings):
    api: APISettings = Field(default_factory=APISettings)  # type: ignore[arg-type]
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        case_sensitive=False,
    )


def get_settings() -> Settings:
    return Settings()
