#!/usr/bin/env python3
"""
WebSocket Performance Benchmark

Tests WebSocket connection capacity and message broadcast latency.

Usage:
    ./venv/bin/python scripts/perf/test_websocket.py

Options:
    --ws-url: WebSocket URL (default: ws://localhost:8000/ws)
    --api-key: API key (default: dev-api-key-change-in-production)
    --clients: Number of concurrent clients (default: 50)
    --duration: Test duration in seconds (default: 30)
"""

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field

import websockets


@dataclass
class ClientStats:
    """Statistics for a single WebSocket client."""

    messages_received: int = 0
    first_message_time: float | None = None
    last_message_time: float | None = None
    message_latencies: list[float] = field(default_factory=list)
    connection_time_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


async def run_client(
    ws_url: str,
    api_key: str,
    client_id: int,
    duration: float,
    stats: ClientStats,
) -> None:
    """Run a single WebSocket client."""
    try:
        start_time = time.perf_counter()

        async with websockets.connect(
            ws_url,
            subprotocols=[f"apikey.{api_key}"],
            ping_interval=20,
            ping_timeout=10,
        ) as ws:
            stats.connection_time_ms = (time.perf_counter() - start_time) * 1000

            end_time = time.time() + duration

            while time.time() < end_time:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    receive_time = time.perf_counter()

                    if stats.first_message_time is None:
                        stats.first_message_time = receive_time

                    stats.last_message_time = receive_time
                    stats.messages_received += 1

                    # Try to extract timestamp from message for latency calculation
                    try:
                        data = json.loads(message)
                        if "timestamp" in data:
                            # Can't calculate true latency without synchronized clocks
                            pass
                    except (json.JSONDecodeError, KeyError):
                        pass

                except TimeoutError:
                    continue

    except websockets.exceptions.ConnectionClosed as e:
        stats.errors.append(f"Connection closed: {e.code}")
    except Exception as e:
        stats.errors.append(str(e))


async def run_benchmark(
    ws_url: str,
    api_key: str,
    num_clients: int,
    duration: float,
) -> dict:
    """Run the WebSocket benchmark with multiple clients."""
    print("\nWebSocket Benchmark")
    print(f"  URL: {ws_url}")
    print(f"  Clients: {num_clients}")
    print(f"  Duration: {duration}s\n")

    # Create stats for each client
    all_stats = [ClientStats() for _ in range(num_clients)]

    # Start all clients
    print("  Starting clients...")
    tasks = [
        run_client(ws_url, api_key, i, duration, all_stats[i])
        for i in range(num_clients)
    ]

    start_time = time.time()

    # Wait for all clients to complete
    await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = time.time() - start_time

    # Aggregate results
    successful_clients = sum(1 for s in all_stats if s.messages_received > 0)
    failed_clients = num_clients - successful_clients

    total_messages = sum(s.messages_received for s in all_stats)

    connection_times = [
        s.connection_time_ms for s in all_stats if s.connection_time_ms > 0
    ]
    sorted_connection = sorted(connection_times) if connection_times else [0]

    messages_per_client = [
        s.messages_received for s in all_stats if s.messages_received > 0
    ]

    # Calculate message rates per client
    rates = []
    for s in all_stats:
        if s.first_message_time and s.last_message_time and s.messages_received > 1:
            client_duration = s.last_message_time - s.first_message_time
            if client_duration > 0:
                rates.append(s.messages_received / client_duration)

    all_errors = []
    for s in all_stats:
        all_errors.extend(s.errors)

    results = {
        "clients": {
            "total": num_clients,
            "successful": successful_clients,
            "failed": failed_clients,
        },
        "messages": {
            "total": total_messages,
            "avg_per_client": (
                statistics.mean(messages_per_client) if messages_per_client else 0
            ),
            "total_rate_mps": total_messages / elapsed if elapsed > 0 else 0,
            "avg_client_rate": statistics.mean(rates) if rates else 0,
        },
        "connection": {
            "avg_time_ms": statistics.mean(connection_times) if connection_times else 0,
            "p50_time_ms": sorted_connection[int(len(sorted_connection) * 0.50)],
            "p95_time_ms": (
                sorted_connection[int(len(sorted_connection) * 0.95)]
                if len(sorted_connection) > 1
                else sorted_connection[0]
            ),
            "max_time_ms": max(connection_times) if connection_times else 0,
        },
        "errors": all_errors[:10],  # First 10 errors
        "elapsed_seconds": elapsed,
    }

    return results


def print_results(results: dict) -> None:
    """Print benchmark results."""
    print("\n" + "=" * 50)
    print("WEBSOCKET BENCHMARK RESULTS")
    print("=" * 50)

    print("\nClients:")
    print(f"  Total: {results['clients']['total']}")
    print(f"  Successful: {results['clients']['successful']}")
    print(f"  Failed: {results['clients']['failed']}")

    print("\nMessages:")
    print(f"  Total Received: {results['messages']['total']}")
    print(f"  Avg per Client: {results['messages']['avg_per_client']:.0f}")
    print(f"  Total Rate: {results['messages']['total_rate_mps']:.1f} msg/sec")
    print(f"  Avg Client Rate: {results['messages']['avg_client_rate']:.1f} msg/sec")

    print("\nConnection Time:")
    print(f"  Average: {results['connection']['avg_time_ms']:.0f}ms")
    print(f"  p50: {results['connection']['p50_time_ms']:.0f}ms")
    print(f"  p95: {results['connection']['p95_time_ms']:.0f}ms")
    print(f"  Max: {results['connection']['max_time_ms']:.0f}ms")

    if results["errors"]:
        print("\nErrors (first 10):")
        for err in results["errors"]:
            print(f"  - {err}")

    print(f"\nTest Duration: {results['elapsed_seconds']:.1f}s")
    print("\n" + "=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Benchmark WebSocket connections")
    parser.add_argument(
        "--ws-url",
        type=str,
        default="ws://localhost:8000/ws",
        help="WebSocket URL",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default="dev-api-key-change-in-production",
        help="API key",
    )
    parser.add_argument(
        "--clients",
        type=int,
        default=50,
        help="Number of concurrent clients",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Test duration in seconds",
    )

    args = parser.parse_args()

    try:
        results = asyncio.run(
            run_benchmark(args.ws_url, args.api_key, args.clients, args.duration)
        )
        print_results(results)
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure the simulation API is running.")


if __name__ == "__main__":
    main()
