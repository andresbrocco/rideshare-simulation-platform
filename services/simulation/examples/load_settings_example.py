#!/usr/bin/env python3
"""
Example script demonstrating how to load and use settings.

This script shows how environment variables are loaded and validated.
Before running, ensure you have set up your .env file:
    cp ../.env.example ../.env
    # Edit .env with your actual values
"""

from settings import get_settings


def main():
    print("Loading settings from environment variables...")
    print()

    try:
        settings = get_settings()

        print("Simulation Settings:")
        print(f"  Speed Multiplier: {settings.simulation.speed_multiplier}x")
        print(f"  Log Level: {settings.simulation.log_level}")
        print(f"  Checkpoint Interval: {settings.simulation.checkpoint_interval}s")
        print()

        print("Kafka Settings:")
        print(f"  Bootstrap Servers: {settings.kafka.bootstrap_servers}")
        print(f"  Security Protocol: {settings.kafka.security_protocol}")
        print(f"  Schema Registry: {settings.kafka.schema_registry_url}")
        print()

        print("Redis Settings:")
        print(f"  Host: {settings.redis.host}")
        print(f"  Port: {settings.redis.port}")
        print(f"  SSL: {settings.redis.ssl}")
        print()

        print("OSRM Settings:")
        print(f"  Base URL: {settings.osrm.base_url}")
        print()

        print("Settings loaded successfully!")

    except Exception as e:
        print(f"Error loading settings: {e}")
        print()
        print("Make sure you have:")
        print("1. Copied .env.example to .env")
        print("2. Set all required environment variables")
        print("3. Or exported them in your shell")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
