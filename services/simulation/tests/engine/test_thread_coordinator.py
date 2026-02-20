"""Tests for ThreadCoordinator - thread-safe command queue for FastAPI/SimPy communication."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from src.engine.thread_coordinator import (
    Command,
    CommandTimeoutError,
    CommandType,
    NoHandlerRegisteredError,
    ShutdownError,
    ThreadCoordinator,
)


@pytest.mark.unit
@pytest.mark.slow
class TestCommandType:
    """Tests for CommandType enum values."""

    def test_command_type_has_pause(self):
        """CommandType has PAUSE value."""
        assert CommandType.PAUSE.value == "pause"

    def test_command_type_has_resume(self):
        """CommandType has RESUME value."""
        assert CommandType.RESUME.value == "resume"

    def test_command_type_has_reset(self):
        """CommandType has RESET value."""
        assert CommandType.RESET.value == "reset"

    def test_command_type_has_set_speed(self):
        """CommandType has SET_SPEED value."""
        assert CommandType.SET_SPEED.value == "set_speed"

    def test_command_type_has_add_drivers(self):
        """CommandType has ADD_DRIVERS value."""
        assert CommandType.ADD_DRIVERS.value == "add_drivers"

    def test_command_type_has_add_riders(self):
        """CommandType has ADD_RIDERS value."""
        assert CommandType.ADD_RIDERS.value == "add_riders"

    def test_command_type_has_add_puppet(self):
        """CommandType has ADD_PUPPET value."""
        assert CommandType.ADD_PUPPET.value == "add_puppet"

    def test_command_type_has_puppet_action(self):
        """CommandType has PUPPET_ACTION value."""
        assert CommandType.PUPPET_ACTION.value == "puppet_action"

    def test_command_type_has_get_snapshot(self):
        """CommandType has GET_SNAPSHOT value."""
        assert CommandType.GET_SNAPSHOT.value == "get_snapshot"

    def test_command_type_has_shutdown(self):
        """CommandType has SHUTDOWN value."""
        assert CommandType.SHUTDOWN.value == "shutdown"


@pytest.mark.unit
@pytest.mark.slow
class TestCommandDataclass:
    """Tests for Command dataclass structure."""

    def test_command_has_required_fields(self):
        """Command has all required fields."""
        event = threading.Event()
        cmd = Command(
            type=CommandType.PAUSE,
            payload={},
            response_event=event,
            result=None,
            error=None,
        )
        assert cmd.type == CommandType.PAUSE
        assert cmd.payload == {}
        assert cmd.response_event is event
        assert cmd.result is None
        assert cmd.error is None

    def test_command_can_store_result(self):
        """Command can store result after processing."""
        event = threading.Event()
        cmd = Command(
            type=CommandType.GET_SNAPSHOT,
            payload={},
            response_event=event,
            result=None,
            error=None,
        )
        cmd.result = {"drivers": [], "riders": []}
        assert cmd.result == {"drivers": [], "riders": []}

    def test_command_can_store_error(self):
        """Command can store error after processing failure."""
        event = threading.Event()
        cmd = Command(
            type=CommandType.PAUSE,
            payload={},
            response_event=event,
            result=None,
            error=None,
        )
        cmd.error = ValueError("Something went wrong")
        assert isinstance(cmd.error, ValueError)


@pytest.mark.unit
@pytest.mark.slow
class TestThreadCoordinatorInit:
    """Tests for ThreadCoordinator initialization."""

    def test_init_with_default_timeout(self):
        """Initializes with default 30s timeout."""
        coordinator = ThreadCoordinator()
        assert coordinator._timeout == 30.0

    def test_init_with_custom_timeout(self):
        """Initializes with custom timeout."""
        coordinator = ThreadCoordinator(timeout=10.0)
        assert coordinator._timeout == 10.0

    def test_init_not_shutdown(self):
        """New coordinator is not in shutdown state."""
        coordinator = ThreadCoordinator()
        assert coordinator.is_shutdown is False


@pytest.mark.unit
@pytest.mark.slow
class TestHandlerRegistration:
    """Tests for handler registration."""

    def test_register_handler_stores_handler(self):
        """Registered handler is stored and callable."""
        coordinator = ThreadCoordinator()
        handler_called = []

        def pause_handler(payload):
            handler_called.append(True)
            return "paused"

        coordinator.register_handler(CommandType.PAUSE, pause_handler)
        assert CommandType.PAUSE in coordinator._handlers

    def test_register_multiple_handlers(self):
        """Can register handlers for different command types."""
        coordinator = ThreadCoordinator()

        coordinator.register_handler(CommandType.PAUSE, lambda p: "paused")
        coordinator.register_handler(CommandType.RESUME, lambda p: "resumed")
        coordinator.register_handler(CommandType.SET_SPEED, lambda p: p["speed"])

        assert CommandType.PAUSE in coordinator._handlers
        assert CommandType.RESUME in coordinator._handlers
        assert CommandType.SET_SPEED in coordinator._handlers

    def test_register_handler_replaces_existing(self):
        """Registering same command type replaces existing handler."""
        coordinator = ThreadCoordinator()

        coordinator.register_handler(CommandType.PAUSE, lambda p: "old")
        coordinator.register_handler(CommandType.PAUSE, lambda p: "new")

        # Only one handler should exist
        assert len([ct for ct in coordinator._handlers if ct == CommandType.PAUSE]) == 1


@pytest.mark.unit
@pytest.mark.slow
class TestSendCommand:
    """Tests for send_command method."""

    def test_send_command_returns_result(self):
        """send_command returns handler result."""
        coordinator = ThreadCoordinator()
        coordinator.register_handler(CommandType.PAUSE, lambda p: "simulation_paused")

        # Process in background thread
        def process_commands():
            time.sleep(0.05)
            coordinator.process_pending_commands()

        thread = threading.Thread(target=process_commands)
        thread.start()

        result = coordinator.send_command(CommandType.PAUSE)
        thread.join()

        assert result == "simulation_paused"

    def test_send_command_with_payload(self):
        """send_command passes payload to handler."""
        coordinator = ThreadCoordinator()
        coordinator.register_handler(CommandType.SET_SPEED, lambda p: p["multiplier"] * 2)

        def process_commands():
            time.sleep(0.05)
            coordinator.process_pending_commands()

        thread = threading.Thread(target=process_commands)
        thread.start()

        result = coordinator.send_command(CommandType.SET_SPEED, {"multiplier": 5})
        thread.join()

        assert result == 10

    def test_send_command_timeout_raises_error(self):
        """send_command raises CommandTimeoutError on timeout."""
        coordinator = ThreadCoordinator(timeout=0.1)
        coordinator.register_handler(CommandType.PAUSE, lambda p: "ok")

        # Don't process commands - let it timeout
        with pytest.raises(CommandTimeoutError):
            coordinator.send_command(CommandType.PAUSE, timeout=0.1)

    def test_send_command_custom_timeout(self):
        """send_command respects custom timeout parameter."""
        coordinator = ThreadCoordinator(timeout=30.0)
        coordinator.register_handler(CommandType.PAUSE, lambda p: "ok")

        with pytest.raises(CommandTimeoutError):
            coordinator.send_command(CommandType.PAUSE, timeout=0.05)

    def test_send_command_no_handler_raises_error(self):
        """send_command raises NoHandlerRegisteredError when no handler exists."""
        coordinator = ThreadCoordinator()

        def process_commands():
            time.sleep(0.05)
            coordinator.process_pending_commands()

        thread = threading.Thread(target=process_commands)
        thread.start()

        with pytest.raises(NoHandlerRegisteredError):
            coordinator.send_command(CommandType.PAUSE)

        thread.join()


@pytest.mark.unit
@pytest.mark.slow
class TestProcessPendingCommands:
    """Tests for process_pending_commands method."""

    def test_process_returns_count_of_processed_commands(self):
        """process_pending_commands returns number of commands processed."""
        coordinator = ThreadCoordinator()
        coordinator.register_handler(CommandType.PAUSE, lambda p: "ok")
        coordinator.register_handler(CommandType.RESUME, lambda p: "ok")

        # Queue commands in background threads
        threads = []
        for cmd_type in [CommandType.PAUSE, CommandType.RESUME]:
            t = threading.Thread(
                target=coordinator.send_command,
                args=(cmd_type,),
            )
            t.start()
            threads.append(t)

        time.sleep(0.1)
        count = coordinator.process_pending_commands()

        for t in threads:
            t.join()

        assert count == 2

    def test_process_returns_zero_when_queue_empty(self):
        """process_pending_commands returns 0 when no commands pending."""
        coordinator = ThreadCoordinator()
        count = coordinator.process_pending_commands()
        assert count == 0

    def test_process_executes_handler(self):
        """process_pending_commands executes registered handler."""
        coordinator = ThreadCoordinator()
        handler_calls = []

        def tracking_handler(payload):
            handler_calls.append(payload)
            return "done"

        coordinator.register_handler(CommandType.ADD_DRIVERS, tracking_handler)

        def send():
            coordinator.send_command(CommandType.ADD_DRIVERS, {"count": 5})

        thread = threading.Thread(target=send)
        thread.start()

        time.sleep(0.05)
        coordinator.process_pending_commands()
        thread.join()

        assert len(handler_calls) == 1
        assert handler_calls[0] == {"count": 5}


@pytest.mark.unit
@pytest.mark.slow
class TestErrorPropagation:
    """Tests for error propagation from handler to caller."""

    def test_handler_exception_propagates_to_caller(self):
        """Exception in handler is propagated to send_command caller."""
        coordinator = ThreadCoordinator()

        def failing_handler(payload):
            raise ValueError("Handler failed intentionally")

        coordinator.register_handler(CommandType.RESET, failing_handler)

        def process_commands():
            time.sleep(0.05)
            coordinator.process_pending_commands()

        thread = threading.Thread(target=process_commands)
        thread.start()

        with pytest.raises(ValueError, match="Handler failed intentionally"):
            coordinator.send_command(CommandType.RESET)

        thread.join()

    def test_handler_runtime_error_propagates(self):
        """RuntimeError in handler propagates correctly."""
        coordinator = ThreadCoordinator()

        def failing_handler(payload):
            raise RuntimeError("Critical failure")

        coordinator.register_handler(CommandType.PAUSE, failing_handler)

        def process_commands():
            time.sleep(0.05)
            coordinator.process_pending_commands()

        thread = threading.Thread(target=process_commands)
        thread.start()

        with pytest.raises(RuntimeError, match="Critical failure"):
            coordinator.send_command(CommandType.PAUSE)

        thread.join()


@pytest.mark.unit
@pytest.mark.slow
class TestShutdownBehavior:
    """Tests for shutdown behavior."""

    def test_shutdown_sets_is_shutdown_true(self):
        """shutdown() sets is_shutdown to True."""
        coordinator = ThreadCoordinator()
        assert coordinator.is_shutdown is False
        coordinator.shutdown()
        assert coordinator.is_shutdown is True

    def test_shutdown_rejects_new_commands(self):
        """After shutdown, send_command raises ShutdownError."""
        coordinator = ThreadCoordinator()
        coordinator.register_handler(CommandType.PAUSE, lambda p: "ok")
        coordinator.shutdown()

        with pytest.raises(ShutdownError):
            coordinator.send_command(CommandType.PAUSE)

    def test_shutdown_allows_pending_commands_to_complete(self):
        """Commands queued before shutdown can still be processed."""
        coordinator = ThreadCoordinator()
        results = []

        def slow_handler(payload):
            time.sleep(0.1)
            return "completed"

        coordinator.register_handler(CommandType.PAUSE, slow_handler)

        def send_and_collect():
            result = coordinator.send_command(CommandType.PAUSE)
            results.append(result)

        thread = threading.Thread(target=send_and_collect)
        thread.start()

        time.sleep(0.02)
        coordinator.shutdown()
        coordinator.process_pending_commands()
        thread.join()

        assert results == ["completed"]


@pytest.mark.unit
@pytest.mark.slow
class TestConcurrentCommands:
    """Tests for concurrent command processing."""

    def test_ten_concurrent_commands_all_processed(self):
        """10+ concurrent commands are all processed correctly."""
        coordinator = ThreadCoordinator()
        results = []
        lock = threading.Lock()

        def counter_handler(payload):
            return payload.get("value", 0) * 2

        coordinator.register_handler(CommandType.SET_SPEED, counter_handler)

        def process_loop():
            while True:
                coordinator.process_pending_commands()
                if coordinator.is_shutdown:
                    break
                time.sleep(0.01)

        processor = threading.Thread(target=process_loop)
        processor.start()

        def send_command(value):
            result = coordinator.send_command(CommandType.SET_SPEED, {"value": value})
            with lock:
                results.append(result)

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(send_command, i) for i in range(15)]
            for future in as_completed(futures):
                future.result()

        coordinator.shutdown()
        processor.join()

        assert len(results) == 15
        expected = {i * 2 for i in range(15)}
        assert set(results) == expected

    def test_concurrent_commands_no_race_conditions(self):
        """Concurrent commands don't cause race conditions in results."""
        coordinator = ThreadCoordinator()
        shared_state = {"counter": 0}
        lock = threading.Lock()

        def increment_handler(payload):
            with lock:
                shared_state["counter"] += 1
            return shared_state["counter"]

        coordinator.register_handler(CommandType.ADD_DRIVERS, increment_handler)

        def process_loop():
            while not coordinator.is_shutdown:
                coordinator.process_pending_commands()
                time.sleep(0.005)

        processor = threading.Thread(target=process_loop)
        processor.start()

        results = []

        def send_and_collect():
            result = coordinator.send_command(CommandType.ADD_DRIVERS, {})
            results.append(result)

        threads = [threading.Thread(target=send_and_collect) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        coordinator.shutdown()
        processor.join()

        # All results should be unique (no race condition duplicates)
        assert len(results) == 20
        assert len(set(results)) == 20

    def test_commands_processed_fifo(self):
        """Commands are processed in FIFO order."""
        coordinator = ThreadCoordinator()
        processing_order = []
        processing_lock = threading.Lock()

        def tracking_handler(payload):
            with processing_lock:
                processing_order.append(payload["seq"])
            return payload["seq"]

        coordinator.register_handler(CommandType.PUPPET_ACTION, tracking_handler)

        # Queue commands sequentially
        events = []
        for i in range(10):
            event = threading.Event()
            cmd = Command(
                type=CommandType.PUPPET_ACTION,
                payload={"seq": i},
                response_event=event,
                result=None,
                error=None,
            )
            coordinator._queue.put(cmd)
            events.append((event, cmd))

        # Process all at once
        coordinator.process_pending_commands()

        # Verify FIFO order
        assert processing_order == list(range(10))


@pytest.mark.unit
@pytest.mark.slow
class TestCommandQueueIntegration:
    """Integration tests for full command queue lifecycle."""

    def test_multiple_command_types_concurrent(self):
        """Different command types can be processed concurrently."""
        coordinator = ThreadCoordinator()
        results = {}
        lock = threading.Lock()

        coordinator.register_handler(CommandType.PAUSE, lambda p: "paused")
        coordinator.register_handler(CommandType.RESUME, lambda p: "resumed")
        coordinator.register_handler(CommandType.SET_SPEED, lambda p: p["speed"])
        coordinator.register_handler(CommandType.GET_SNAPSHOT, lambda p: {"state": "ok"})

        def process_loop():
            while not coordinator.is_shutdown:
                coordinator.process_pending_commands()
                time.sleep(0.01)

        processor = threading.Thread(target=process_loop)
        processor.start()

        def send_and_store(cmd_type, payload, key):
            result = coordinator.send_command(cmd_type, payload)
            with lock:
                results[key] = result

        threads = [
            threading.Thread(target=send_and_store, args=(CommandType.PAUSE, None, "pause")),
            threading.Thread(target=send_and_store, args=(CommandType.RESUME, None, "resume")),
            threading.Thread(
                target=send_and_store,
                args=(CommandType.SET_SPEED, {"speed": 2.0}, "speed"),
            ),
            threading.Thread(
                target=send_and_store, args=(CommandType.GET_SNAPSHOT, None, "snapshot")
            ),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        coordinator.shutdown()
        processor.join()

        assert results["pause"] == "paused"
        assert results["resume"] == "resumed"
        assert results["speed"] == 2.0
        assert results["snapshot"] == {"state": "ok"}

    def test_handler_with_complex_return_value(self):
        """Handler can return complex data structures."""
        coordinator = ThreadCoordinator()

        def snapshot_handler(payload):
            return {
                "drivers": [{"id": "d1", "status": "available"}],
                "riders": [{"id": "r1", "status": "requesting"}],
                "trips": [],
                "metadata": {"count": 2, "timestamp": "2025-01-01T00:00:00Z"},
            }

        coordinator.register_handler(CommandType.GET_SNAPSHOT, snapshot_handler)

        def process_commands():
            time.sleep(0.05)
            coordinator.process_pending_commands()

        thread = threading.Thread(target=process_commands)
        thread.start()

        result = coordinator.send_command(CommandType.GET_SNAPSHOT)
        thread.join()

        assert "drivers" in result
        assert "riders" in result
        assert result["metadata"]["count"] == 2
