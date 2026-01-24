#!/usr/bin/env python3
"""
Load Testing Script for Rideshare Simulation Platform

Gradually ramps up agents to discover performance limits.

Usage:
    ./venv/bin/python scripts/load_test.py --max-drivers 500 --max-riders 2000

Options:
    --max-drivers: Maximum number of drivers to create (default: 500)
    --max-riders: Maximum number of riders to create (default: 2000)
    --ramp-duration: Duration in seconds to ramp up agents (default: 300)
    --hold-duration: Duration in seconds to hold at max load (default: 120)
    --api-url: API base URL (default: http://localhost:8000)
    --api-key: API key for authentication (default: dev-api-key-change-in-production)
    --output: Output CSV file for results (default: load_test_results.csv)
"""

import argparse
import csv
import sys
import time
from dataclasses import dataclass
from datetime import datetime

import requests


@dataclass
class PerformanceSnapshot:
    """Point-in-time performance measurement."""

    timestamp: float
    elapsed_seconds: float
    driver_count: int
    rider_count: int
    events_per_sec: float
    gps_pings_per_sec: float
    trip_events_per_sec: float
    osrm_avg_ms: float
    osrm_p95_ms: float
    kafka_avg_ms: float
    redis_avg_ms: float
    memory_mb: float
    active_trips: int


