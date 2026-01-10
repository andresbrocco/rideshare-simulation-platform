"""Trip repository for CRUD operations with state tracking."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trip import Trip as TripDomain
from trip import TripState

from ..schema import Trip
from ..utils import utc_now

TERMINAL_STATES = {TripState.COMPLETED.value, TripState.CANCELLED.value}


class TripRepository:
    """Repository for trip CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        trip_id: str,
        rider_id: str,
        pickup_location: tuple[float, float],
        dropoff_location: tuple[float, float],
        pickup_zone_id: str,
        dropoff_zone_id: str,
        surge_multiplier: float,
        fare: float,
    ) -> None:
        """Create a new trip in REQUESTED state."""
        pickup_lat, pickup_lon = pickup_location
        dropoff_lat, dropoff_lon = dropoff_location
        now = utc_now()

        trip = Trip(
            trip_id=trip_id,
            rider_id=rider_id,
            state=TripState.REQUESTED.value,
            pickup_location=f"{pickup_lat},{pickup_lon}",
            dropoff_location=f"{dropoff_lat},{dropoff_lon}",
            pickup_zone_id=pickup_zone_id,
            dropoff_zone_id=dropoff_zone_id,
            surge_multiplier=surge_multiplier,
            fare=fare,
            offer_sequence=0,
            requested_at=now,
        )
        self.session.add(trip)

    def get(self, trip_id: str) -> TripDomain | None:
        """Get trip by ID, returning domain model."""
        trip = self.session.get(Trip, trip_id)
        if trip is None:
            return None
        return self._to_domain(trip)

    def update_state(
        self,
        trip_id: str,
        new_state: TripState,
        driver_id: str | None = None,
        cancelled_by: str | None = None,
        cancellation_reason: str | None = None,
        cancellation_stage: str | None = None,
    ) -> None:
        """Update trip state with appropriate timestamps."""
        trip = self.session.get(Trip, trip_id)
        if trip is None:
            return

        trip.state = new_state.value
        now = utc_now()

        if new_state == TripState.OFFER_SENT:
            trip.offer_sequence += 1
        elif new_state == TripState.MATCHED:
            trip.matched_at = now
            trip.driver_id = driver_id
        elif new_state == TripState.STARTED:
            trip.started_at = now
        elif new_state == TripState.COMPLETED:
            trip.completed_at = now
        elif new_state == TripState.CANCELLED:
            trip.cancelled_by = cancelled_by
            trip.cancellation_reason = cancellation_reason
            trip.cancellation_stage = cancellation_stage

        trip.updated_at = now

    def list_in_flight(self) -> list[TripDomain]:
        """List trips in non-terminal states."""
        stmt = select(Trip).where(Trip.state.notin_(TERMINAL_STATES))
        result = self.session.execute(stmt)
        return [self._to_domain(t) for t in result.scalars().all()]

    def list_by_driver(self, driver_id: str) -> list[TripDomain]:
        """List trips by driver ID."""
        stmt = (
            select(Trip)
            .where(Trip.driver_id == driver_id)
            .order_by(Trip.requested_at.desc())
        )
        result = self.session.execute(stmt)
        return [self._to_domain(t) for t in result.scalars().all()]

    def list_by_rider(self, rider_id: str) -> list[TripDomain]:
        """List trips by rider ID."""
        stmt = (
            select(Trip)
            .where(Trip.rider_id == rider_id)
            .order_by(Trip.requested_at.desc())
        )
        result = self.session.execute(stmt)
        return [self._to_domain(t) for t in result.scalars().all()]

    def list_by_zone(self, pickup_zone_id: str) -> list[TripDomain]:
        """List trips by pickup zone."""
        stmt = (
            select(Trip)
            .where(Trip.pickup_zone_id == pickup_zone_id)
            .order_by(Trip.requested_at.desc())
        )
        result = self.session.execute(stmt)
        return [self._to_domain(t) for t in result.scalars().all()]

    def count_in_flight(self) -> int:
        """Count trips in non-terminal states."""
        stmt = (
            select(func.count())
            .select_from(Trip)
            .where(Trip.state.notin_(TERMINAL_STATES))
        )
        return self.session.execute(stmt).scalar() or 0

    def _to_domain(self, trip: Trip) -> TripDomain:
        """Convert ORM model to domain model."""
        pickup_lat, pickup_lon = map(float, trip.pickup_location.split(","))
        dropoff_lat, dropoff_lon = map(float, trip.dropoff_location.split(","))

        return TripDomain(
            trip_id=trip.trip_id,
            rider_id=trip.rider_id,
            driver_id=trip.driver_id,
            state=TripState(trip.state),
            pickup_location=(pickup_lat, pickup_lon),
            dropoff_location=(dropoff_lat, dropoff_lon),
            pickup_zone_id=trip.pickup_zone_id,
            dropoff_zone_id=trip.dropoff_zone_id,
            surge_multiplier=trip.surge_multiplier,
            fare=trip.fare,
            offer_sequence=trip.offer_sequence,
            cancelled_by=trip.cancelled_by,
            cancellation_reason=trip.cancellation_reason,
            cancellation_stage=trip.cancellation_stage,
            requested_at=trip.requested_at,
            matched_at=trip.matched_at,
            started_at=trip.started_at,
            completed_at=trip.completed_at,
        )
