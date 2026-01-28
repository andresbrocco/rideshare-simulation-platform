"""Standardized exception hierarchy for the simulation platform."""

from typing import Any


class SimulationError(Exception):
    """Base exception for all simulation errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class TransientError(SimulationError):
    """Errors that may succeed on retry."""

    pass


class NetworkError(TransientError):
    """Network-related transient errors (timeout, connection refused)."""

    pass


class ServiceUnavailableError(TransientError):
    """External service temporarily unavailable (5xx responses)."""

    pass


class PersistenceError(TransientError):
    """Database or state persistence failed after retries."""

    pass


class PermanentError(SimulationError):
    """Errors that will not succeed on retry."""

    pass


class ValidationError(PermanentError):
    """Invalid input or data format."""

    pass


class NotFoundError(PermanentError):
    """Requested entity does not exist."""

    pass


class StateError(PermanentError):
    """Invalid state transition."""

    pass


class ConfigurationError(PermanentError):
    """Missing or invalid configuration."""

    pass


class FatalError(SimulationError):
    """Critical errors requiring immediate shutdown."""

    pass
