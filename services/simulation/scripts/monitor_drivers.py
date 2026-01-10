#!/usr/bin/env python3
"""Monitor driver online/offline status over time."""

import time
from datetime import datetime

import requests

API_URL = "http://localhost:8000"
API_KEY = "dev-api-key-change-in-production"


def get_status():
    """Get simulation status."""
    resp = requests.get(f"{API_URL}/simulation/status", headers={"X-API-Key": API_KEY})
    return resp.json()


def main():
    print("=== Driver Status Monitoring ===")
    print("Time       | Online | Total | Trips | Status")
    print("-" * 50)

    samples = []

    for _ in range(30):  # 2.5 minutes (5s intervals)
        try:
            status = get_status()
            online = status.get("online_drivers", 0)
            total = status.get("total_drivers", 0)
            trips = status.get("active_trips", 0)

            timestamp = datetime.now().strftime("%H:%M:%S")

            samples.append(
                {"time": timestamp, "online": online, "total": total, "trips": trips}
            )

            print(f"{timestamp} | {online:6} | {total:5} | {trips:5} |")

        except Exception as e:
            print(f"Error: {e}")

        time.sleep(5)

    # Analyze the data
    print("\n=== Analysis ===")

    if len(samples) >= 2:
        # Check if online drivers ever increased after decreasing
        online_counts = [s["online"] for s in samples]

        min_online = min(online_counts)
        max_online = max(online_counts)

        # Find if there was a recovery (increase after decrease)
        recovered = False
        lowest_idx = online_counts.index(min_online)

        for idx in range(lowest_idx + 1, len(online_counts)):
            if online_counts[idx] > min_online:
                recovered = True
                break

        print(f"Initial online: {online_counts[0]}")
        print(f"Min online: {min_online}")
        print(f"Max online: {max_online}")
        print(f"Final online: {online_counts[-1]}")
        print(f"Drivers recovered (went back online): {recovered}")

        # Show trend
        trend = "stable"
        if online_counts[-1] > online_counts[0]:
            trend = "increasing"
        elif online_counts[-1] < online_counts[0]:
            trend = "decreasing"

        print(f"Overall trend: {trend}")


if __name__ == "__main__":
    main()
