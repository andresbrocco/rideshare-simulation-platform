"""Thread coordinator for FastAPI/SimPy communication.

This module provides thread-safe command queue communication between the FastAPI
main thread and the SimPy background simulation thread.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from queue import Empty, Queue
from typing import Any


class CommandType(str, Enum):
    """Types of commands that can be sent to the simulation engine."""

    PAUSE = "pause"
    RESUME = "resume"
    RESET = "reset"
    SET_SPEED = "set_speed"
    ADD_DRIVERS = "add_drivers"
    ADD_RIDERS = "add_riders"
    ADD_PUPPET = "add_puppet"
    PUPPET_ACTION = "puppet_action"
    GET_SNAPSHOT = "get_snapshot"
    SHUTDOWN = "shutdown"


@dataclass
class Command:
    """A command to be processed by the simulation engine."""

    type: CommandType
    payload: dict[str, Any]
    response_event: threading.Event
    result: Any
    error: Exception | None


class CommandTimeoutError(Exception):
    """Raised when a command times out waiting for response."""

    pass


class NoHandlerRegisteredError(Exception):
    """Raised when no handler is registered for a command type."""

    pass


class ShutdownError(Exception):
    """Raised when attempting to send commands after shutdown."""

    pass


class ThreadCoordinator:
    """Coordinates thread-safe command passing between threads."""

    def __init__(self, timeout: float = 30.0) -> None:
        """Initialize the thread coordinator."""
        self._timeout = timeout
        self._queue: Queue[Command] = Queue()
        self._handlers: dict[CommandType, Callable[[dict[str, Any]], Any]] = {}
        self._shutdown_event = threading.Event()

    def register_handler(
        self, command_type: CommandType, handler: Callable[[dict[str, Any]], Any]
    ) -> None:
        """Register a handler for a command type."""
        self._handlers[command_type] = handler

    def send_command(
        self,
        command_type: CommandType,
        payload: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Send a command and wait for response."""
        if self._shutdown_event.is_set():
            raise ShutdownError("Coordinator has been shut down")

        response_event = threading.Event()
        cmd = Command(
            type=command_type,
            payload=payload or {},
            response_event=response_event,
            result=None,
            error=None,
        )
        self._queue.put(cmd)

        effective_timeout = timeout if timeout is not None else self._timeout
        if not response_event.wait(timeout=effective_timeout):
            raise CommandTimeoutError(f"Command {command_type} timed out")

        if cmd.error is not None:
            raise cmd.error

        return cmd.result

    def process_pending_commands(self) -> int:
        """Process all pending commands in the queue. Returns count processed."""
        count = 0
        while True:
            try:
                cmd = self._queue.get_nowait()
            except Empty:
                break

            handler = self._handlers.get(cmd.type)
            if handler is None:
                cmd.error = NoHandlerRegisteredError(f"No handler registered for {cmd.type}")
            else:
                try:
                    cmd.result = handler(cmd.payload)
                except Exception as e:
                    cmd.error = e

            cmd.response_event.set()
            count += 1

        return count

    def shutdown(self) -> None:
        """Shutdown the coordinator, rejecting new commands."""
        self._shutdown_event.set()

    @property
    def is_shutdown(self) -> bool:
        """Check if the coordinator has been shut down."""
        return self._shutdown_event.is_set()
