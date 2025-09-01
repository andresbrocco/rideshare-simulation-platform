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
        self, polyline: list[tuple[float, float]], progress: float
    ) -> tuple[float, float]:
        if progress <= 0.0:
            return polyline[0]
        if progress >= 1.0:
            return polyline[-1]

        distances = []
        total_distance = 0.0
        for i in range(len(polyline) - 1):
            d = haversine_distance_m(
                polyline[i][0], polyline[i][1], polyline[i + 1][0], polyline[i + 1][1]
            )
            distances.append(d)
            total_distance += d

        target_distance = total_distance * progress
        accumulated = 0.0

        for i, segment_distance in enumerate(distances):
            if accumulated + segment_distance >= target_distance:
                segment_progress = (target_distance - accumulated) / segment_distance
                return self._interpolate_segment(polyline[i], polyline[i + 1], segment_progress)
            accumulated += segment_distance

        return polyline[-1]

    def calculate_heading(
        self, from_coords: tuple[float, float], to_coords: tuple[float, float]
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
