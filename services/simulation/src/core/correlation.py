"""Correlation context for distributed tracing."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

# Context variables for correlation IDs
current_correlation_id: ContextVar[str | None] = ContextVar(
    "correlation_id", default=None
)
current_session_id: ContextVar[str | None] = ContextVar("session_id", default=None)


class CorrelationFilter(logging.Filter):
    """Logging filter that adds correlation IDs to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = current_correlation_id.get() or "-"
        record.session_id = current_session_id.get() or "-"
        return True


def setup_correlation_logging(session_id: str) -> None:
    """Configure root logger with correlation filter.

    Args:
        session_id: The simulation session ID.
    """
    current_session_id.set(session_id)

    # Add correlation filter to root logger
    root = logging.getLogger()
    correlation_filter = CorrelationFilter()

    for handler in root.handlers:
        handler.addFilter(correlation_filter)


def get_correlation_formatter() -> logging.Formatter:
    """Get a log formatter that includes correlation fields."""
    return logging.Formatter(
        "%(asctime)s [%(levelname)s] [session=%(session_id)s] "
        "[corr=%(correlation_id)s] %(name)s: %(message)s"
    )


@contextmanager
def with_correlation(correlation_id: str) -> Iterator[None]:
    """Context manager to set correlation ID for a block of code.

    Usage:
        with with_correlation(trip.trip_id):
            logger.info("Processing trip")  # Will include correlation_id in log
            do_something()
    """
    token = current_correlation_id.set(correlation_id)
    try:
        yield
    finally:
        current_correlation_id.reset(token)


def get_current_correlation_id() -> str | None:
    """Get the current correlation ID from context."""
    return current_correlation_id.get()


def get_current_session_id() -> str | None:
    """Get the current session ID from context."""
    return current_session_id.get()
