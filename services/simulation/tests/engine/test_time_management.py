"""Tests for TimeManager - simulation time tracking and conversions."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
import simpy


@pytest.fixture
def mock_env():
    """Create a SimPy environment for testing."""
    return simpy.Environment()


@pytest.fixture
def fixed_start_time():
    """Fixed simulation start time for deterministic testing."""
    tz = timezone(timedelta(hours=-3))
    return datetime(2025, 8, 13, 12, 0, 0, tzinfo=tz)


@pytest.fixture
def time_manager(mock_env, fixed_start_time):
    """Create TimeManager with mock environment."""
    from engine import TimeManager

    return TimeManager(fixed_start_time, mock_env)


@pytest.mark.unit
class TestTimeManagerInit:
    def test_time_manager_init(self, time_manager, fixed_start_time):
        """Initializes with simulation start time."""
        assert time_manager._simulation_start_time == fixed_start_time


@pytest.mark.unit
class TestCurrentTime:
    def test_current_time_at_zero(self, time_manager, fixed_start_time):
        """Returns start time when env.now=0."""
        current = time_manager.current_time()
        assert current == fixed_start_time.astimezone(UTC)

    def test_current_time_after_advance(self, time_manager, mock_env, fixed_start_time):
        """Returns correct time after 1 hour advancement."""
        mock_env.run(until=3600)
        current = time_manager.current_time()
        expected = fixed_start_time.astimezone(UTC) + timedelta(hours=1)
        assert current == expected

    def test_current_time_after_day(self, time_manager, mock_env, fixed_start_time):
        """Handles multi-day simulations."""
        mock_env.run(until=86400)
        current = time_manager.current_time()
        expected = fixed_start_time.astimezone(UTC) + timedelta(days=1)
        assert current == expected


@pytest.mark.unit
class TestTimestampFormatting:
    def test_format_timestamp_iso8601(self, time_manager):
        """Formats timestamp as ISO 8601 UTC."""
        dt = datetime(2025, 8, 13, 18, 0, 0, tzinfo=UTC)
        formatted = time_manager.format_timestamp(dt)
        assert formatted == "2025-08-13T18:00:00Z"

    def test_format_timestamp_default(self, time_manager, mock_env):
        """Uses current_time() when dt not provided."""
        mock_env.run(until=3600)
        formatted = time_manager.format_timestamp()
        assert formatted.endswith("Z")
        assert "2025-08-13" in formatted


@pytest.mark.unit
class TestTimeConversions:
    def test_simulated_seconds_to_datetime(self, time_manager, fixed_start_time):
        """Converts SimPy seconds to datetime."""
        dt = time_manager.to_datetime(7200)
        expected = fixed_start_time.astimezone(UTC) + timedelta(hours=2)
        assert dt == expected

    def test_datetime_to_simulated_seconds(self, time_manager, fixed_start_time):
        """Converts datetime back to SimPy seconds."""
        dt = fixed_start_time + timedelta(hours=3)
        seconds = time_manager.to_seconds(dt)
        assert seconds == 10800


@pytest.mark.unit
class TestElapsedTime:
    def test_elapsed_time(self, time_manager, mock_env):
        """Calculates elapsed simulation time."""
        mock_env.run(until=5400)
        elapsed = time_manager.elapsed_time()
        assert elapsed == timedelta(seconds=5400)


@pytest.mark.unit
class TestDayCalculations:
    def test_simulation_day_number(self, time_manager, mock_env):
        """Gets current simulation day (0-indexed)."""
        mock_env.run(until=172800)
        day = time_manager.current_day()
        assert day == 2

    def test_time_of_day(self, time_manager, mock_env):
        """Gets time-of-day in seconds."""
        mock_env.run(until=90000)
        time_of_day = time_manager.time_of_day()
        assert time_of_day == 3600

    def test_time_of_day_at_midnight(self, time_manager, mock_env):
        """Time-of-day wraps at midnight."""
        mock_env.run(until=86400)
        time_of_day = time_manager.time_of_day()
        assert time_of_day == 0


@pytest.mark.unit
class TestBusinessHours:
    def test_is_business_hours_true(self, time_manager, mock_env):
        """Checks if current time is business hours (9 AM - 6 PM, Mon-Fri)."""
        mock_env.run(until=7200)
        is_business = time_manager.is_business_hours()
        assert is_business is True

    def test_is_business_hours_false_early(self, time_manager, mock_env):
        """Returns False before 9 AM."""
        mock_env.run(until=61200)
        is_business = time_manager.is_business_hours()
        assert is_business is False

    def test_is_business_hours_false_late(self, time_manager, mock_env):
        """Returns False after 6 PM."""
        mock_env.run(until=32400)
        is_business = time_manager.is_business_hours()
        assert is_business is False


@pytest.mark.unit
class TestDurationFormatting:
    def test_format_duration_complex(self, time_manager):
        """Formats duration as human-readable."""
        formatted = time_manager.format_duration(7265)
        assert formatted == "2h 1m 5s"

    def test_format_duration_zero(self, time_manager):
        """Handles zero seconds."""
        formatted = time_manager.format_duration(0)
        assert formatted == "0s"

    def test_format_duration_only_seconds(self, time_manager):
        """Handles less than 1 minute."""
        formatted = time_manager.format_duration(59)
        assert formatted == "59s"

    def test_format_duration_only_hours(self, time_manager):
        """Handles exact hours."""
        formatted = time_manager.format_duration(3600)
        assert formatted == "1h 0m 0s"

    def test_format_duration_hours_minutes(self, time_manager):
        """Handles hours and minutes."""
        formatted = time_manager.format_duration(7260)
        assert formatted == "2h 1m 0s"
