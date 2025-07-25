"""Database utility functions."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return current UTC time as naive datetime for SQLite compatibility.

    SQLite stores datetimes as TEXT without timezone info. Using naive
    datetimes that represent UTC ensures consistent comparisons.
    """
    return datetime.now(UTC).replace(tzinfo=None)
