"""Simplified logging setup for performance controller."""

import logging
import sys


def setup_logging(
    level: str = "INFO",
    json_output: bool = False,
    environment: str = "development",
) -> None:
    """Configure root logger with appropriate formatting."""
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    if json_output:
        handler.setFormatter(
            logging.Formatter(
                '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                '"logger": "%(name)s", "message": "%(message)s", '
                '"service_name": "performance-controller", '
                f'"environment": "{environment}"}}'
            )
        )
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )

    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper()))

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
