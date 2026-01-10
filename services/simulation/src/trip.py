"""Trip state machine and models."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TripState(str, Enum):
    """Trip lifecycle states."""

    REQUESTED = "requested"
    OFFER_SENT = "offer_sent"
    OFFER_EXPIRED = "offer_expired"
    OFFER_REJECTED = "offer_rejected"
    MATCHED = "matched"
    DRIVER_EN_ROUTE = "driver_en_route"
    DRIVER_ARRIVED = "driver_arrived"
    STARTED = "started"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    def to_event_type(self) -> str:
        """Convert state to Kafka event type (e.g., 'trip.requested')."""
        return f"trip.{self.value}"


VALID_TRANSITIONS: dict[TripState, set[TripState]] = {
    TripState.REQUESTED: {TripState.OFFER_SENT, TripState.CANCELLED},
    TripState.OFFER_SENT: {
        TripState.OFFER_EXPIRED,
        TripState.OFFER_REJECTED,
        TripState.MATCHED,
        TripState.CANCELLED,
    },
    TripState.OFFER_EXPIRED: {TripState.OFFER_SENT, TripState.CANCELLED},
    TripState.OFFER_REJECTED: {TripState.OFFER_SENT, TripState.CANCELLED},
    TripState.MATCHED: {TripState.DRIVER_EN_ROUTE, TripState.CANCELLED},
    TripState.DRIVER_EN_ROUTE: {TripState.DRIVER_ARRIVED, TripState.CANCELLED},
    TripState.DRIVER_ARRIVED: {TripState.STARTED, TripState.CANCELLED},
    TripState.STARTED: {TripState.COMPLETED},
    TripState.COMPLETED: set(),
    TripState.CANCELLED: set(),
}


class Trip(BaseModel):
    """Trip with state machine logic."""

    trip_id: str
    rider_id: str
    driver_id: str | None = None
    state: TripState = Field(default=TripState.REQUESTED)
    pickup_location: tuple[float, float]
    dropoff_location: tuple[float, float]
    pickup_zone_id: str
    dropoff_zone_id: str
    surge_multiplier: float
    fare: float
    offer_sequence: int = Field(default=0)
    cancelled_by: Literal["rider", "driver", "system"] | None = None
    cancellation_reason: str | None = None
    cancellation_stage: str | None = None
    requested_at: datetime | None = None
    matched_at: datetime | None = None
    driver_arrived_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    # Route coordinates for visualization (not persisted to database)
    route: list[tuple[float, float]] | None = None
    pickup_route: list[tuple[float, float]] | None = None  # Driver → pickup route
    # Route progress indices for efficient frontend updates
    route_progress_index: int = 0
    pickup_route_progress_index: int = 0

    def transition_to(self, new_state: TripState) -> None:
        """Transition to a new state with validation."""
        if self.state in {TripState.COMPLETED, TripState.CANCELLED}:
            raise ValueError(
                f"Cannot transition from terminal state {self.state.value}"
            )

        if new_state not in VALID_TRANSITIONS[self.state]:
            raise ValueError(
                f"Invalid transition from {self.state.value} to {new_state.value}"
            )

        self.state = new_state

        if new_state == TripState.OFFER_SENT:
            self.offer_sequence += 1

    def cancel(
        self,
        by: Literal["rider", "driver", "system"],
        reason: str,
        stage: str,
    ) -> None:
        """Cancel the trip with metadata."""
        self.cancelled_by = by
        self.cancellation_reason = reason
        self.cancellation_stage = stage
        self.state = TripState.CANCELLED
