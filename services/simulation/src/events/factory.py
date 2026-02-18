"""Event factory for creating events with tracing fields."""

from typing import TYPE_CHECKING, Any, TypeVar

from core.correlation import get_current_session_id
from events.schemas import CorrelationMixin

if TYPE_CHECKING:
    from trip import Trip

T = TypeVar("T", bound=CorrelationMixin)


class EventFactory:
    """Factory for creating events with tracing fields populated."""

    @staticmethod
    def create(
        event_class: type[T],
        *,
        session_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        **kwargs: Any,
    ) -> T:
        """Create event with tracing fields.

        Args:
            event_class: The event class to instantiate
            session_id: Pre-fetched session ID to avoid per-event context-var read.
                        Falls back to get_current_session_id() when None.
            correlation_id: Primary correlation ID (e.g., trip_id, driver_id)
            causation_id: ID of event that caused this one
            **kwargs: Additional fields to pass to the event constructor

        Returns:
            Event instance with tracing fields populated
        """
        return event_class(
            session_id=session_id if session_id is not None else get_current_session_id(),
            correlation_id=correlation_id,
            causation_id=causation_id,
            **kwargs,
        )

    @staticmethod
    def create_for_trip(
        event_class: type[T],
        trip: "Trip",
        *,
        session_id: str | None = None,
        update_causation: bool = True,
        **kwargs: Any,
    ) -> T:
        """Create trip event with automatic causation chaining.

        Uses trip_id as correlation_id and the trip's last_event_id as causation_id.
        Optionally updates the trip's last_event_id for causation chaining.

        Args:
            event_class: The event class to instantiate
            trip: The trip to use for correlation/causation IDs
            session_id: Pre-fetched session ID to avoid per-event context-var read.
                        Falls back to get_current_session_id() when None.
            update_causation: If True, update trip.last_event_id with this event's ID
            **kwargs: Additional fields to pass to the event constructor

        Returns:
            Event instance with tracing fields populated
        """
        event = event_class(
            session_id=session_id if session_id is not None else get_current_session_id(),
            correlation_id=trip.trip_id,
            causation_id=trip.last_event_id,
            **kwargs,
        )
        if update_causation:
            # All event classes have event_id field
            trip.last_event_id = str(event.event_id)  # type: ignore[attr-defined]
        return event
