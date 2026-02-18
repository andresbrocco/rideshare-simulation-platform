"""Tests for logging context managers."""

import logging

import pytest

from src.sim_logging import ContextFilter, LogContext, log_context, log_trip_context


@pytest.mark.unit
class TestLogContext:
    """Tests for log_context context manager."""

    @pytest.fixture
    def logger(self):
        """Create a test logger with ContextFilter and a capturing handler."""
        logger = logging.getLogger("test.context")
        logger.setLevel(logging.DEBUG)
        return logger

    @pytest.fixture
    def captured_records(self, logger):
        """Capture log records for inspection."""
        records: list[logging.LogRecord] = []

        class RecordCapture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        handler = RecordCapture()
        handler.addFilter(ContextFilter())
        logger.addHandler(handler)
        yield records
        logger.removeHandler(handler)

    def test_log_context_adds_extra_fields(self, logger, captured_records):
        """Verify extra fields are added to log records via ContextFilter."""
        with log_context(driver_id="driver-123", rider_id="rider-456"):
            logger.info("Test message")

        assert len(captured_records) == 1
        record = captured_records[0]
        assert record.driver_id == "driver-123"
        assert record.rider_id == "rider-456"

    def test_log_context_does_not_modify_log_record_factory(self, logger, captured_records):
        """Verify log_context() does not replace the global LogRecordFactory."""
        original_factory = logging.getLogRecordFactory()

        with log_context(trip_id="trip-001"):
            # Factory should remain unchanged while inside the context
            assert logging.getLogRecordFactory() is original_factory
            logger.info("inside context")

        # Factory should still be unchanged after exiting the context
        assert logging.getLogRecordFactory() is original_factory

    def test_log_context_clears_on_exit(self, logger, captured_records):
        """Verify fields are cleared after context exits."""
        with log_context(trip_id="trip-002"):
            logger.info("inside")

        logger.info("outside")

        assert len(captured_records) == 2
        assert captured_records[0].trip_id == "trip-002"
        assert not hasattr(captured_records[1], "trip_id")


@pytest.mark.unit
class TestLogTripContext:
    """Tests for log_trip_context context manager."""

    @pytest.fixture
    def logger(self):
        """Create a test logger with ContextFilter and a capturing handler."""
        logger = logging.getLogger("test.trip_context")
        logger.setLevel(logging.DEBUG)
        return logger

    @pytest.fixture
    def captured_records(self, logger):
        """Capture log records for inspection."""
        records: list[logging.LogRecord] = []

        class RecordCapture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        handler = RecordCapture()
        handler.addFilter(ContextFilter())
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


@pytest.mark.unit
class TestLogContextGet:
    """Tests for LogContext.get() returning internal dict."""

    @pytest.fixture(autouse=True)
    def _clear_context(self):
        """Ensure clean context state for each test."""
        LogContext.clear()
        yield
        LogContext.clear()

    def test_get_returns_internal_dict(self):
        """Verify get() returns the same dict object as internal state."""
        LogContext.set(key="value")
        result = LogContext.get()
        assert result is LogContext._local.context

    def test_get_reflects_subsequent_set(self):
        """Verify the returned reference reflects later set() calls."""
        ref = LogContext.get()
        LogContext.set(new_key="new_value")
        assert ref["new_key"] == "new_value"
