#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.geo.gps_simulation import GPSSimulator

simulator = GPSSimulator(noise_meters=10.0, dropout_probability=0.05)

# Original coordinate in Sao Paulo
original = (-23.55, -46.63)
print(f"Original: {original}")

# Add noise to simulate real GPS
noisy = simulator.add_noise(*original)
print(f"With noise: {noisy}")

# Simulate polyline interpolation
polyline = [
    (-23.55, -46.63),
    (-23.56, -46.64),
    (-23.57, -46.65),
]

position_25 = simulator.interpolate_position(polyline, 0.25)
position_50 = simulator.interpolate_position(polyline, 0.50)
position_75 = simulator.interpolate_position(polyline, 0.75)

print("\nRoute interpolation:")
print(f"25%: {position_25}")
print(f"50%: {position_50}")
print(f"75%: {position_75}")

# Calculate heading
heading = simulator.calculate_heading(original, position_50)
print(f"\nHeading: {heading:.1f}°")

# Calculate speed
speed_ms = simulator.calculate_speed(distance_meters=100, time_seconds=10)
speed_kmh = speed_ms * 3.6
print(f"Speed: {speed_ms} m/s ({speed_kmh:.1f} km/h)")

# GPS accuracy
accuracy = simulator.get_gps_accuracy()
print(f"GPS accuracy: {accuracy:.1f}m")

# Simulate dropouts
dropouts = sum(1 for _ in range(100) if simulator.should_dropout())
print(f"\nDropouts in 100 updates: {dropouts} (~5% expected)")
