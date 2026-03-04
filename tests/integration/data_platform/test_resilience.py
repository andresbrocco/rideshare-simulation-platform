"""Resilience integration tests for data platform.

Tests data consistency and recovery under failure conditions.
Spark Thrift Server-dependent tests (NEW-005, NEW-006, REG-001) have been
removed as part of the Spark removal (Trino is now used for SQL access to
Delta tables).
"""

import pytest


pytestmark = [
    pytest.mark.resilience,
    pytest.mark.requires_profiles("core", "data-pipeline"),
]
