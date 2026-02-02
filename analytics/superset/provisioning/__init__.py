"""Superset Dashboard Provisioning Module.

A declarative, robust provisioning system for Superset dashboards
using the REST API with proper error handling and retry logic.
"""

from provisioning.client import SupersetClient
from provisioning.exceptions import (
    AuthenticationError,
    ConnectionError,
    PermanentError,
    RateLimitError,
    ResourceNotFoundError,
    ServerBusyError,
    SupersetProvisioningError,
    TableNotFoundError,
    TransientError,
    ValidationError,
)
from provisioning.provisioner import DashboardProvisioner, ProvisioningResult

__all__ = [
    "SupersetClient",
    "DashboardProvisioner",
    "ProvisioningResult",
    "SupersetProvisioningError",
    "TransientError",
    "ConnectionError",
    "RateLimitError",
    "ServerBusyError",
    "PermanentError",
    "AuthenticationError",
    "ValidationError",
    "ResourceNotFoundError",
    "TableNotFoundError",
]
