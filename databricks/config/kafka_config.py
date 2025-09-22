"""
Kafka connection configuration for Confluent Cloud.

Provides helper functions to build Kafka connection config from Databricks secrets.
"""

try:
    from databricks.sdk.runtime import dbutils
except ImportError:
    # For local testing/development - mock dbutils
    class MockDBUtils:
        class Secrets:
            def get(self, scope: str, key: str) -> str:
                return f"mock-{key}"

        secrets = Secrets()

    dbutils = MockDBUtils()


def get_kafka_config() -> dict:
    """
    Build Kafka connection configuration from Databricks secrets.

    Returns:
        Dictionary with Kafka connection parameters including:
        - kafka.bootstrap.servers
        - kafka.security.protocol
        - kafka.sasl.mechanism
        - kafka.sasl.jaas.config
    """
    bootstrap_servers = dbutils.secrets.get("kafka", "bootstrap_servers")
    api_key = dbutils.secrets.get("kafka", "api_key")
    api_secret = dbutils.secrets.get("kafka", "api_secret")

    # Build SASL JAAS config for Confluent Cloud authentication
    jaas_config = (
        "org.apache.kafka.common.security.plain.PlainLoginModule required "
        f'username="{api_key}" '
        f'password="{api_secret}";'
    )

    return {
        "kafka.bootstrap.servers": bootstrap_servers,
        "kafka.security.protocol": "SASL_SSL",
        "kafka.sasl.mechanism": "PLAIN",
        "kafka.sasl.jaas.config": jaas_config,
    }
