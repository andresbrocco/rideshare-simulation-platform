#!/usr/bin/env python3
"""
Redis Pub/Sub Performance Benchmark

Tests Redis publish throughput and subscriber lag.

Usage:
    ./venv/bin/python scripts/perf/test_redis.py

Options:
    --redis-host: Redis host (default: localhost)
    --redis-port: Redis port (default: 6379)
    --messages: Number of messages to publish (default: 10000)
    --channel: Channel name (default: test-channel)
"""

import argparse
import json
import statistics
import threading
import time
import uuid

import redis


def run_publisher_benchmark(
    host: str, port: int, channel: str, num_messages: int
) -> dict:
    """Benchmark Redis publish throughput."""
    print("\nPublisher Benchmark")
    print(f"  Channel: {channel}")
    print(f"  Messages: {num_messages}\n")

    client = redis.Redis(host=host, port=port, decode_responses=True)

    # Generate sample messages
    sample_message = json.dumps(
        {
            "event_id": str(uuid.uuid4()),
            "entity_type": "driver",
            "entity_id": "test-driver",
            "timestamp": "2025-01-01T00:00:00Z",
            "location": [-23.55, -46.63],
            "heading": 90.0,
            "speed": 30.0,
        }
    )

    latencies: list[float] = []

    start_time = time.time()

    for i in range(num_messages):
        msg_start = time.perf_counter()
        client.publish(channel, sample_message)
        latency_ms = (time.perf_counter() - msg_start) * 1000
        latencies.append(latency_ms)

        if (i + 1) % 1000 == 0:
            print(f"  Published {i + 1}/{num_messages}")

    elapsed = time.time() - start_time
    throughput = num_messages / elapsed

    sorted_latencies = sorted(latencies)
    results = {
        "messages": num_messages,
        "elapsed_seconds": elapsed,
        "throughput_mps": throughput,
        "avg_latency_ms": statistics.mean(latencies),
        "p50_latency_ms": sorted_latencies[int(len(sorted_latencies) * 0.50)],
        "p95_latency_ms": sorted_latencies[int(len(sorted_latencies) * 0.95)],
        "p99_latency_ms": sorted_latencies[int(len(sorted_latencies) * 0.99)],
    }

    client.close()
    return results


def run_pubsub_lag_benchmark(
    host: str, port: int, channel: str, num_messages: int
) -> dict:
    """Benchmark Redis pub/sub lag."""
    print("\nPub/Sub Lag Benchmark")
    print(f"  Channel: {channel}")
    print(f"  Messages: {num_messages}\n")

    received_times: dict[str, float] = {}
    received_count = 0
    receive_lock = threading.Lock()

    def subscriber_thread():
        nonlocal received_count
        sub_client = redis.Redis(host=host, port=port, decode_responses=True)
        pubsub = sub_client.pubsub()
        pubsub.subscribe(channel)

        for message in pubsub.listen():
            if message["type"] == "message":
                receive_time = time.perf_counter()
                data = json.loads(message["data"])
                msg_id = data.get("msg_id")
                if msg_id:
                    with receive_lock:
                        received_times[msg_id] = receive_time
                        received_count += 1
                        if received_count >= num_messages:
                            break

        pubsub.close()
        sub_client.close()

    # Start subscriber
    sub_thread = threading.Thread(target=subscriber_thread, daemon=True)
    sub_thread.start()
    time.sleep(0.5)  # Wait for subscriber to be ready

    # Publish messages with timestamps
    pub_client = redis.Redis(host=host, port=port, decode_responses=True)
    send_times: dict[str, float] = {}

    for i in range(num_messages):
        msg_id = str(uuid.uuid4())
        message = json.dumps({"msg_id": msg_id})
        send_times[msg_id] = time.perf_counter()
        pub_client.publish(channel, message)

        if (i + 1) % 1000 == 0:
            print(f"  Published {i + 1}/{num_messages}")

    pub_client.close()

    # Wait for subscriber to receive all
    sub_thread.join(timeout=10)

    # Calculate lag
    lags: list[float] = []
    for msg_id, send_time in send_times.items():
        if msg_id in received_times:
            lag_ms = (received_times[msg_id] - send_time) * 1000
            lags.append(lag_ms)

    if not lags:
        return {"error": "No messages received"}

    sorted_lags = sorted(lags)
    results = {
        "messages_sent": num_messages,
        "messages_received": len(lags),
        "delivery_rate": len(lags) / num_messages * 100,
        "avg_lag_ms": statistics.mean(lags),
        "p50_lag_ms": sorted_lags[int(len(sorted_lags) * 0.50)],
        "p95_lag_ms": sorted_lags[int(len(sorted_lags) * 0.95)],
        "p99_lag_ms": sorted_lags[int(len(sorted_lags) * 0.99)],
        "max_lag_ms": max(lags),
    }

    return results


def print_results(pub_results: dict, lag_results: dict) -> None:
    """Print benchmark results."""
    print("\n" + "=" * 50)
    print("REDIS BENCHMARK RESULTS")
    print("=" * 50)

    print("\nPublish Throughput:")
    print(f"  Messages: {pub_results['messages']}")
    print(f"  Duration: {pub_results['elapsed_seconds']:.1f}s")
    print(f"  Throughput: {pub_results['throughput_mps']:.0f} msg/sec")
    print(f"  Avg Latency: {pub_results['avg_latency_ms']:.3f}ms")
    print(f"  p95 Latency: {pub_results['p95_latency_ms']:.3f}ms")
    print(f"  p99 Latency: {pub_results['p99_latency_ms']:.3f}ms")

    if "error" not in lag_results:
        print("\nPub/Sub Lag:")
        print(f"  Delivery Rate: {lag_results['delivery_rate']:.1f}%")
        print(f"  Avg Lag: {lag_results['avg_lag_ms']:.3f}ms")
        print(f"  p50 Lag: {lag_results['p50_lag_ms']:.3f}ms")
        print(f"  p95 Lag: {lag_results['p95_lag_ms']:.3f}ms")
        print(f"  p99 Lag: {lag_results['p99_lag_ms']:.3f}ms")
        print(f"  Max Lag: {lag_results['max_lag_ms']:.3f}ms")

    print("\n" + "=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Benchmark Redis pub/sub")
    parser.add_argument(
        "--redis-host",
        type=str,
        default="localhost",
        help="Redis host",
    )
    parser.add_argument(
        "--redis-port",
        type=int,
        default=6379,
        help="Redis port",
    )
    parser.add_argument(
        "--messages",
        type=int,
        default=10000,
        help="Number of messages",
    )
    parser.add_argument(
        "--channel",
        type=str,
        default="test-benchmark",
        help="Channel name",
    )

    args = parser.parse_args()

    # Run benchmarks
    pub_results = run_publisher_benchmark(
        args.redis_host, args.redis_port, args.channel, args.messages
    )

    lag_results = run_pubsub_lag_benchmark(
        args.redis_host,
        args.redis_port,
        args.channel + "-lag",
        min(args.messages, 1000),
    )

    print_results(pub_results, lag_results)


if __name__ == "__main__":
    main()
