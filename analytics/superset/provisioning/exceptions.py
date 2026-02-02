"""Exception hierarchy for Superset provisioning.

Exceptions are categorized as:
- TransientError: Retryable errors (connection issues, rate limits, server busy)
- PermanentError: Non-retryable errors (auth failures, validation errors)
"""


class SupersetProvisioningError(Exception):
    """Base exception for all provisioning errors."""

    pass


# =============================================================================
# Transient (Retryable) Errors
# =============================================================================


class TransientError(SupersetProvisioningError):
    """Base class for retryable errors."""

    pass


class ConnectionError(TransientError):
    """Network connection failure."""

    pass


class RateLimitError(TransientError):
    """HTTP 429 Too Many Requests."""

    def __init__(self, retry_after: int | None = None) -> None:
        self.retry_after = retry_after
        msg = "Rate limit exceeded"
        if retry_after:
            msg += f" (retry after {retry_after}s)"
        super().__init__(msg)


class ServerBusyError(TransientError):
    """HTTP 503 Service Unavailable or similar server overload."""

    pass


# =============================================================================
# Permanent (Non-Retryable) Errors
# =============================================================================


class PermanentError(SupersetProvisioningError):
    """Base class for non-retryable errors."""

    pass


class AuthenticationError(PermanentError):
    """HTTP 401 Unauthorized or authentication failure."""

    pass


class ValidationError(PermanentError):
    """HTTP 400/422 validation errors or invalid input."""

    def __init__(self, message: str, errors: list[dict[str, str]] | None = None) -> None:
        self.errors = errors or []
        super().__init__(message)


class ResourceNotFoundError(PermanentError):
    """HTTP 404 Not Found."""

    def __init__(self, resource_type: str, identifier: str) -> None:
        self.resource_type = resource_type
        self.identifier = identifier
        super().__init__(f"{resource_type} not found: {identifier}")


class TableNotFoundError(PermanentError):
    """Required table does not exist in the database."""

    def __init__(self, table_name: str, database: str = "lakehouse") -> None:
        self.table_name = table_name
        self.database = database
        super().__init__(f"Table '{table_name}' not found in database '{database}'")
