"""Transaction utilities for explicit transaction boundaries.

This module provides context managers for managing database transactions
with automatic commit/rollback semantics to prevent partial state updates.
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.orm import Session


@contextmanager
def transaction(session: Session) -> Generator[Session]:
    """Context manager for explicit transaction boundaries.

    Commits on successful completion, rolls back on any exception.
    Use this when you need to ensure multiple operations succeed or fail together.

    Example:
        with transaction(session):
            trip_repo.update_state("trip_1", TripState.DRIVER_ASSIGNED, driver_id="d1")
            driver_repo.update_status("d1", "busy")
        # Automatic commit if no exception, rollback otherwise

    Args:
        session: SQLAlchemy session to manage

    Yields:
        The same session for use within the context

    Raises:
        Any exception raised within the context (after rollback)
    """
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise


@contextmanager
def savepoint(session: Session) -> Generator[Session]:
    """Context manager for nested transaction (savepoint).

    Creates a savepoint within an existing transaction. On exception,
    rolls back only to the savepoint without affecting the outer transaction.
    Use this for operations that should be atomic but are part of a larger transaction.

    Example:
        with transaction(session):
            # Outer transaction
            trip_repo.create(...)

            with savepoint(session):
                # Nested savepoint - can fail independently
                driver_repo.batch_upsert_with_state(drivers)

            # Continue outer transaction even if savepoint rolled back

    Args:
        session: SQLAlchemy session to create savepoint on

    Yields:
        The same session for use within the context

    Raises:
        Any exception raised within the context (after savepoint rollback)
    """
    nested = session.begin_nested()
    try:
        yield session
        nested.commit()
    except Exception:
        nested.rollback()
        raise
