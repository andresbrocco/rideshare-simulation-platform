#!/usr/bin/env python3
"""Test event producer for Kafka topics.

Usage:
    python generate_test_events.py --event-type trip_lifecycle --count 10
    python generate_test_events.py --event-type gps_pings --count 100
    python generate_test_events.py --event-type all --count 5
"""

import argparse
import json
import os
import sys
import time
import uuid
from typing import List, Dict, Any

from confluent_kafka import Producer


# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fixtures.trip_events import generate_trip_lifecycle
from fixtures.gps_events import generate_multi_driver_gps_pings
from fixtures.driver_events import (
    generate_driver_status_event,
    generate_driver_profile_event,
)
from fixtures.rider_events import generate_rider_profile_event


# Environment variables
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8085")


def create_producer() -> Producer:
    """Create Kafka producer instance.

    Returns:
        Configured Kafka Producer
    """
    config = {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "client.id": "test-data-producer",
        "acks": "all",  # Wait for all in-sync replicas
        "retries": 3,
        "linger.ms": 10,  # Batch messages for efficiency
    }
    return Producer(config)


def delivery_callback(err, msg):
    """Callback for producer delivery reports.

    Args:
        err: Error if delivery failed
        msg: Message metadata
    """
    if err:
        print(f"ERROR: Message delivery failed: {err}")
    else:
        print(
            f"Message delivered to {msg.topic()} "
            f"[partition {msg.partition()}] at offset {msg.offset()}"
        )


def publish_events(producer: Producer, topic: str, events: List[Dict[str, Any]]):
    """Publish events to Kafka topic.

    Args:
        producer: Kafka Producer instance
        topic: Kafka topic name
        events: List of event dictionaries
    """
    for event in events:
        # Serialize event as JSON
        value = json.dumps(event).encode("utf-8")

        # Determine partition key
        if "trip_id" in event:
            key = event["trip_id"].encode("utf-8")
        elif "entity_id" in event:
            key = event["entity_id"].encode("utf-8")
        elif "driver_id" in event:
            key = event["driver_id"].encode("utf-8")
        elif "rider_id" in event:
            key = event["rider_id"].encode("utf-8")
        else:
            key = None

        # Produce message
        producer.produce(
            topic=topic,
            key=key,
            value=value,
            callback=delivery_callback,
        )

    # Wait for all messages to be delivered
    producer.flush()


def generate_trip_events(count: int) -> List[Dict[str, Any]]:
    """Generate trip lifecycle events.

    Args:
        count: Number of trip lifecycles to generate

    Returns:
        List of trip events
    """
    all_events = []
    for i in range(count):
        lifecycle = generate_trip_lifecycle()
        all_events.extend(lifecycle)
    return all_events


def generate_gps_events(count: int) -> List[Dict[str, Any]]:
    """Generate GPS ping events.

    Args:
        count: Total number of GPS pings to generate

    Returns:
        List of GPS ping events
    """
    # Distribute pings across multiple drivers
    num_drivers = max(1, count // 20)  # ~20 pings per driver
    pings_per_driver = count // num_drivers

    return generate_multi_driver_gps_pings(
        num_drivers=num_drivers,
        pings_per_driver=pings_per_driver,
    )


def generate_driver_status_events(count: int) -> List[Dict[str, Any]]:
    """Generate driver status events.

    Args:
        count: Number of status events to generate

    Returns:
        List of driver status events
    """
    events = []
    for i in range(count):
        driver_id = f"driver-{uuid.uuid4()}"
        event = generate_driver_status_event(
            driver_id=driver_id,
            new_status="online",
            trigger="driver_app_opened",
        )
        events.append(event)
    return events


def generate_driver_profile_events(count: int) -> List[Dict[str, Any]]:
    """Generate driver profile events.

    Args:
        count: Number of profile events to generate

    Returns:
        List of driver profile events
    """
    events = []
    for i in range(count):
        driver_id = f"driver-{uuid.uuid4()}"
        event = generate_driver_profile_event(
            event_type="driver.created",
            driver_id=driver_id,
        )
        events.append(event)
    return events


def generate_rider_profile_events(count: int) -> List[Dict[str, Any]]:
    """Generate rider profile events.

    Args:
        count: Number of profile events to generate

    Returns:
        List of rider profile events
    """
    events = []
    for i in range(count):
        rider_id = f"rider-{uuid.uuid4()}"
        event = generate_rider_profile_event(
            event_type="rider.created",
            rider_id=rider_id,
        )
        events.append(event)
    return events


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate test events for Kafka")
    parser.add_argument(
        "--event-type",
        choices=[
            "trip_lifecycle",
            "gps_pings",
            "driver_status",
            "driver_profiles",
            "rider_profiles",
            "all",
        ],
        required=True,
        help="Type of events to generate",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of events to generate (default: 10)",
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuously (for stress testing)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Interval in seconds between batches (continuous mode)",
    )

    args = parser.parse_args()

    print(f"Kafka Bootstrap Servers: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Schema Registry URL: {SCHEMA_REGISTRY_URL}")
    print(f"Event Type: {args.event_type}")
    print(f"Count: {args.count}")
    print(f"Continuous: {args.continuous}")
    print()

    # Create producer
    producer = create_producer()

    # Event generation mapping
    event_generators = {
        "trip_lifecycle": (generate_trip_events, "trips"),
        "gps_pings": (generate_gps_events, "gps-pings"),
        "driver_status": (generate_driver_status_events, "driver-status"),
        "driver_profiles": (generate_driver_profile_events, "driver-profiles"),
        "rider_profiles": (generate_rider_profile_events, "rider-profiles"),
    }

    def produce_batch():
        """Produce a single batch of events."""
        if args.event_type == "all":
            # Generate all event types
            for event_type, (generator, topic) in event_generators.items():
                print(f"Generating {args.count} {event_type} events...")
                events = generator(args.count)
                print(f"Publishing {len(events)} events to {topic}...")
                publish_events(producer, topic, events)
                print()
        else:
            # Generate specific event type
            generator, topic = event_generators[args.event_type]
            print(f"Generating {args.count} {args.event_type} events...")
            events = generator(args.count)
            print(f"Publishing {len(events)} events to {topic}...")
            publish_events(producer, topic, events)
            print()

    # Run once or continuously
    if args.continuous:
        print("Running in continuous mode (Ctrl+C to stop)...")
        try:
            while True:
                produce_batch()
                print(f"Waiting {args.interval} seconds before next batch...")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopping producer...")
    else:
        produce_batch()

    print("Done!")


if __name__ == "__main__":
    main()
