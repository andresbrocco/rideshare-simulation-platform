import asyncio
import concurrent.futures
import threading
import time
from unittest.mock import patch

import pytest

from src.utils.async_helpers import run_coroutine_safe


async def sample_coro():
    """Simple coroutine for testing."""
    return "success"


async def slow_coro():
    """Coroutine that takes some time."""
    await asyncio.sleep(0.1)
    return "slow_success"


@pytest.fixture
def running_loop_in_thread():
    """Create an event loop running in a separate thread."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()

    # Wait for loop to be running
    while not loop.is_running():
        time.sleep(0.01)

    yield loop

    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=1)
    loop.close()


class TestRunCoroutineSafe:
    def test_run_coroutine_safe_with_valid_loop(self, running_loop_in_thread):
        """When provided a running event loop, should schedule via run_coroutine_threadsafe."""
        future = run_coroutine_safe(
            sample_coro(), main_event_loop=running_loop_in_thread
        )

        assert future is not None
        assert isinstance(future, concurrent.futures.Future)
        result = future.result(timeout=2)
        assert result == "success"

    def test_run_coroutine_safe_with_none_loop(self, caplog):
        """When main_event_loop=None and fallback_sync=False, should log warning and return None."""
        coro = sample_coro()

        result = run_coroutine_safe(coro, main_event_loop=None, fallback_sync=False)

        assert result is None
        assert (
            "no event loop" in caplog.text.lower()
            or "event loop" in caplog.text.lower()
        )

    def test_run_coroutine_safe_with_non_coroutine(
        self, caplog, running_loop_in_thread
    ):
        """When called with a non-coroutine, should log warning and return None."""
        not_a_coro = "this is a string"

        result = run_coroutine_safe(not_a_coro, main_event_loop=running_loop_in_thread)

        assert result is None
        assert "coroutine" in caplog.text.lower()

    def test_run_coroutine_safe_fallback_sync(self):
        """When fallback_sync=True and no event loop, should run synchronously."""
        coro = sample_coro()

        result = run_coroutine_safe(coro, main_event_loop=None, fallback_sync=True)

        # When running synchronously, we expect the result directly, not a Future
        # The function may return the result or wrap it
        assert result == "success" or (
            hasattr(result, "result") and result.result() == "success"
        )

    def test_run_coroutine_safe_from_simpy_thread(self, running_loop_in_thread):
        """Simulate calling from a background thread (like SimPy would)."""
        results = []
        errors = []

        def simpy_thread_work():
            try:
                future = run_coroutine_safe(
                    slow_coro(), main_event_loop=running_loop_in_thread
                )
                if future:
                    results.append(future.result(timeout=2))
            except Exception as e:
                errors.append(e)

        # Run from a different thread (simulating SimPy background thread)
        simpy_thread = threading.Thread(target=simpy_thread_work)
        simpy_thread.start()
        simpy_thread.join(timeout=3)

        assert not errors, f"Errors occurred: {errors}"
        assert results == ["slow_success"]

    def test_run_coroutine_safe_with_closed_loop(self, caplog):
        """When provided a closed event loop, should handle gracefully."""
        loop = asyncio.new_event_loop()
        loop.close()

        result = run_coroutine_safe(
            sample_coro(), main_event_loop=loop, fallback_sync=False
        )

        assert result is None
