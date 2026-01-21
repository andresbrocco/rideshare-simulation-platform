# Threading Model

This document describes the thread coordination model used for communication between FastAPI and the SimPy simulation engine.

## Thread Ownership

```
┌─────────────────────────────────────────────────────────────────┐
│                        MAIN THREAD                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    FastAPI + asyncio                     │    │
│  │  - HTTP request handlers                                 │    │
│  │  - WebSocket connections                                 │    │
│  │  - API endpoints (/simulation/*, /drivers/*, etc.)      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              │ send_command()                    │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              ThreadCoordinator (Queue)                   │    │
│  │  - Thread-safe command queue                             │    │
│  │  - Response synchronization via threading.Event          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
└──────────────────────────────│───────────────────────────────────┘
                               │ process_pending_commands()
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SIMULATION THREAD                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                 SimPy Environment                        │    │
│  │  - SimulationEngine.step() loop                          │    │
│  │  - Agent processes (drivers, riders)                     │    │
│  │  - Trip execution                                        │    │
│  │  - Surge pricing updates                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Command Types

| Command | Purpose | Payload |
|---------|---------|---------|
| `PAUSE` | Initiate two-phase pause | `{}` |
| `RESUME` | Resume from paused state | `{}` |
| `RESET` | Reset simulation to clean state | `{}` |
| `SET_SPEED` | Change simulation speed multiplier | `{"speed": int}` |
| `ADD_DRIVERS` | Spawn new driver agents | `{"count": int, "zone_id": str}` |
| `ADD_RIDERS` | Spawn new rider agents | `{"count": int, "zone_id": str}` |
| `ADD_PUPPET` | Add test puppet agent | `{"puppet_type": str, ...}` |
| `PUPPET_ACTION` | Control test puppet | `{"puppet_id": str, "action": str}` |
| `GET_SNAPSHOT` | Request immutable state snapshot | `{}` |
| `SHUTDOWN` | Graceful coordinator shutdown | `{}` |

## Snapshot Pattern for Reads

All read operations from the API thread use immutable snapshots:

```python
# API handler (main thread)
async def get_simulation_status():
    snapshot = coordinator.send_command(CommandType.GET_SNAPSHOT)
    return snapshot.to_dict()

# SimPy thread handler
def handle_get_snapshot(payload):
    return SimulationSnapshot(
        timestamp=datetime.now(UTC),
        simulation_time=env.now,
        is_running=engine.state == SimulationState.RUNNING,
        drivers=tuple(AgentSnapshot(...) for d in drivers),
        ...
    )
```

Snapshot classes are frozen dataclasses:
- `AgentSnapshot` - Driver/rider state
- `TripSnapshot` - Trip state
- `SimulationSnapshot` - Full simulation state

## Command Flow

1. API handler calls `coordinator.send_command(CommandType.X, payload)`
2. Command is placed in thread-safe queue with a unique ID
3. API thread blocks on `response_event.wait(timeout)`
4. SimPy thread calls `coordinator.process_pending_commands()` each step
5. Handler executes, result stored in command object
6. `response_event.set()` unblocks API thread
7. Result returned to API handler

## Error Handling

- `CommandTimeoutError` - Command did not complete within timeout
- `NoHandlerRegisteredError` - No handler for command type
- `ShutdownError` - Coordinator has been shut down

## Migration Notes

Integration with existing code:
1. `SimulationEngine` will call `process_pending_commands()` at start of each `step()`
2. API handlers will use `send_command()` instead of direct method calls
3. State reads will use `GET_SNAPSHOT` for thread-safe access
4. WebSocket updates continue via Redis pub/sub (unchanged)
