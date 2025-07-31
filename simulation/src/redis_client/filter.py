"""Event filtering for Redis pub/sub visualization."""

from events.schemas import (
    DriverStatusEvent,
    GPSPingEvent,
    SurgeUpdateEvent,
    TripEvent,
)
from pubsub.channels import (
    CHANNEL_DRIVER_UPDATES,
    CHANNEL_RIDER_UPDATES,
    CHANNEL_SURGE_UPDATES,
    CHANNEL_TRIP_UPDATES,
    DriverUpdateMessage,
    RiderUpdateMessage,
    SurgeUpdateMessage,
    TripUpdateMessage,
)


class EventFilter:
    """Filters and transforms events for real-time visualization."""

    def should_publish(self, event) -> bool:
        """Return True if event should be published to Redis."""
        if isinstance(event, GPSPingEvent | DriverStatusEvent | SurgeUpdateEvent):
            return True

        if isinstance(event, TripEvent):
            return event.event_type not in [
                "trip.offer_sent",
                "trip.offer_expired",
                "trip.offer_rejected",
            ]

        return False

    def transform(self, event) -> tuple[str, object]:
        """Transform event to (channel, message) for Redis pub/sub."""
        if isinstance(event, GPSPingEvent):
            if event.entity_type == "driver":
                status = "busy" if event.trip_id else "online"
                message = DriverUpdateMessage(
                    driver_id=event.entity_id,
                    location=event.location,
                    heading=event.heading,
                    status=status,
                    trip_id=event.trip_id,
                    timestamp=event.timestamp,
                )
                return CHANNEL_DRIVER_UPDATES, message
            else:
                message = RiderUpdateMessage(
                    rider_id=event.entity_id,
                    location=event.location,
                    trip_id=event.trip_id,
                    timestamp=event.timestamp,
                )
                return CHANNEL_RIDER_UPDATES, message

        if isinstance(event, TripEvent):
            state = event.event_type.replace("trip.", "")
            message = TripUpdateMessage(
                trip_id=event.trip_id,
                state=state,
                pickup=event.pickup_location,
                dropoff=event.dropoff_location,
                driver_id=event.driver_id,
                rider_id=event.rider_id,
                fare=event.fare,
                surge_multiplier=event.surge_multiplier,
                timestamp=event.timestamp,
            )
            return CHANNEL_TRIP_UPDATES, message

        if isinstance(event, DriverStatusEvent):
            message = DriverUpdateMessage(
                driver_id=event.driver_id,
                location=event.location,
                heading=None,
                status=event.new_status,
                trip_id=None,
                timestamp=event.timestamp,
            )
            return CHANNEL_DRIVER_UPDATES, message

        if isinstance(event, SurgeUpdateEvent):
            message = SurgeUpdateMessage(
                zone_id=event.zone_id,
                previous_multiplier=event.previous_multiplier,
                new_multiplier=event.new_multiplier,
                driver_count=event.available_drivers,
                request_count=event.pending_requests,
                timestamp=event.timestamp,
            )
            return CHANNEL_SURGE_UPDATES, message

        raise ValueError(f"Cannot transform event of type {type(event)}")
