"""Tests for logging formatters."""

import json
import logging

import pytest

from src.logging import DevFormatter, JSONFormatter


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    @pytest.fixture
    def formatter(self):
        """Create a JSONFormatter instance."""
        return JSONFormatter()

    @pytest.fixture
    def log_record(self):
        """Create a basic log record."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        return record

    def test_json_formatter_basic_output(self, formatter, log_record):
        """Verify JSON format with timestamp, level, logger, message."""
        output = formatter.format(log_record)
        data = json.loads(output)

        assert "timestamp" in data
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "Test message"

    def test_json_formatter_includes_extra_fields(self, formatter, log_record):
        """Verify trip_id, driver_id, correlation_id from extra={}."""
        log_record.trip_id = "trip-123"
        log_record.driver_id = "driver-456"
        log_record.correlation_id = "corr-789"

        output = formatter.format(log_record)
        data = json.loads(output)

        assert data["trip_id"] == "trip-123"
        assert data["driver_id"] == "driver-456"
        assert data["correlation_id"] == "corr-789"

    def test_json_formatter_includes_environment(self, formatter, log_record):
        """Verify env field is present."""
        output = formatter.format(log_record)
        data = json.loads(output)

        assert "env" in data


class TestDevFormatter:
    """Tests for DevFormatter."""

    @pytest.fixture
    def formatter(self):
        """Create a DevFormatter instance."""
        return DevFormatter()

    @pytest.fixture
    def log_record(self):
        """Create a basic log record."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        return record

    def test_dev_formatter_output(self, formatter, log_record):
        """Verify human-readable format."""
        output = formatter.format(log_record)

        # Should contain timestamp, level, logger name, and message
        assert "INFO" in output
        assert "test.logger" in output
        assert "Test message" in output
