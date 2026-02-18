import bisect
import math
import random

from geo.distance import haversine_distance_m


class GPSSimulator:
    def __init__(self, noise_meters: float = 10.0, dropout_probability: float = 0.05):
        self.noise_meters = noise_meters
        self.dropout_probability = dropout_probability

    def add_noise(
        self, lat: float, lon: float, max_noise_meters: float = 15.0
    ) -> tuple[float, float]:
        if self.noise_meters == 0:
            return lat, lon

        # Generate Gaussian noise and clamp to max value
        noise_lat = max(
            -max_noise_meters, min(max_noise_meters, random.gauss(0, self.noise_meters))
        )
        noise_lon = max(
            -max_noise_meters, min(max_noise_meters, random.gauss(0, self.noise_meters))
        )

        lat_offset = noise_lat / 111000
        lon_offset = noise_lon / (111000 * math.cos(math.radians(lat)))

        return lat + lat_offset, lon + lon_offset

    def should_dropout(self) -> bool:
        return random.random() < self.dropout_probability

    def interpolate_position(
        self,
        polyline: list[tuple[float, float]],
        progress: float,
        cumulative_distances: list[float] | None = None,
    ) -> tuple[float, float]:
        if progress <= 0.0:
            return polyline[0]
        if progress >= 1.0:
            return polyline[-1]

        if cumulative_distances is None:
            cumulative_distances = precompute_cumulative_distances(polyline)

        if not cumulative_distances:
            return polyline[0]

        total_distance = cumulative_distances[-1]
        target_distance = total_distance * progress

        # bisect_left gives O(log N) segment lookup vs O(N) linear scan
        idx = bisect.bisect_left(cumulative_distances, target_distance)
        idx = min(idx, len(polyline) - 2)

        prev_cumulative = cumulative_distances[idx - 1] if idx > 0 else 0.0
        segment_distance = cumulative_distances[idx] - prev_cumulative

        if segment_distance == 0.0:
            return polyline[idx]

        segment_progress = (target_distance - prev_cumulative) / segment_distance
        return self._interpolate_segment(polyline[idx], polyline[idx + 1], segment_progress)

    @staticmethod
    def calculate_heading(
        from_coords: tuple[float, float], to_coords: tuple[float, float]
    ) -> float:
        lat1, lon1 = math.radians(from_coords[0]), math.radians(from_coords[1])
        lat2, lon2 = math.radians(to_coords[0]), math.radians(to_coords[1])

        dlon = lon2 - lon1

        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

        bearing_rad = math.atan2(y, x)
        bearing_deg = (math.degrees(bearing_rad) + 360) % 360

        return bearing_deg

    def calculate_speed(self, distance_meters: float, time_seconds: float) -> float:
        if time_seconds == 0:
            return 0.0
        return distance_meters / time_seconds

    def get_gps_accuracy(self) -> float:
        base_accuracy = self.noise_meters
        variation = random.uniform(-0.2, 0.2)
        return base_accuracy * (1 + variation)

    def _interpolate_segment(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        progress: float,
    ) -> tuple[float, float]:
        lat = start[0] + (end[0] - start[0]) * progress
        lon = start[1] + (end[1] - start[1]) * progress
        return lat, lon


def precompute_cumulative_distances(polyline: list[tuple[float, float]]) -> list[float]:
    """Precompute cumulative Haversine distances along a polyline.

    Returns a list of length len(polyline) - 1 where entry i is the
    cumulative distance from polyline[0] to polyline[i+1] in meters.
    Returns empty list for polylines shorter than 2 points.
    """
    if len(polyline) < 2:
        return []

    cumulative: list[float] = []
    total = 0.0
    for i in range(len(polyline) - 1):
        d = haversine_distance_m(
            polyline[i][0],
            polyline[i][1],
            polyline[i + 1][0],
            polyline[i + 1][1],
        )
        total += d
        cumulative.append(total)
    return cumulative


def precompute_headings(geometry: list[tuple[float, float]]) -> list[float]:
    """Precompute headings between consecutive polyline points.

    Returns a list of length len(geometry) - 1. Index i gives the heading
    when traveling from geometry[i] to geometry[i+1].
    Returns an empty list if geometry has fewer than 2 points.
    """
    if len(geometry) < 2:
        return []
    return [
        GPSSimulator.calculate_heading(geometry[i], geometry[i + 1])
        for i in range(len(geometry) - 1)
    ]
