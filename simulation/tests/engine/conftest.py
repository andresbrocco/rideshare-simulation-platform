"""Shared fixtures for engine tests."""

from unittest.mock import MagicMock, Mock

import pytest


def create_mock_sqlite_db():
    """Create a mock SQLite database with proper context manager support."""
    db = Mock()
    session_mock = MagicMock()

    # Mock the session context manager
    session_mock.__enter__ = Mock(return_value=session_mock)
    session_mock.__exit__ = Mock(return_value=None)

    # Mock the execute method to return empty results
    result_mock = Mock()
    scalars_mock = Mock()
    scalars_mock.all = Mock(return_value=[])
    result_mock.scalars = Mock(return_value=scalars_mock)
    session_mock.execute = Mock(return_value=result_mock)

    db.session = Mock(return_value=session_mock)
    return db


@pytest.fixture
def mock_sqlite_db():
    """Mock SQLite database with proper context manager support."""
    return create_mock_sqlite_db()
