import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class DLQConfig:
    enabled: bool
    validate_json: bool
    validate_schema: bool
    schema_dir: str

    @classmethod
    def from_env(cls) -> "DLQConfig":
        return cls(
            enabled=os.getenv("DLQ_ENABLED", "true").lower() == "true",
            validate_json=os.getenv("DLQ_VALIDATE_JSON", "false").lower() == "true",
            validate_schema=os.getenv("DLQ_VALIDATE_SCHEMA", "false").lower() == "true",
            schema_dir=os.getenv("DLQ_SCHEMA_DIR", "/app/schemas"),
        )


@dataclass
class BronzeIngestionConfig:
    kafka_bootstrap_servers: str
    kafka_group_id: str
    kafka_security_protocol: str
    kafka_sasl_mechanism: str
    kafka_sasl_username: str
    kafka_sasl_password: str
    delta_base_path: str
    batch_interval_seconds: int
    kafka_poll_timeout_ms: int
    s3_endpoint: Optional[str]
    aws_access_key_id: Optional[str]
    aws_secret_access_key: Optional[str]
    aws_region: str
    bronze_bucket: str
    dlq: DLQConfig

    @classmethod
    def from_env(cls) -> "BronzeIngestionConfig":
        return cls(
            kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092"),
            kafka_group_id=os.getenv("KAFKA_CONSUMER_GROUP", "bronze-ingestion"),
            kafka_security_protocol=os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),
            kafka_sasl_mechanism=os.getenv("KAFKA_SASL_MECHANISM", "PLAIN"),
            kafka_sasl_username=os.getenv("KAFKA_SASL_USERNAME", ""),
            kafka_sasl_password=os.getenv("KAFKA_SASL_PASSWORD", ""),
            delta_base_path=os.getenv("DELTA_BASE_PATH", "s3a://rideshare-bronze"),
            batch_interval_seconds=int(os.getenv("BATCH_INTERVAL_SECONDS", "10")),
            kafka_poll_timeout_ms=int(os.getenv("KAFKA_POLL_TIMEOUT_MS", "1000")),
            s3_endpoint=os.getenv("S3_ENDPOINT_URL", "") or os.getenv("S3_ENDPOINT", "") or None,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "") or None,
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "") or None,
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            bronze_bucket=os.getenv("BRONZE_BUCKET", "rideshare-bronze"),
            dlq=DLQConfig.from_env(),
        )

    def get_storage_options(self) -> Optional[dict[str, str]]:
        """Return storage_options dict for S3/MinIO access, or None for local paths."""
        if self.delta_base_path.startswith("s3://") or self.delta_base_path.startswith("s3a://"):
            opts: dict[str, str] = {
                "AWS_REGION": self.aws_region,
                "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
            }
            if self.s3_endpoint:
                opts["AWS_ENDPOINT_URL"] = self.s3_endpoint
                if self.s3_endpoint.startswith("http://"):
                    opts["AWS_ALLOW_HTTP"] = "true"
            if self.aws_access_key_id:
                opts["AWS_ACCESS_KEY_ID"] = self.aws_access_key_id
            if self.aws_secret_access_key:
                opts["AWS_SECRET_ACCESS_KEY"] = self.aws_secret_access_key
            return opts
        return None
