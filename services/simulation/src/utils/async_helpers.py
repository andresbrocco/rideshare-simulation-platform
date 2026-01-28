import asyncio
import concurrent.futures
import inspect
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)


def run_coroutine_safe(
    coro: Coroutine[Any, Any, Any],
    main_event_loop: asyncio.AbstractEventLoop | None = None,
    fallback_sync: bool = False,
) -> concurrent.futures.Future[Any] | Any | None:
    """Schedule a coroutine to run on an event loop from any thread."""
    if not inspect.iscoroutine(coro):
        logger.warning("Expected a coroutine, got %s", type(coro).__name__)
        return None

    if main_event_loop is not None:
        if main_event_loop.is_closed():
            logger.warning("Event loop is closed, cannot schedule coroutine")
            coro.close()
            return None

        if main_event_loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, main_event_loop)

    if fallback_sync:
        try:
            result = asyncio.run(coro)
            return result
        except Exception as e:
            logger.error("Failed to run coroutine synchronously: %s", e)
            return None

    logger.warning("No event loop available to run coroutine")
    coro.close()
    return None
