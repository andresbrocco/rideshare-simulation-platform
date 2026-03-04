"""Data flow integration tests for data platform.

Tests data integrity and lineage through the medallion lakehouse.
Spark Thrift Server-dependent tests (DF-001, DF-002) have been removed as part
of the Spark removal (Trino is now used for SQL access to Delta tables).
"""

import pytest


pytestmark = [
    pytest.mark.data_flow,
    pytest.mark.requires_profiles("core", "data-pipeline"),
]
