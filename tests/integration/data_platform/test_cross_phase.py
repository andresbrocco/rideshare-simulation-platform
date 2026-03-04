"""Cross-phase integration tests for data platform.

Tests integration between phases of the medallion lakehouse architecture.
Spark Thrift Server-dependent tests (XP-001, XP-002) have been removed as part
of the Spark removal (Trino is now used for SQL access to Delta tables).
"""

import pytest


pytestmark = [
    pytest.mark.cross_phase,
    pytest.mark.requires_profiles("core", "data-pipeline"),
]
