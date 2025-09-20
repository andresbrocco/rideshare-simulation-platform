"""Log formatters for JSON and human-readable output."""

import json
import logging
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    """Formats logs as JSON for production environments."""

    def __init__(self, environment: str = "development"):
        super().__init__()
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "env": self.environment,
        }

        for field in ("trip_id", "driver_id", "rider_id", "correlation_id"):
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class DevFormatter(logging.Formatter):
    """Human-readable format for development."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
