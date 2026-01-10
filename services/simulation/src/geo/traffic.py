"""Time-of-day traffic multipliers for route duration adjustment."""

import math


class TrafficModel:
    """Adjusts route durations based on time-of-day traffic patterns."""

    # Peak multipliers
    RUSH_HOUR_PEAK = 1.40  # 40% slower during rush hour
    NIGHT_PEAK = 0.85  # 15% faster at night
    BASELINE = 1.0

    # Traffic period definitions (center hour, peak multiplier, half-width)
    MORNING_RUSH = (8.0, RUSH_HOUR_PEAK, 1.0)  # 7-9 AM, peaks at 8 AM
    EVENING_RUSH = (18.0, RUSH_HOUR_PEAK, 1.0)  # 5-7 PM, peaks at 6 PM
    NIGHT_HOURS = (2.0, NIGHT_PEAK, 3.5)  # 10:30 PM - 5:30 AM, peaks at 2 AM

    # Sigmoid steepness (higher = sharper transition)
    STEEPNESS = 8.0

    def get_multiplier(self, hour: float) -> float:
        """Get traffic multiplier for given hour (0-23.99).

        Args:
            hour: Hour of day as float (e.g., 7.5 = 7:30 AM)

        Returns:
            Multiplier to apply to route duration
        """
        # Normalize hour to 0-24 range
        hour = hour % 24

        # Calculate contribution from each traffic period
        morning_effect = self._period_effect(hour, *self.MORNING_RUSH)
        evening_effect = self._period_effect(hour, *self.EVENING_RUSH)
        night_effect = self._night_effect(hour)

        # Combine effects - use max for rush hours, blend in night effect
        rush_multiplier = max(morning_effect, evening_effect)

        # If in night period, use night multiplier; otherwise use rush/baseline
        if night_effect > 0:
            # Blend between night and baseline based on night effect strength
            return self.BASELINE + (self.NIGHT_PEAK - self.BASELINE) * night_effect
        else:
            # Blend between baseline and rush based on rush effect strength
            return (
                self.BASELINE + (self.RUSH_HOUR_PEAK - self.BASELINE) * rush_multiplier
            )

    def _period_effect(
        self, hour: float, center: float, peak: float, half_width: float
    ) -> float:
        """Calculate effect strength for a traffic period using sigmoid smoothing."""
        distance = abs(hour - center)
        if distance > half_width + 1.0:  # Outside influence range
            return 0.0

        # Sigmoid: 1 at center, drops to 0 at edges
        return self._sigmoid(half_width - distance)

    def _night_effect(self, hour: float) -> float:
        """Calculate night period effect, handling midnight wraparound."""
        center = self.NIGHT_HOURS[0]
        half_width = self.NIGHT_HOURS[2]

        # Handle midnight wraparound
        distance = 24 - hour + center if hour > 12 else abs(hour - center)

        if distance > half_width + 1.0:
            return 0.0

        return self._sigmoid(half_width - distance)

    def _sigmoid(self, x: float) -> float:
        """Sigmoid function for smooth transitions."""
        return 1 / (1 + math.exp(-self.STEEPNESS * x))

    def apply_to_duration(self, duration_seconds: float, hour: float) -> float:
        """Apply traffic multiplier to a route duration.

        Args:
            duration_seconds: Base duration from OSRM
            hour: Current simulation hour

        Returns:
            Adjusted duration in seconds
        """
        multiplier = self.get_multiplier(hour)
        return duration_seconds * multiplier
