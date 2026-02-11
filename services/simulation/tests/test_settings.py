import pytest
from pydantic import ValidationError

from settings import (
    APISettings,
    AWSSettings,
    DatabricksSettings,
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
        assert settings.speed_multiplier == 1
        assert settings.log_level == "INFO"
        assert settings.checkpoint_interval == 300

    def test_env_prefix(self, monkeypatch):
        monkeypatch.setenv("SIM_SPEED_MULTIPLIER", "10")
        monkeypatch.setenv("SIM_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("SIM_CHECKPOINT_INTERVAL", "600")

        settings = SimulationSettings()
        assert settings.speed_multiplier == 10
        assert settings.log_level == "DEBUG"
        assert settings.checkpoint_interval == 600

    def test_validation(self):
        with pytest.raises(ValidationError):
            SimulationSettings(speed_multiplier=0)

        with pytest.raises(ValidationError):
            SimulationSettings(speed_multiplier=1025)  # Max is 1024

        with pytest.raises(ValidationError):
            SimulationSettings(checkpoint_interval=30)


@pytest.mark.unit
class TestKafkaSettings:
    def test_defaults(self):
        settings = KafkaSettings()
        assert settings.bootstrap_servers == "localhost:9092"
        assert settings.security_protocol == "PLAINTEXT"
        assert settings.sasl_username == ""
        assert settings.sasl_password == ""

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
        assert settings.password is None
        assert settings.ssl is False

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
class TestDatabricksSettings:
    def test_defaults(self):
        settings = DatabricksSettings()
        assert settings.host == ""
        assert settings.token == ""
        assert settings.catalog == "rideshare"

    def test_valid_config(self):
        settings = DatabricksSettings(
            host="https://dbc-12345.cloud.databricks.com",
            token="dapi12345",
        )
        assert settings.host == "https://dbc-12345.cloud.databricks.com"
        assert settings.catalog == "rideshare"

    def test_invalid_host(self):
        with pytest.raises(ValidationError):
            DatabricksSettings(
                host="http://insecure.databricks.com",
                token="token",
            )


@pytest.mark.unit
class TestAWSSettings:
    def test_defaults(self):
        settings = AWSSettings()
        assert settings.region == "us-east-1"
        assert settings.access_key_id is None
        assert settings.secret_access_key is None


@pytest.mark.unit
class TestAPISettings:
    def test_defaults(self):
        settings = APISettings()
        assert settings.key == ""

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
        monkeypatch.setenv("DATABRICKS_HOST", "https://dbc-12345.cloud.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "token")
        monkeypatch.setenv("API_KEY", "test-key")

        settings = Settings()
        assert settings.kafka.bootstrap_servers == "localhost:9092"
        assert settings.redis.host == "localhost"
        assert settings.simulation.speed_multiplier == 1

    def test_get_settings(self, monkeypatch):
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        monkeypatch.setenv("KAFKA_SASL_USERNAME", "key")
        monkeypatch.setenv("KAFKA_SASL_PASSWORD", "secret")
        monkeypatch.setenv("KAFKA_SCHEMA_REGISTRY_URL", "http://localhost:8081")
        monkeypatch.setenv("KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO", "key:secret")
        monkeypatch.setenv("REDIS_HOST", "localhost")
        monkeypatch.setenv("DATABRICKS_HOST", "https://dbc-12345.cloud.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "token")
        monkeypatch.setenv("API_KEY", "test-key")

        settings = get_settings()
        assert isinstance(settings, Settings)
