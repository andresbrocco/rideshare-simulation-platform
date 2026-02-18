"""Thread-local logging context for adding fields to log records."""

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


class LogContext:
    """Thread-local storage for log context fields."""

    _local = threading.local()

    @classmethod
    def set(cls, **kwargs: Any) -> None:
        if not hasattr(cls._local, "context"):
            cls._local.context = {}
        cls._local.context.update(kwargs)

    @classmethod
    def get(cls) -> dict[str, Any]:
        if not hasattr(cls._local, "context"):
            cls._local.context = {}
        ctx: dict[str, Any] = cls._local.context
        return ctx

    @classmethod
    def clear(cls) -> None:
        cls._local.context = {}


class ContextFilter(logging.Filter):
    """Injects LogContext fields into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in LogContext.get().items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


@contextmanager
def log_context(**kwargs: Any) -> Iterator[None]:
    """Context manager that sets logging context fields.

    Fields are injected into log records via ContextFilter, which must
    be attached to the handler (see setup_logging).
    """
    LogContext.set(**kwargs)
    try:
        yield
    finally:
        LogContext.clear()


@contextmanager
def log_trip_context(trip_id: str, **kwargs: Any) -> Iterator[None]:
    """Convenience context manager for trip operations."""
    correlation_id = kwargs.pop("correlation_id", trip_id)
    with log_context(trip_id=trip_id, correlation_id=correlation_id, **kwargs):
        yield
