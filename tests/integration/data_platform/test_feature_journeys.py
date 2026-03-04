"""Feature journey integration tests for data platform.

Tests complete end-to-end flows through the medallion lakehouse architecture.
Spark Thrift Server-dependent tests (FJ-001, FJ-003) have been removed as part
of the Spark removal (Trino is now used for SQL access to Delta tables).
"""

import pytest


pytestmark = [
    pytest.mark.feature_journey,
    pytest.mark.requires_profiles("core", "data-pipeline"),
]
