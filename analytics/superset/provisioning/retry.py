"""Retry mechanism with exponential backoff and jitter."""

import logging
import random
import time
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from provisioning.exceptions import (
    PermanentError,
    RateLimitError,
    TransientError,
)

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def calculate_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter_factor: float = 0.5,
) -> float:
    """Calculate backoff delay with exponential increase and jitter.

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds
        jitter_factor: Random jitter as fraction of delay (0.0-1.0)

    Returns:
        Delay in seconds with jitter applied
    """
    # Exponential backoff: base_delay * 2^attempt
    delay = base_delay * (2**attempt)

    # Cap at max_delay
    delay = min(delay, max_delay)

    # Add jitter: random value between -jitter_factor*delay and +jitter_factor*delay
    jitter = delay * jitter_factor * (2 * random.random() - 1)
    delay = max(0.0, delay + jitter)

    return delay


def retry_on_transient_error(
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter_factor: float = 0.5,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator that retries a function on TransientError.

    Fails immediately on PermanentError.

    Args:
        max_attempts: Maximum number of attempts (including first try)
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay cap in seconds
        jitter_factor: Random jitter as fraction of delay

    Returns:
        Decorated function with retry behavior
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: TransientError | None = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except PermanentError:
                    # Don't retry permanent errors
                    raise
                except TransientError as e:
                    last_exception = e

                    if attempt + 1 >= max_attempts:
                        # Last attempt failed
                        break

                    # Calculate delay, respecting rate limit headers
                    if isinstance(e, RateLimitError) and e.retry_after:
                        delay = float(e.retry_after)
                    else:
                        delay = calculate_backoff(
                            attempt,
                            base_delay=base_delay,
                            max_delay=max_delay,
                            jitter_factor=jitter_factor,
                        )

                    logger.warning(
                        "Transient error on attempt %d/%d for %s: %s. " "Retrying in %.2fs...",
                        attempt + 1,
                        max_attempts,
                        func.__name__,
                        str(e),
                        delay,
                    )
                    time.sleep(delay)

            # All retries exhausted
            assert last_exception is not None  # noqa: S101
            raise last_exception

        return wrapper

    return decorator
