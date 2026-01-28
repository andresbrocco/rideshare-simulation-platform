"""Polling and timeout utilities for integration tests."""

import time
from typing import Callable, Any, Optional


class TimeoutError(Exception):
    """Raised when polling exceeds timeout."""

    pass


def wait_for_condition(
    condition: Callable[[], bool],
    timeout_seconds: int = 60,
    poll_interval: float = 1.0,
    max_retries: Optional[int] = None,
    description: str = "condition",
) -> None:
    """Wait for a condition to become true.

    Args:
        condition: Callable that returns True when condition is met
        timeout_seconds: Maximum time to wait (default 60s)
        poll_interval: Base polling interval in seconds (default 1s)
        max_retries: Maximum number of retries (overrides timeout if set)
        description: Human-readable description for error messages

    Raises:
        TimeoutError: If condition not met within timeout
    """
    start_time = time.time()
    attempt = 0

    while True:
        try:
            if condition():
                return
        except Exception:
            # Log exception but continue polling
            pass

        attempt += 1
        elapsed = time.time() - start_time

        # Check timeout
        if max_retries is not None and attempt >= max_retries:
            raise TimeoutError(f"Condition '{description}' not met after {attempt} attempts")
        elif elapsed >= timeout_seconds:
            raise TimeoutError(f"Condition '{description}' not met after {elapsed:.1f} seconds")

        # Sleep with exponential backoff (capped at 10s)
        sleep_time = min(poll_interval * (2 ** (attempt - 1)), 10.0)
        time.sleep(sleep_time)


def wait_with_exponential_backoff(
    callback: Callable[[], Any],
    max_attempts: int = 10,
    initial_interval: float = 1.0,
    max_interval: float = 10.0,
    description: str = "operation",
) -> Any:
    """Execute callback with exponential backoff on failure.

    Args:
        callback: Function to execute
        max_attempts: Maximum number of attempts
        initial_interval: Initial wait interval in seconds
        max_interval: Maximum wait interval (cap for exponential growth)
        description: Description for error messages

    Returns:
        Result from successful callback execution

    Raises:
        Exception: Last exception if all attempts fail
    """
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            return callback()
        except Exception as e:
            last_exception = e
            if attempt == max_attempts:
                break

            # Calculate backoff time
            wait_time = min(initial_interval * (2 ** (attempt - 1)), max_interval)
            time.sleep(wait_time)

    raise TimeoutError(
        f"Operation '{description}' failed after {max_attempts} attempts. "
        f"Last error: {last_exception}"
    )


def poll_until_records_present(
    query_callback: Callable[[], int],
    expected_count: int,
    timeout_seconds: int = 60,
    poll_interval: float = 2.0,
    description: str = "records",
) -> None:
    """Poll until expected number of records appear.

    Used by Bronze ingestion waiting to poll Delta tables via Thrift Server.

    Args:
        query_callback: Function that returns current record count
        expected_count: Expected number of records
        timeout_seconds: Maximum wait time
        poll_interval: Base polling interval
        description: Description for error messages

    Raises:
        TimeoutError: If expected count not reached within timeout
    """

    def condition() -> bool:
        current_count = query_callback()
        return current_count >= expected_count

    wait_for_condition(
        condition=condition,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        description=f"{description} (expected: {expected_count})",
    )
