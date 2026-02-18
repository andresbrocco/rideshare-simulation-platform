"""Tests for MetricsCollector performance optimizations."""

import threading
import time
from collections import deque
from unittest.mock import Mock, patch

import pytest

import metrics.collector as collector_module
from metrics.collector import MetricsCollector, get_metrics_collector


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the global singleton before and after each test."""
    collector_module._metrics_collector = None
    yield
    collector_module._metrics_collector = None


class TrackingLock:
    """Thin wrapper around threading.Lock that counts acquire/release calls."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.acquire_count = 0

    def __enter__(self) -> bool:
        self.acquire_count += 1
        self._lock.acquire()
        return True

    def __exit__(self, *args: object) -> None:
        self._lock.release()


@pytest.mark.unit
class TestDequeCleanup:
    """Verify cleanup methods use popleft and preserve deque identity."""

    def test_cleanup_old_events_preserves_deque_identity(self) -> None:
        """_cleanup_old_events removes expired entries via popleft without
        allocating a new container -- the deque object identity must be stable."""
        mc = MetricsCollector(window_seconds=10)
        events_before = mc._events

        # Insert events: 5 expired, 3 current
        now = time.time()
        for i in range(5):
            mc._events.append((now - 20 + i, "old"))
        for i in range(3):
            mc._events.append((now + i, "new"))

        mc._cleanup_old_events(now)

        # Identity preserved (no list-slice allocation)
        assert mc._events is events_before
        assert len(mc._events) == 3
        assert all(event_type == "new" for _, event_type in mc._events)

    def test_cleanup_old_latency_preserves_deque_identity(self) -> None:
        """_cleanup_old_latency removes expired samples without replacing the deque."""
        mc = MetricsCollector(window_seconds=10)
        mc._latency_samples["kafka"]  # trigger defaultdict creation
        samples_before = mc._latency_samples["kafka"]

        now = time.time()
        for i in range(4):
            mc._latency_samples["kafka"].append((now - 20 + i, float(i)))
        mc._latency_samples["kafka"].append((now, 99.0))

        mc._cleanup_old_latency(now, "kafka")

        assert mc._latency_samples["kafka"] is samples_before
        assert len(mc._latency_samples["kafka"]) == 1
        assert mc._latency_samples["kafka"][0][1] == 99.0

    def test_cleanup_old_errors_preserves_deque_identity(self) -> None:
        """_cleanup_old_errors removes expired entries without replacing the deque."""
        mc = MetricsCollector(window_seconds=10)
        mc._errors["redis"]  # trigger defaultdict creation
        errors_before = mc._errors["redis"]

        now = time.time()
        for i in range(3):
            mc._errors["redis"].append((now - 20 + i, "timeout"))
        mc._errors["redis"].append((now, "connection"))

        mc._cleanup_old_errors(now, "redis")

        assert mc._errors["redis"] is errors_before
        assert len(mc._errors["redis"]) == 1
        assert mc._errors["redis"][0][1] == "connection"

    def test_events_and_samples_are_deque_instances(self) -> None:
        """Confirm all event/latency/error storage uses deque, not list."""
        mc = MetricsCollector()

        assert isinstance(mc._events, deque)

        mc.record_latency("osrm", 5.0)
        assert isinstance(mc._latency_samples["osrm"], deque)

        mc.record_error("kafka", "timeout")
        assert isinstance(mc._errors["kafka"], deque)


@pytest.mark.unit
class TestSingletonFastPath:
    """Verify get_metrics_collector() acquires the lock at most once."""

    def test_fast_path_skips_lock_after_initialization(self) -> None:
        """After the singleton is initialized, subsequent calls should not
        acquire _collector_lock."""
        tracker = TrackingLock()
        original_lock = collector_module._collector_lock
        collector_module._collector_lock = tracker  # type: ignore[assignment]
        try:
            # First call initializes the singleton (acquires lock once)
            instance = get_metrics_collector()
            assert tracker.acquire_count == 1

            # Subsequent calls should take the fast path -- no more acquires
            for _ in range(10):
                result = get_metrics_collector()
                assert result is instance

            assert tracker.acquire_count == 1
        finally:
            collector_module._collector_lock = original_lock

    def test_first_call_acquires_lock(self) -> None:
        """The very first call must acquire the lock to create the instance."""
        assert collector_module._metrics_collector is None

        tracker = TrackingLock()
        original_lock = collector_module._collector_lock
        collector_module._collector_lock = tracker  # type: ignore[assignment]
        try:
            instance = get_metrics_collector()
            assert tracker.acquire_count == 1
            assert instance is collector_module._metrics_collector
        finally:
            collector_module._collector_lock = original_lock


@pytest.mark.unit
class TestEventEmitterCachedReference:
    """Verify EventEmitter caches the metrics collector at construction."""

    def test_cached_reference_matches_singleton(self) -> None:
        """EventEmitter._metrics_collector must be the same object as the
        global singleton returned by get_metrics_collector()."""
        from agents.event_emitter import EventEmitter

        emitter = EventEmitter(kafka_producer=Mock())
        singleton = get_metrics_collector()

        assert emitter._metrics_collector is singleton

    def test_emit_event_uses_cached_reference(self) -> None:
        """_emit_event should call record_event on the cached collector,
        not call get_metrics_collector() again."""
        from agents.event_emitter import EventEmitter

        emitter = EventEmitter(kafka_producer=None)  # no-op Kafka

        with patch("agents.event_emitter.get_metrics_collector") as mock_getter:
            emitter._emit_event(
                event=Mock(),
                kafka_topic="trips",
                partition_key="trip1",
            )
            # get_metrics_collector should NOT be called during _emit_event
            mock_getter.assert_not_called()
