"""Per-agent statistics tracking.

These dataclasses track session-only statistics for drivers and riders.
Statistics reset when the simulation restarts.
"""

from dataclasses import dataclass


@dataclass
class DriverStatistics:
    """Statistics tracked for each driver during a simulation session."""

    # Trip statistics
    trips_completed: int = 0
    trips_cancelled: int = 0

    # Offer statistics
    offers_received: int = 0
    offers_accepted: int = 0
    offers_rejected: int = 0
    offers_expired: int = 0

    # Earnings (BRL)
    total_earnings: float = 0.0

    # Performance metrics (for computing averages)
    total_pickup_time_seconds: float = 0.0
    total_trip_duration_seconds: float = 0.0

    # Ratings given to riders
    total_rating_given: float = 0.0
    ratings_given_count: int = 0

    def record_offer_received(self) -> None:
        """Record that an offer was sent to this driver."""
        self.offers_received += 1

    def record_offer_accepted(self) -> None:
        """Record that this driver accepted an offer."""
        self.offers_accepted += 1

    def record_offer_rejected(self) -> None:
        """Record that this driver rejected an offer."""
        self.offers_rejected += 1

    def record_offer_expired(self) -> None:
        """Record that an offer to this driver expired."""
        self.offers_expired += 1

    def record_trip_completed(
        self, fare: float, pickup_time_seconds: float, trip_duration_seconds: float
    ) -> None:
        """Record a completed trip with earnings and timing data."""
        self.trips_completed += 1
        self.total_earnings += fare
        self.total_pickup_time_seconds += pickup_time_seconds
        self.total_trip_duration_seconds += trip_duration_seconds

    def record_trip_cancelled(self) -> None:
        """Record that a trip was cancelled after matching."""
        self.trips_cancelled += 1

    def record_rating_given(self, rating: float) -> None:
        """Record a rating given to a rider."""
        self.total_rating_given += rating
        self.ratings_given_count += 1

    @property
    def cancellation_rate(self) -> float:
        """Percentage of matched trips that were cancelled."""
        total = self.trips_completed + self.trips_cancelled
        return (self.trips_cancelled / total * 100) if total > 0 else 0.0

    @property
    def acceptance_rate(self) -> float:
        """Percentage of offers that were accepted."""
        if self.offers_received == 0:
            return 0.0
        return self.offers_accepted / self.offers_received * 100

    @property
    def rejection_rate(self) -> float:
        """Percentage of offers that were rejected."""
        if self.offers_received == 0:
            return 0.0
        return self.offers_rejected / self.offers_received * 100

    @property
    def expiration_rate(self) -> float:
        """Percentage of offers that expired."""
        if self.offers_received == 0:
            return 0.0
        return self.offers_expired / self.offers_received * 100

    @property
    def avg_fare(self) -> float:
        """Average fare per completed trip."""
        if self.trips_completed == 0:
            return 0.0
        return self.total_earnings / self.trips_completed

    @property
    def avg_pickup_time_seconds(self) -> float:
        """Average time from match to pickup in seconds."""
        if self.trips_completed == 0:
            return 0.0
        return self.total_pickup_time_seconds / self.trips_completed

    @property
    def avg_trip_duration_minutes(self) -> float:
        """Average trip duration in minutes."""
        if self.trips_completed == 0:
            return 0.0
        return (self.total_trip_duration_seconds / self.trips_completed) / 60

    @property
    def avg_rating_given(self) -> float:
        """Average rating given to riders."""
        if self.ratings_given_count == 0:
            return 0.0
        return self.total_rating_given / self.ratings_given_count


@dataclass
class RiderStatistics:
    """Statistics tracked for each rider during a simulation session."""

    # Trip statistics
    trips_completed: int = 0
    trips_cancelled: int = 0
    trips_requested: int = 0
    requests_timed_out: int = 0

    # Spending (BRL)
    total_spent: float = 0.0

    # Wait time metrics (for computing averages)
    total_wait_time_seconds: float = 0.0  # Time from request to match
    total_pickup_wait_seconds: float = 0.0  # Time from match to pickup

    # Ratings given to drivers
    total_rating_given: float = 0.0
    ratings_given_count: int = 0

    # Surge tracking
    surge_trips: int = 0

    def record_trip_requested(self) -> None:
        """Record that this rider requested a trip."""
        self.trips_requested += 1

    def record_trip_completed(
        self,
        fare: float,
        wait_time_seconds: float,
        pickup_wait_seconds: float,
        had_surge: bool,
    ) -> None:
        """Record a completed trip with spending and timing data."""
        self.trips_completed += 1
        self.total_spent += fare
        self.total_wait_time_seconds += wait_time_seconds
        self.total_pickup_wait_seconds += pickup_wait_seconds
        if had_surge:
            self.surge_trips += 1

    def record_trip_cancelled(self) -> None:
        """Record that a trip was cancelled."""
        self.trips_cancelled += 1

    def record_request_timed_out(self) -> None:
        """Record that a trip request timed out (patience exceeded)."""
        self.requests_timed_out += 1

    def record_rating_given(self, rating: float) -> None:
        """Record a rating given to a driver."""
        self.total_rating_given += rating
        self.ratings_given_count += 1

    @property
    def cancellation_rate(self) -> float:
        """Percentage of requested trips that were cancelled."""
        if self.trips_requested == 0:
            return 0.0
        return self.trips_cancelled / self.trips_requested * 100

    @property
    def avg_fare(self) -> float:
        """Average fare per completed trip."""
        if self.trips_completed == 0:
            return 0.0
        return self.total_spent / self.trips_completed

    @property
    def avg_wait_time_seconds(self) -> float:
        """Average time from request to match in seconds."""
        if self.trips_completed == 0:
            return 0.0
        return self.total_wait_time_seconds / self.trips_completed

    @property
    def avg_pickup_wait_seconds(self) -> float:
        """Average time from match to pickup in seconds."""
        if self.trips_completed == 0:
            return 0.0
        return self.total_pickup_wait_seconds / self.trips_completed

    @property
    def avg_rating_given(self) -> float:
        """Average rating given to drivers."""
        if self.ratings_given_count == 0:
            return 0.0
        return self.total_rating_given / self.ratings_given_count

    @property
    def surge_trips_percentage(self) -> float:
        """Percentage of completed trips that had surge pricing."""
        if self.trips_completed == 0:
            return 0.0
        return self.surge_trips / self.trips_completed * 100
