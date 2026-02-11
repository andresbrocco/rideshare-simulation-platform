"""Tests for transaction utilities."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.schema import Base, SimulationMetadata
from src.db.transaction import savepoint, transaction


@pytest.fixture
def engine():
    """Create an in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_maker(engine):
    """Create a session factory."""
    return sessionmaker(bind=engine)


@pytest.mark.unit
class TestTransaction:
    """Tests for the transaction context manager."""

    def test_transaction_commits_on_success(self, session_maker):
        """Transaction should commit when no exception is raised."""
        with session_maker() as session, transaction(session):
            metadata = SimulationMetadata(key="test_key", value="test_value")
            session.add(metadata)

        # Verify data was committed
        with session_maker() as session:
            result = session.get(SimulationMetadata, "test_key")
            assert result is not None
            assert result.value == "test_value"

    def test_transaction_rolls_back_on_exception(self, session_maker):
        """Transaction should rollback when an exception is raised."""
        with (  # noqa: SIM117
            session_maker() as session,
            pytest.raises(ValueError, match="intentional error"),
        ):
            with transaction(session):
                metadata = SimulationMetadata(key="rollback_key", value="value")
                session.add(metadata)
                raise ValueError("intentional error")

        # Verify data was NOT committed
        with session_maker() as session:
            result = session.get(SimulationMetadata, "rollback_key")
            assert result is None

    def test_transaction_multiple_operations(self, session_maker):
        """Transaction should commit multiple operations atomically."""
        with session_maker() as session, transaction(session):
            session.add(SimulationMetadata(key="key1", value="value1"))
            session.add(SimulationMetadata(key="key2", value="value2"))
            session.add(SimulationMetadata(key="key3", value="value3"))

        # Verify all data was committed
        with session_maker() as session:
            assert session.get(SimulationMetadata, "key1") is not None
            assert session.get(SimulationMetadata, "key2") is not None
            assert session.get(SimulationMetadata, "key3") is not None

    def test_transaction_partial_rollback(self, session_maker):
        """All operations in a transaction should rollback on failure."""
        with session_maker() as session, pytest.raises(ValueError):  # noqa: SIM117
            with transaction(session):
                session.add(SimulationMetadata(key="partial1", value="value1"))
                session.add(SimulationMetadata(key="partial2", value="value2"))
                # Flush to ensure records are staged
                session.flush()
                raise ValueError("failure after flush")

        # Verify NONE of the data was committed
        with session_maker() as session:
            assert session.get(SimulationMetadata, "partial1") is None
            assert session.get(SimulationMetadata, "partial2") is None


@pytest.mark.unit
class TestSavepoint:
    """Tests for the savepoint context manager."""

    def test_savepoint_commits_within_transaction(self, session_maker):
        """Savepoint should commit within an outer transaction."""
        with session_maker() as session, transaction(session):
            session.add(SimulationMetadata(key="outer", value="outer_value"))

            with savepoint(session):
                session.add(SimulationMetadata(key="inner", value="inner_value"))

        # Verify both records were committed
        with session_maker() as session:
            assert session.get(SimulationMetadata, "outer") is not None
            assert session.get(SimulationMetadata, "inner") is not None

    def test_savepoint_rolls_back_independently(self, session_maker):
        """Savepoint rollback should not affect outer transaction."""
        with session_maker() as session, transaction(session):
            session.add(SimulationMetadata(key="outer_ok", value="value"))

            # Savepoint fails but outer transaction continues
            with pytest.raises(ValueError), savepoint(session):
                session.add(SimulationMetadata(key="inner_fail", value="value"))
                raise ValueError("savepoint error")

            # Add another record after failed savepoint
            session.add(SimulationMetadata(key="after_fail", value="value"))

        # Outer transaction records committed, savepoint record rolled back
        with session_maker() as session:
            assert session.get(SimulationMetadata, "outer_ok") is not None
            assert session.get(SimulationMetadata, "inner_fail") is None
            assert session.get(SimulationMetadata, "after_fail") is not None

    def test_nested_savepoints(self, session_maker):
        """Multiple nested savepoints should work correctly."""
        with session_maker() as session, transaction(session):
            session.add(SimulationMetadata(key="level0", value="value"))

            with savepoint(session):
                session.add(SimulationMetadata(key="level1", value="value"))

                with savepoint(session):
                    session.add(SimulationMetadata(key="level2", value="value"))

        # All levels committed
        with session_maker() as session:
            assert session.get(SimulationMetadata, "level0") is not None
            assert session.get(SimulationMetadata, "level1") is not None
            assert session.get(SimulationMetadata, "level2") is not None

    def test_inner_savepoint_failure_preserves_outer(self, session_maker):
        """Inner savepoint failure should preserve outer savepoint."""
        with session_maker() as session, transaction(session):  # noqa: SIM117
            with savepoint(session):
                session.add(SimulationMetadata(key="sp1", value="value"))

                with pytest.raises(ValueError), savepoint(session):
                    session.add(SimulationMetadata(key="sp2_fail", value="value"))
                    raise ValueError("inner failure")

                # Continue in outer savepoint
                session.add(SimulationMetadata(key="sp1_after", value="value"))

        # Outer savepoint committed, inner rolled back
        with session_maker() as session:
            assert session.get(SimulationMetadata, "sp1") is not None
            assert session.get(SimulationMetadata, "sp2_fail") is None
            assert session.get(SimulationMetadata, "sp1_after") is not None
