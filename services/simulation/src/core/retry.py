"""Retry utilities with exponential backoff."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeVar

from .exceptions import TransientError

T = TypeVar("T")
logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 0.5
    multiplier: float = 2.0
    max_delay: float = 30.0
    retryable_exceptions: tuple[type[Exception], ...] = field(
        default_factory=lambda: (TransientError,)
    )


async def with_retry(
    operation: Callable[[], Awaitable[T]],
    config: RetryConfig | None = None,
    operation_name: str = "operation",
    on_retry: Callable[[Exception, int], None] | None = None,
) -> T:
    """Execute async operation with exponential backoff retry."""
    if config is None:
        config = RetryConfig()

    last_exception: Exception | None = None

    for attempt in range(config.max_attempts):
        try:
            return await operation()
        except config.retryable_exceptions as e:
            last_exception = e
            if attempt == config.max_attempts - 1:
                logger.error(f"{operation_name} failed after {config.max_attempts} attempts: {e}")
                raise

            delay = min(
                config.base_delay * (config.multiplier**attempt),
                config.max_delay,
            )
            logger.warning(
                f"{operation_name} failed (attempt {attempt + 1}/{config.max_attempts}), "
                f"retrying in {delay:.1f}s: {e}"
            )

            if on_retry:
                on_retry(e, attempt)

            await asyncio.sleep(delay)

    raise last_exception  # type: ignore


def with_retry_sync(
    operation: Callable[[], T],
    config: RetryConfig | None = None,
    operation_name: str = "operation",
) -> T:
    """Synchronous version of with_retry."""
    if config is None:
        config = RetryConfig()

    last_exception: Exception | None = None

    for attempt in range(config.max_attempts):
        try:
            return operation()
        except config.retryable_exceptions as e:
            last_exception = e
            if attempt == config.max_attempts - 1:
                raise

            delay = min(
                config.base_delay * (config.multiplier**attempt),
                config.max_delay,
            )
            logger.warning(
                f"{operation_name} failed (attempt {attempt + 1}), retrying in {delay:.1f}s"
            )
            time.sleep(delay)

    raise last_exception  # type: ignore
