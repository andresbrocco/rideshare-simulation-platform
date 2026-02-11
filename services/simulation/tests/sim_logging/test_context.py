"""Tests for logging context managers."""

import logging

import pytest

from src.sim_logging import log_context, log_trip_context


@pytest.mark.unit
class TestLogContext:
    """Tests for log_context context manager."""

    @pytest.fixture
    def logger(self):
        """Create a test logger with a handler that captures records."""
        logger = logging.getLogger("test.context")
        logger.setLevel(logging.DEBUG)
        return logger

    @pytest.fixture
    def captured_records(self, logger):
        """Capture log records for inspection."""
        records = []

        class RecordCapture(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = RecordCapture()
        logger.addHandler(handler)
        yield records
        logger.removeHandler(handler)

    def test_log_context_adds_extra_fields(self, logger, captured_records):
        """Verify extra fields are added to log records."""
        with log_context(driver_id="driver-123", rider_id="rider-456"):
            logger.info("Test message")

        assert len(captured_records) == 1
        record = captured_records[0]
        assert record.driver_id == "driver-123"
        assert record.rider_id == "rider-456"


@pytest.mark.unit
class TestLogTripContext:
    """Tests for log_trip_context context manager."""

    @pytest.fixture
    def logger(self):
        """Create a test logger with a handler that captures records."""
        logger = logging.getLogger("test.trip_context")
        logger.setLevel(logging.DEBUG)
        return logger

    @pytest.fixture
    def captured_records(self, logger):
        """Capture log records for inspection."""
        records = []

        class RecordCapture(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = RecordCapture()
        logger.addHandler(handler)
        yield records
        logger.removeHandler(handler)

    def test_log_trip_context_sets_trip_and_correlation(self, logger, captured_records):
        """Verify trip_id and correlation_id are set."""
        with log_trip_context(trip_id="trip-789"):
            logger.info("Trip log message")

        assert len(captured_records) == 1
        record = captured_records[0]
        assert record.trip_id == "trip-789"
        assert hasattr(record, "correlation_id")
        # correlation_id should be set (either to trip_id or a generated value)
        assert record.correlation_id is not None
