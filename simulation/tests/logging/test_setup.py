"""Tests for logging setup."""

import logging

import pytest

from src.logging import get_logger, setup_logging


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_configures_root_logger(self):
        """Verify handler is added to root logger."""
        # Clear any existing handlers
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers.copy()

        try:
            root_logger.handlers.clear()
            setup_logging()

            assert len(root_logger.handlers) > 0
        finally:
            # Restore original handlers
            root_logger.handlers = original_handlers

    def test_setup_logging_suppresses_noisy_loggers(self):
        """Verify confluent_kafka and urllib3 are set to WARNING."""
        setup_logging()

        kafka_logger = logging.getLogger("confluent_kafka")
        urllib3_logger = logging.getLogger("urllib3")

        assert kafka_logger.level >= logging.WARNING
        assert urllib3_logger.level >= logging.WARNING


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_named_logger(self):
        """Verify logger name is set correctly."""
        logger = get_logger("test.module")

        assert logger.name == "test.module"
        assert isinstance(logger, logging.Logger)
