import pytest
from pydantic import ValidationError

from settings import (
    APISettings,
    KafkaSettings,
    OSRMSettings,
    RedisSettings,
    Settings,
    SimulationSettings,
    get_settings,
)


@pytest.mark.unit
class TestSimulationSettings:
    def test_defaults(self):
        settings = SimulationSettings()
        assert settings.speed_multiplier == 1.0
        assert settings.log_level == "INFO"
        assert settings.checkpoint_interval == 300

    def test_env_prefix(self, monkeypatch):
        monkeypatch.setenv("SIM_SPEED_MULTIPLIER", "10")
        monkeypatch.setenv("SIM_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("SIM_CHECKPOINT_INTERVAL", "600")

        settings = SimulationSettings()
        assert settings.speed_multiplier == 10.0
        assert settings.log_level == "DEBUG"
        assert settings.checkpoint_interval == 600

    def test_validation(self):
        with pytest.raises(ValidationError):
            SimulationSettings(speed_multiplier=0.06)  # Below minimum 0.0625

        with pytest.raises(ValidationError):
            SimulationSettings(speed_multiplier=1025.0)  # Max is 1024

        with pytest.raises(ValidationError):
            SimulationSettings(checkpoint_interval=30)

    def test_speed_multiplier_accepts_float(self):
        settings = SimulationSettings(speed_multiplier=0.0625)
        assert settings.speed_multiplier == 0.0625

        settings = SimulationSettings(speed_multiplier=2.5)
        assert settings.speed_multiplier == 2.5

    def test_mid_trip_cancellation_rate_default(self):
        settings = SimulationSettings()
        assert settings.mid_trip_cancellation_rate == 0.002

    def test_mid_trip_cancellation_rate_validation(self):
        with pytest.raises(ValidationError):
            SimulationSettings(mid_trip_cancellation_rate=-0.1)

        with pytest.raises(ValidationError):
            SimulationSettings(mid_trip_cancellation_rate=1.5)

    def test_mid_trip_cancellation_rate_env_override(self, monkeypatch):
        monkeypatch.setenv("SIM_MID_TRIP_CANCELLATION_RATE", "0.05")
        settings = SimulationSettings()
        assert settings.mid_trip_cancellation_rate == 0.05

    def test_rtr_window_seconds_default(self):
        settings = SimulationSettings()
        assert settings.rtr_window_seconds == 10.0

    def test_rtr_window_seconds_env_override(self, monkeypatch):
        monkeypatch.setenv("SIM_RTR_WINDOW_SECONDS", "30.0")
        settings = SimulationSettings()
        assert settings.rtr_window_seconds == 30.0

    def test_rtr_window_seconds_validation(self):
        with pytest.raises(ValidationError):
            SimulationSettings(rtr_window_seconds=0.5)  # below ge=1.0
        with pytest.raises(ValidationError):
            SimulationSettings(rtr_window_seconds=400.0)  # above le=300.0


@pytest.mark.unit
class TestKafkaSettings:
    def test_defaults(self):
        settings = KafkaSettings()
        assert settings.bootstrap_servers == "localhost:9092"
        assert settings.security_protocol == "PLAINTEXT"

    def test_credentials_required(self, monkeypatch):
        monkeypatch.delenv("KAFKA_SASL_USERNAME", raising=False)
        monkeypatch.delenv("KAFKA_SASL_PASSWORD", raising=False)
        monkeypatch.delenv("KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO", raising=False)
        with pytest.raises(ValidationError):
            KafkaSettings()

    def test_valid_config(self):
        settings = KafkaSettings(
            bootstrap_servers="kafka.example.com:9092",
            sasl_username="key",
            sasl_password="secret",
            schema_registry_url="http://localhost:8081",
            schema_registry_basic_auth_user_info="key:secret",
        )
        assert settings.bootstrap_servers == "kafka.example.com:9092"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "custom:9092")
        settings = KafkaSettings()
        assert settings.bootstrap_servers == "custom:9092"


@pytest.mark.unit
class TestRedisSettings:
    def test_defaults(self):
        settings = RedisSettings()
        assert settings.host == "localhost"
        assert settings.port == 6379
        assert settings.ssl is False

    def test_password_required(self, monkeypatch):
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        with pytest.raises(ValidationError):
            RedisSettings()

    def test_with_password(self):
        settings = RedisSettings(host="redis.example.com", password="secret", ssl=True)
        assert settings.password == "secret"
        assert settings.ssl is True


@pytest.mark.unit
class TestOSRMSettings:
    def test_default(self):
        settings = OSRMSettings()
        assert settings.base_url == "http://localhost:5000"

    def test_trailing_slash_removed(self):
        settings = OSRMSettings(base_url="http://example.com:5000/")
        assert settings.base_url == "http://example.com:5000"

    def test_invalid_url(self):
        with pytest.raises(ValidationError):
            OSRMSettings(base_url="not-a-url")


@pytest.mark.unit
class TestAPISettings:
    def test_key_required(self, monkeypatch):
        monkeypatch.delenv("API_KEY", raising=False)
        with pytest.raises(ValidationError):
            APISettings()

    def test_valid_key(self):
        settings = APISettings(key="my-secret-key")
        assert settings.key == "my-secret-key"


@pytest.mark.unit
class TestSettings:
    def test_integration(self, monkeypatch):
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        monkeypatch.setenv("KAFKA_SASL_USERNAME", "key")
        monkeypatch.setenv("KAFKA_SASL_PASSWORD", "secret")
        monkeypatch.setenv("KAFKA_SCHEMA_REGISTRY_URL", "http://localhost:8081")
        monkeypatch.setenv("KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO", "key:secret")
        monkeypatch.setenv("REDIS_HOST", "localhost")
        monkeypatch.setenv("REDIS_PASSWORD", "redis-secret")
        monkeypatch.setenv("API_KEY", "test-key")

        settings = Settings()
        assert settings.kafka.bootstrap_servers == "localhost:9092"
        assert settings.redis.host == "localhost"
        assert settings.simulation.speed_multiplier == 1.0

    def test_get_settings(self, monkeypatch):
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        monkeypatch.setenv("KAFKA_SASL_USERNAME", "key")
        monkeypatch.setenv("KAFKA_SASL_PASSWORD", "secret")
        monkeypatch.setenv("KAFKA_SCHEMA_REGISTRY_URL", "http://localhost:8081")
        monkeypatch.setenv("KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO", "key:secret")
        monkeypatch.setenv("REDIS_HOST", "localhost")
        monkeypatch.setenv("REDIS_PASSWORD", "redis-secret")
        monkeypatch.setenv("API_KEY", "test-key")

        settings = get_settings()
        assert isinstance(settings, Settings)
