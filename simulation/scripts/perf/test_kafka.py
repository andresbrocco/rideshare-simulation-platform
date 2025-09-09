#!/usr/bin/env python3
"""
Kafka Producer Performance Benchmark

Tests Kafka producer throughput and delivery latency.

Usage:
    ./venv/bin/python scripts/perf/test_kafka.py

Options:
    --bootstrap-servers: Kafka bootstrap servers (default: localhost:9092)
    --topic: Topic to produce to (default: test-benchmark)
    --messages: Number of messages to produce (default: 10000)
    --batch-size: Producer batch size (default: 16384)
"""

import argparse
import json
import statistics
import time
import uuid
from threading import Event

from confluent_kafka import Producer


def delivery_callback(err, msg, latencies: list, delivery_event: Event):
    """Callback for message delivery."""
    if err:
        print(f"Delivery failed: {err}")
    else:
        latency_ms = (time.perf_counter() - float(msg.key())) * 1000
        latencies.append(latency_ms)


def run_benchmark(
    bootstrap_servers: str,
    topic: str,
    num_messages: int,
    batch_size: int,
) -> dict:
    """Run the Kafka producer benchmark."""
    print("\nKafka Producer Benchmark")
    print(f"  Servers: {bootstrap_servers}")
    print(f"  Topic: {topic}")
    print(f"  Messages: {num_messages}")
    print(f"  Batch Size: {batch_size}\n")

    config = {
        "bootstrap.servers": bootstrap_servers,
        "batch.size": batch_size,
        "linger.ms": 5,
        "acks": "all",
    }

    producer = Producer(config)
    latencies: list[float] = []
    delivery_event = Event()

    # Generate sample message
    sample_payload = json.dumps(
        {
            "event_id": str(uuid.uuid4()),
            "entity_type": "driver",
            "entity_id": "test-driver",
            "timestamp": "2025-01-01T00:00:00Z",
            "location": [-23.55, -46.63],
            "heading": 90.0,
            "speed": 30.0,
            "accuracy": 5.0,
        }
    )

    produce_latencies: list[float] = []
    start_time = time.time()

    for i in range(num_messages):
        produce_start = time.perf_counter()

        # Use timestamp as key for latency tracking
        producer.produce(
            topic,
            key=str(produce_start),
            value=sample_payload,
            callback=lambda err, msg: delivery_callback(err, msg, latencies, delivery_event),
        )

        produce_latency = (time.perf_counter() - produce_start) * 1000
        produce_latencies.append(produce_latency)

        # Poll to handle callbacks
        producer.poll(0)

        if (i + 1) % 1000 == 0:
            print(f"  Produced {i + 1}/{num_messages}")

    # Flush remaining messages
    print("  Flushing...")
    producer.flush()

    elapsed = time.time() - start_time
    throughput = num_messages / elapsed

    # Calculate statistics
    sorted_produce = sorted(produce_latencies)
    sorted_delivery = sorted(latencies) if latencies else [0]

    results = {
        "messages": num_messages,
        "elapsed_seconds": elapsed,
        "throughput_mps": throughput,
        "produce": {
            "avg_latency_ms": statistics.mean(produce_latencies),
            "p50_latency_ms": sorted_produce[int(len(sorted_produce) * 0.50)],
            "p95_latency_ms": sorted_produce[int(len(sorted_produce) * 0.95)],
            "p99_latency_ms": sorted_produce[int(len(sorted_produce) * 0.99)],
        },
        "delivery": {
            "count": len(latencies),
            "avg_latency_ms": statistics.mean(latencies) if latencies else 0,
            "p50_latency_ms": sorted_delivery[int(len(sorted_delivery) * 0.50)],
            "p95_latency_ms": sorted_delivery[int(len(sorted_delivery) * 0.95)],
            "p99_latency_ms": sorted_delivery[int(len(sorted_delivery) * 0.99)],
        },
    }

    return results


def print_results(results: dict) -> None:
    """Print benchmark results."""
    print("\n" + "=" * 50)
    print("KAFKA BENCHMARK RESULTS")
    print("=" * 50)

    print("\nThroughput:")
    print(f"  Messages: {results['messages']}")
    print(f"  Duration: {results['elapsed_seconds']:.1f}s")
    print(f"  Throughput: {results['throughput_mps']:.0f} msg/sec")

    print("\nProduce Latency (local queue):")
    print(f"  Average: {results['produce']['avg_latency_ms']:.3f}ms")
    print(f"  p50: {results['produce']['p50_latency_ms']:.3f}ms")
    print(f"  p95: {results['produce']['p95_latency_ms']:.3f}ms")
    print(f"  p99: {results['produce']['p99_latency_ms']:.3f}ms")

    print("\nDelivery Latency (end-to-end):")
    print(f"  Delivered: {results['delivery']['count']}")
    print(f"  Average: {results['delivery']['avg_latency_ms']:.1f}ms")
    print(f"  p50: {results['delivery']['p50_latency_ms']:.1f}ms")
    print(f"  p95: {results['delivery']['p95_latency_ms']:.1f}ms")
    print(f"  p99: {results['delivery']['p99_latency_ms']:.1f}ms")

    print("\n" + "=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Benchmark Kafka producer")
    parser.add_argument(
        "--bootstrap-servers",
        type=str,
        default="localhost:9092",
        help="Kafka bootstrap servers",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default="test-benchmark",
        help="Topic to produce to",
    )
    parser.add_argument(
        "--messages",
        type=int,
        default=10000,
        help="Number of messages",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16384,
        help="Producer batch size",
    )

    args = parser.parse_args()

    try:
        results = run_benchmark(
            args.bootstrap_servers,
            args.topic,
            args.messages,
            args.batch_size,
        )
        print_results(results)
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure Kafka is running and accessible.")


if __name__ == "__main__":
    main()
