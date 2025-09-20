"""Tests for logging filters."""

import logging

import pytest

from src.logging import DefaultCorrelationFilter, PIIFilter


class TestPIIFilter:
    """Tests for PIIFilter."""

    @pytest.fixture
    def pii_filter(self):
        """Create a PIIFilter instance."""
        return PIIFilter()

    @pytest.fixture
    def make_record(self):
        """Factory for creating log records with specific messages."""

        def _make_record(msg: str) -> logging.LogRecord:
            return logging.LogRecord(
                name="test.logger",
                level=logging.INFO,
                pathname="test.py",
                lineno=10,
                msg=msg,
                args=(),
                exc_info=None,
            )

        return _make_record

    def test_pii_filter_masks_email(self, pii_filter, make_record):
        """Test that email addresses are masked."""
        record = make_record("contact: john@example.com")
        pii_filter.filter(record)

        assert "[EMAIL]" in record.msg
        assert "john@example.com" not in record.msg

    def test_pii_filter_masks_phone(self, pii_filter, make_record):
        """Test that phone numbers are masked."""
        record = make_record("call 555-123-4567")
        pii_filter.filter(record)

        assert "[PHONE]" in record.msg
        assert "555-123-4567" not in record.msg

    def test_pii_filter_masks_multiple(self, pii_filter, make_record):
        """Test handling multiple PII in one message."""
        record = make_record("User john@example.com called 555-123-4567")
        pii_filter.filter(record)

        assert "[EMAIL]" in record.msg
        assert "[PHONE]" in record.msg
        assert "john@example.com" not in record.msg
        assert "555-123-4567" not in record.msg


class TestDefaultCorrelationFilter:
    """Tests for DefaultCorrelationFilter."""

    @pytest.fixture
    def correlation_filter(self):
        """Create a DefaultCorrelationFilter instance."""
        return DefaultCorrelationFilter()

    @pytest.fixture
    def log_record(self):
        """Create a basic log record."""
        return logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

    def test_correlation_filter_adds_default(self, correlation_filter, log_record):
        """Test that default correlation_id is added when missing."""
        # Record should not have correlation_id initially
        assert not hasattr(log_record, "correlation_id")

        correlation_filter.filter(log_record)

        assert hasattr(log_record, "correlation_id")
        assert log_record.correlation_id == "-"
