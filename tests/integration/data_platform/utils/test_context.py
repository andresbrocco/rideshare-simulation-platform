"""Test context for unique ID generation.

This module provides the TestContext class that generates unique identifiers
for each test, allowing tests to run in parallel without ID conflicts and
enabling precise filtering of test-specific data in queries.
"""

import uuid
from dataclasses import dataclass, field


@dataclass
class TestContext:
    """Unique identifiers for a single test.

    Each test gets a unique test_id that can be used to generate
    predictable but unique IDs for trips, drivers, riders, and events.
    This allows tests to filter queries by their specific data without
    being affected by data from other tests or previous runs.

    Attributes:
        test_id: A unique identifier combining test name prefix and UUID
    """

    test_id: str = field(init=False)
    _test_name: str = field(default="")

    def __post_init__(self):
        """Generate unique test_id from test name and UUID."""
        prefix = self._test_name[:8] if self._test_name else "test"
        # Use first 8 chars of UUID for shorter but still unique IDs
        self.test_id = f"{prefix}-{uuid.uuid4().hex[:8]}"

    def trip_id(self, suffix: str = "001") -> str:
        """Generate unique trip ID for this test.

        Args:
            suffix: Optional suffix to distinguish multiple trips in same test

        Returns:
            Unique trip ID like "trip-testname-a1b2c3d4-001"
        """
        return f"trip-{self.test_id}-{suffix}"

    def driver_id(self, suffix: str = "001") -> str:
        """Generate unique driver ID for this test.

        Args:
            suffix: Optional suffix to distinguish multiple drivers in same test

        Returns:
            Unique driver ID like "driver-testname-a1b2c3d4-001"
        """
        return f"driver-{self.test_id}-{suffix}"

    def rider_id(self, suffix: str = "001") -> str:
        """Generate unique rider ID for this test.

        Args:
            suffix: Optional suffix to distinguish multiple riders in same test

        Returns:
            Unique rider ID like "rider-testname-a1b2c3d4-001"
        """
        return f"rider-{self.test_id}-{suffix}"

    def event_id(self, suffix: str = "001") -> str:
        """Generate unique event ID for this test.

        Args:
            suffix: Optional suffix to distinguish multiple events in same test

        Returns:
            Unique event ID like "event-testname-a1b2c3d4-001"
        """
        return f"event-{self.test_id}-{suffix}"

    def correlation_id(self) -> str:
        """Generate unique correlation ID for this test.

        Returns:
            Unique correlation ID matching the test_id
        """
        return f"corr-{self.test_id}"

    def filter_pattern(self) -> str:
        """SQL LIKE pattern for filtering this test's data.

        Returns:
            Pattern like "%testname-a1b2c3d4%" for use in WHERE clauses
        """
        return f"%{self.test_id}%"

    def marker_id(self) -> str:
        """Generate unique marker ID for Kafka test markers.

        Returns:
            Unique marker ID like "marker-testname-a1b2c3d4"
        """
        return f"marker-{self.test_id}"
