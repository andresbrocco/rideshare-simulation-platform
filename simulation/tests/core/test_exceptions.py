"""Tests for the exception hierarchy."""

import pytest

from src.core.exceptions import (
    ConfigurationError,
    FatalError,
    NetworkError,
    NotFoundError,
    PermanentError,
    ServiceUnavailableError,
    SimulationError,
    StateError,
    TransientError,
    ValidationError,
)


class TestExceptionHierarchy:
    """Test that exception classes follow the correct inheritance."""

    def test_transient_errors_inherit_from_simulation_error(self):
        assert issubclass(TransientError, SimulationError)
        assert issubclass(NetworkError, TransientError)
        assert issubclass(ServiceUnavailableError, TransientError)

    def test_permanent_errors_inherit_from_simulation_error(self):
        assert issubclass(PermanentError, SimulationError)
        assert issubclass(ValidationError, PermanentError)
        assert issubclass(NotFoundError, PermanentError)
        assert issubclass(StateError, PermanentError)
        assert issubclass(ConfigurationError, PermanentError)

    def test_fatal_errors_inherit_from_simulation_error(self):
        assert issubclass(FatalError, SimulationError)


class TestExceptionAttributes:
    """Test exception message and details handling."""

    def test_simulation_error_stores_message(self):
        err = SimulationError("test message")
        assert err.message == "test message"
        assert str(err) == "test message"

    def test_simulation_error_stores_details(self):
        err = SimulationError("test", details={"key": "value"})
        assert err.details == {"key": "value"}

    def test_simulation_error_default_details_is_empty_dict(self):
        err = SimulationError("test")
        assert err.details == {}

    def test_network_error_inherits_attributes(self):
        err = NetworkError("connection refused", details={"host": "localhost"})
        assert err.message == "connection refused"
        assert err.details == {"host": "localhost"}

    def test_validation_error_with_details(self):
        err = ValidationError(
            "Invalid input",
            details={"field": "email", "value": "not-an-email"},
        )
        assert err.message == "Invalid input"
        assert err.details["field"] == "email"


class TestExceptionCatching:
    """Test that exceptions can be caught at appropriate levels."""

    def test_catch_transient_errors(self):
        """Transient errors should be catchable as TransientError."""
        with pytest.raises(TransientError):
            raise NetworkError("timeout")

        with pytest.raises(TransientError):
            raise ServiceUnavailableError("503")

    def test_catch_permanent_errors(self):
        """Permanent errors should be catchable as PermanentError."""
        with pytest.raises(PermanentError):
            raise ValidationError("invalid")

        with pytest.raises(PermanentError):
            raise NotFoundError("not found")

        with pytest.raises(PermanentError):
            raise StateError("bad state")

        with pytest.raises(PermanentError):
            raise ConfigurationError("missing config")

    def test_catch_all_simulation_errors(self):
        """All custom errors should be catchable as SimulationError."""
        errors = [
            NetworkError("net"),
            ServiceUnavailableError("service"),
            ValidationError("valid"),
            NotFoundError("not found"),
            StateError("state"),
            ConfigurationError("config"),
            FatalError("fatal"),
        ]
        for err in errors:
            with pytest.raises(SimulationError):
                raise err

    def test_transient_error_not_caught_as_permanent(self):
        """Transient errors should not be caught as PermanentError."""
        try:
            raise NetworkError("timeout")
        except PermanentError:
            pytest.fail("NetworkError should not be caught as PermanentError")
        except TransientError:
            pass  # Expected

    def test_permanent_error_not_caught_as_transient(self):
        """Permanent errors should not be caught as TransientError."""
        try:
            raise ValidationError("invalid")
        except TransientError:
            pytest.fail("ValidationError should not be caught as TransientError")
        except PermanentError:
            pass  # Expected
