"""Shared fixtures for engine tests."""

from contextlib import contextmanager
from unittest.mock import MagicMock, Mock

import pytest


def create_mock_sqlite_db():
    """Create a mock SQLite database with proper context manager support.

    The sqlite_db is used as a callable that returns a context manager:
    with sqlite_db() as session:
        ...
    """
    session_mock = MagicMock()

    # Mock the execute method to return empty results
    result_mock = Mock()
    scalars_mock = Mock()
    scalars_mock.all = Mock(return_value=[])
    result_mock.scalars = Mock(return_value=scalars_mock)
    session_mock.execute = Mock(return_value=result_mock)

    # Create a context manager that yields the session mock
    @contextmanager
    def session_factory():
        yield session_mock

    return session_factory


@pytest.fixture
def mock_sqlite_db():
    """Mock SQLite database with proper context manager support."""
    return create_mock_sqlite_db()