class LoadTester:
    """Orchestrates load testing of the simulation."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        max_drivers: int,
        max_riders: int,
        ramp_duration: int,
        hold_duration: int,
        output_file: str,
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.max_drivers = max_drivers
        self.max_riders = max_riders
        self.ramp_duration = ramp_duration
        self.hold_duration = hold_duration
        self.output_file = output_file

        self.headers = {"X-API-Key": api_key}
        self.snapshots: list[PerformanceSnapshot] = []
        self.start_time = 0.0

    def _api_get(self, endpoint: str) -> dict | None:
        """Make GET request to API."""
        try:
            response = requests.get(
                f"{self.api_url}{endpoint}",
                headers=self.headers,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"API error: {e}")
            return None

    def _api_post(self, endpoint: str, data: dict | None = None) -> dict | None:
        """Make POST request to API."""
        try:
            response = requests.post(
                f"{self.api_url}{endpoint}",
                headers=self.headers,
                json=data or {},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"API error: {e}")
            return None

    def get_performance_metrics(self) -> dict | None:
        """Fetch current performance metrics."""
        return self._api_get("/metrics/performance")

    def get_simulation_status(self) -> dict | None:
        """Fetch current simulation status."""
        return self._api_get("/simulation/status")

    def add_drivers(self, count: int) -> bool:
        """Add drivers to the simulation."""
        result = self._api_post("/agents/drivers", {"count": count})
        return result is not None

    def add_riders(self, count: int) -> bool:
        """Add riders to the simulation."""
        result = self._api_post("/agents/riders", {"count": count})
        return result is not None

    def start_simulation(self) -> bool:
        """Start the simulation."""
        result = self._api_post("/simulation/start")
        return result is not None

    def take_snapshot(self) -> PerformanceSnapshot | None:
        """Take a performance snapshot."""
        perf = self.get_performance_metrics()
        status = self.get_simulation_status()

        if not perf or not status:
            return None

        elapsed = time.time() - self.start_time

        # Extract latency metrics safely
        osrm = perf.get("latency", {}).get("osrm") or {}
        kafka = perf.get("latency", {}).get("kafka") or {}
        redis = perf.get("latency", {}).get("redis") or {}

        return PerformanceSnapshot(
            timestamp=time.time(),
            elapsed_seconds=elapsed,
            driver_count=status.get("drivers_total", 0),
            rider_count=status.get("riders_total", 0),
            events_per_sec=perf.get("events", {}).get("total_per_sec", 0),
            gps_pings_per_sec=perf.get("events", {}).get("gps_pings_per_sec", 0),
            trip_events_per_sec=perf.get("events", {}).get("trip_events_per_sec", 0),
            osrm_avg_ms=osrm.get("avg_ms", 0),
            osrm_p95_ms=osrm.get("p95_ms", 0),
            kafka_avg_ms=kafka.get("avg_ms", 0),
            redis_avg_ms=redis.get("avg_ms", 0),
            memory_mb=perf.get("memory", {}).get("rss_mb", 0),
            active_trips=perf.get("queue_depths", {}).get("active_trips", 0),
        )

    def check_saturation(self, snapshot: PerformanceSnapshot) -> bool:
        """Check if system is saturated (performance degrading)."""
        # Saturation indicators:
        # - OSRM latency > 500ms
        # - Memory > 2GB
        # - Events/sec dropping significantly
        if snapshot.osrm_p95_ms > 500:
            print(f"  [WARN] OSRM p95 latency high: {snapshot.osrm_p95_ms:.0f}ms")
            return True
        if snapshot.memory_mb > 2048:
            print(f"  [WARN] Memory usage high: {snapshot.memory_mb:.0f}MB")
            return True
        return False

    def run_ramp_phase(self) -> bool:
        """Run the ramp-up phase, gradually adding agents."""
        print(f"\n[RAMP] Starting ramp-up over {self.ramp_duration}s")
        print(f"       Target: {self.max_drivers} drivers, {self.max_riders} riders\n")

        # Calculate increments (10 steps)
        num_steps = 10
        step_duration = self.ramp_duration / num_steps
        drivers_per_step = self.max_drivers // num_steps
        riders_per_step = self.max_riders // num_steps

        current_drivers = 0
        current_riders = 0

        for step in range(1, num_steps + 1):
            print(f"  Step {step}/{num_steps}")

            # Add agents
            drivers_to_add = min(drivers_per_step, self.max_drivers - current_drivers)
            riders_to_add = min(riders_per_step, self.max_riders - current_riders)

            if drivers_to_add > 0:
                print(f"    Adding {drivers_to_add} drivers...")
                if not self.add_drivers(drivers_to_add):
                    print("    [ERROR] Failed to add drivers")
                    return False
                current_drivers += drivers_to_add

            if riders_to_add > 0:
                print(f"    Adding {riders_to_add} riders...")
                if not self.add_riders(riders_to_add):
                    print("    [ERROR] Failed to add riders")
                    return False
                current_riders += riders_to_add

            # Wait and collect metrics
            samples_per_step = 3
            for _ in range(samples_per_step):
                time.sleep(step_duration / samples_per_step)
                snapshot = self.take_snapshot()
                if snapshot:
                    self.snapshots.append(snapshot)
                    self._print_snapshot(snapshot)

                    if self.check_saturation(snapshot):
                        print("\n  [SATURATION DETECTED] Stopping ramp-up early")
                        return True

        return True

    def run_hold_phase(self) -> None:
        """Run the hold phase at maximum load."""
        print(f"\n[HOLD] Holding at max load for {self.hold_duration}s\n")

        end_time = time.time() + self.hold_duration
        sample_interval = 5  # seconds

        while time.time() < end_time:
            snapshot = self.take_snapshot()
            if snapshot:
                self.snapshots.append(snapshot)
                self._print_snapshot(snapshot)
            time.sleep(sample_interval)

    def _print_snapshot(self, snapshot: PerformanceSnapshot) -> None:
        """Print a snapshot summary."""
        print(
            f"    [{snapshot.elapsed_seconds:6.0f}s] "
            f"D:{snapshot.driver_count:4d} R:{snapshot.rider_count:5d} "
            f"| Events:{snapshot.events_per_sec:7.1f}/s "
            f"| OSRM:{snapshot.osrm_avg_ms:5.0f}ms "
            f"| Mem:{snapshot.memory_mb:6.0f}MB "
            f"| Trips:{snapshot.active_trips:3d}"
        )

    def save_results(self) -> None:
        """Save results to CSV file."""
        if not self.snapshots:
            print("No snapshots to save")
            return

        with open(self.output_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "elapsed_seconds",
                    "driver_count",
                    "rider_count",
                    "events_per_sec",
                    "gps_pings_per_sec",
                    "trip_events_per_sec",
                    "osrm_avg_ms",
                    "osrm_p95_ms",
                    "kafka_avg_ms",
                    "redis_avg_ms",
                    "memory_mb",
                    "active_trips",
                ]
            )
            for s in self.snapshots:
                writer.writerow(
                    [
                        s.timestamp,
                        s.elapsed_seconds,
                        s.driver_count,
                        s.rider_count,
                        s.events_per_sec,
                        s.gps_pings_per_sec,
                        s.trip_events_per_sec,
                        s.osrm_avg_ms,
                        s.osrm_p95_ms,
                        s.kafka_avg_ms,
                        s.redis_avg_ms,
                        s.memory_mb,
                        s.active_trips,
                    ]
                )

        print(f"\nResults saved to: {self.output_file}")

    def print_summary(self) -> None:
        """Print test summary."""
        if not self.snapshots:
            return

        print("\n" + "=" * 60)
        print("LOAD TEST SUMMARY")
        print("=" * 60)

        # Final metrics
        final = self.snapshots[-1]
        print("\nFinal State:")
        print(f"  Drivers: {final.driver_count}")
        print(f"  Riders: {final.rider_count}")
        print(f"  Active Trips: {final.active_trips}")
        print(f"  Memory: {final.memory_mb:.0f} MB")

        # Peak metrics
        peak_events = max(s.events_per_sec for s in self.snapshots)
        peak_memory = max(s.memory_mb for s in self.snapshots)
        peak_osrm = max(s.osrm_p95_ms for s in self.snapshots)

        print("\nPeak Metrics:")
        print(f"  Events/sec: {peak_events:.1f}")
        print(f"  Memory: {peak_memory:.0f} MB")
        print(f"  OSRM p95: {peak_osrm:.0f} ms")

        # Bottleneck analysis
        print("\nBottleneck Analysis:")
        if peak_osrm > 500:
            print(f"  [CRITICAL] OSRM latency exceeded 500ms (peak: {peak_osrm:.0f}ms)")
        if peak_memory > 1024:
            print(f"  [WARNING] Memory usage exceeded 1GB (peak: {peak_memory:.0f}MB)")

        print("\n" + "=" * 60)

    def run(self) -> None:
        """Run the complete load test."""
        print("=" * 60)
        print("RIDESHARE SIMULATION LOAD TEST")
        print("=" * 60)
        print(f"\nStarted at: {datetime.now().isoformat()}")
        print(f"API URL: {self.api_url}")
        print(f"Max Drivers: {self.max_drivers}")
        print(f"Max Riders: {self.max_riders}")
        print(f"Ramp Duration: {self.ramp_duration}s")
        print(f"Hold Duration: {self.hold_duration}s")

        # Check API connectivity
        status = self.get_simulation_status()
        if not status:
            print("\n[ERROR] Cannot connect to API")
            sys.exit(1)

        print(f"\nSimulation Status: {status.get('state', 'unknown')}")

        # Start simulation if not running
        if status.get("state") != "running":
            print("\nStarting simulation...")
            if not self.start_simulation():
                print("[ERROR] Failed to start simulation")
                sys.exit(1)
            time.sleep(2)

        self.start_time = time.time()

        # Run phases
        try:
            if self.run_ramp_phase():
                self.run_hold_phase()
        except KeyboardInterrupt:
            print("\n\n[INTERRUPTED] Stopping load test...")

        # Save and summarize
        self.save_results()
        self.print_summary()


def main():
    parser = argparse.ArgumentParser(description="Load test the rideshare simulation platform")
    parser.add_argument(
        "--max-drivers",
        type=int,
        default=500,
        help="Maximum number of drivers (default: 500)",
    )
    parser.add_argument(
        "--max-riders",
        type=int,
        default=2000,
        help="Maximum number of riders (default: 2000)",
    )
    parser.add_argument(
        "--ramp-duration",
        type=int,
        default=300,
        help="Ramp-up duration in seconds (default: 300)",
    )
    parser.add_argument(
        "--hold-duration",
        type=int,
        default=120,
        help="Hold duration in seconds (default: 120)",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default="dev-api-key-change-in-production",
        help="API key for authentication",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="load_test_results.csv",
        help="Output CSV file (default: load_test_results.csv)",
    )

    args = parser.parse_args()

    tester = LoadTester(
        api_url=args.api_url,
        api_key=args.api_key,
        max_drivers=args.max_drivers,
        max_riders=args.max_riders,
        ramp_duration=args.ramp_duration,
        hold_duration=args.hold_duration,
        output_file=args.output,
    )

    tester.run()


if __name__ == "__main__":
    main()
