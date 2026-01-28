#!/usr/bin/env python3
"""
OSRM Performance Benchmark

Tests OSRM routing service performance with concurrent requests.

Usage:
    ./venv/bin/python scripts/perf/test_osrm.py

Options:
    --osrm-url: OSRM base URL (default: http://localhost:5050)
    --concurrency: Number of concurrent requests (default: 10)
    --requests: Total number of requests (default: 100)
"""

import argparse
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# São Paulo bounding box
SAO_PAULO_BOUNDS = {
    "min_lat": -23.7,
    "max_lat": -23.4,
    "min_lon": -46.8,
    "max_lon": -46.4,
}


def random_coords() -> tuple[float, float]:
    """Generate random coordinates within São Paulo."""
    lat = random.uniform(SAO_PAULO_BOUNDS["min_lat"], SAO_PAULO_BOUNDS["max_lat"])
    lon = random.uniform(SAO_PAULO_BOUNDS["min_lon"], SAO_PAULO_BOUNDS["max_lon"])
    return lat, lon


def fetch_route(osrm_url: str, timeout: float = 10.0) -> tuple[float, bool]:
    """Fetch a route and return (latency_ms, success)."""
    origin = random_coords()
    dest = random_coords()

    url = f"{osrm_url}/route/v1/driving/{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
    params = {"overview": "full", "geometries": "polyline"}

    start = time.perf_counter()
    try:
        response = requests.get(url, params=params, timeout=timeout)
        latency_ms = (time.perf_counter() - start) * 1000

        if response.status_code == 200:
            data = response.json()
            if data.get("code") == "Ok":
                return latency_ms, True

        return latency_ms, False
    except Exception:
        latency_ms = (time.perf_counter() - start) * 1000
        return latency_ms, False


def run_benchmark(osrm_url: str, concurrency: int, total_requests: int) -> dict:
    """Run the benchmark and return results."""
    print(f"\nBenchmarking OSRM: {osrm_url}")
    print(f"Concurrency: {concurrency}")
    print(f"Total Requests: {total_requests}\n")

    latencies: list[float] = []
    successes = 0
    failures = 0

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(fetch_route, osrm_url) for _ in range(total_requests)]

        for i, future in enumerate(as_completed(futures), 1):
            latency_ms, success = future.result()
            latencies.append(latency_ms)

            if success:
                successes += 1
            else:
                failures += 1

            if i % 10 == 0:
                print(f"  Progress: {i}/{total_requests} ({successes} ok, {failures} fail)")

    elapsed = time.time() - start_time
    throughput = total_requests / elapsed

    # Calculate statistics
    sorted_latencies = sorted(latencies)
    results = {
        "total_requests": total_requests,
        "successes": successes,
        "failures": failures,
        "elapsed_seconds": elapsed,
        "throughput_rps": throughput,
        "avg_latency_ms": statistics.mean(latencies),
        "p50_latency_ms": sorted_latencies[int(len(sorted_latencies) * 0.50)],
        "p95_latency_ms": sorted_latencies[int(len(sorted_latencies) * 0.95)],
        "p99_latency_ms": sorted_latencies[int(len(sorted_latencies) * 0.99)],
        "min_latency_ms": min(latencies),
        "max_latency_ms": max(latencies),
    }

    return results


def print_results(results: dict) -> None:
    """Print benchmark results."""
    print("\n" + "=" * 50)
    print("OSRM BENCHMARK RESULTS")
    print("=" * 50)

    print("\nRequests:")
    print(f"  Total: {results['total_requests']}")
    print(f"  Success: {results['successes']}")
    print(f"  Failures: {results['failures']}")
    print(f"  Success Rate: {results['successes'] / results['total_requests'] * 100:.1f}%")

    print("\nThroughput:")
    print(f"  Duration: {results['elapsed_seconds']:.1f}s")
    print(f"  Requests/sec: {results['throughput_rps']:.1f}")

    print("\nLatency:")
    print(f"  Average: {results['avg_latency_ms']:.1f}ms")
    print(f"  Median (p50): {results['p50_latency_ms']:.1f}ms")
    print(f"  p95: {results['p95_latency_ms']:.1f}ms")
    print(f"  p99: {results['p99_latency_ms']:.1f}ms")
    print(f"  Min: {results['min_latency_ms']:.1f}ms")
    print(f"  Max: {results['max_latency_ms']:.1f}ms")

    print("\n" + "=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Benchmark OSRM performance")
    parser.add_argument(
        "--osrm-url",
        type=str,
        default="http://localhost:5050",
        help="OSRM base URL",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Number of concurrent requests",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=100,
        help="Total number of requests",
    )

    args = parser.parse_args()

    results = run_benchmark(args.osrm_url, args.concurrency, args.requests)
    print_results(results)


if __name__ == "__main__":
    main()
