"""Logging setup and configuration."""

import logging
import sys

from .context import ContextFilter
from .filters import DefaultCorrelationFilter, PIIFilter
from .formatters import DevFormatter, JSONFormatter


def setup_logging(
    level: str = "INFO",
    json_output: bool = False,
    environment: str = "development",
) -> None:
    """Configure the root logger with appropriate formatter and filters."""
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    if json_output:
        handler.setFormatter(JSONFormatter(environment))
    else:
        handler.setFormatter(DevFormatter())

    handler.addFilter(PIIFilter())
    handler.addFilter(DefaultCorrelationFilter())
    handler.addFilter(ContextFilter())

    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper()))

    logging.getLogger("confluent_kafka").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)
