"""Event filtering for Redis pub/sub visualization."""

from events.schemas import (
    DriverProfileEvent,
    DriverStatusEvent,
    GPSPingEvent,
    RiderProfileEvent,
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

    def should_publish(self, event: object) -> bool:
        """Return True if event should be published to Redis."""
        if isinstance(
            event,
            GPSPingEvent
            | DriverStatusEvent
            | DriverProfileEvent
            | RiderProfileEvent
            | SurgeUpdateEvent,
        ):
            return True

        if isinstance(event, TripEvent):
            return event.event_type not in [
                "trip.offer_sent",
                "trip.offer_expired",
                "trip.offer_rejected",
            ]

        return False

    def transform(self, event: object) -> tuple[
        str,
        DriverUpdateMessage | RiderUpdateMessage | TripUpdateMessage | SurgeUpdateMessage,
    ]:
        """Transform event to (channel, message) for Redis pub/sub."""
        if isinstance(event, GPSPingEvent):
            if event.entity_type == "driver":
                # Infer status: if trip_id present, driver is in an active trip
                # Use en_route_pickup as reasonable default for active trip status
                status = "en_route_pickup" if event.trip_id else "online"
                driver_msg = DriverUpdateMessage(
                    driver_id=event.entity_id,
                    location=event.location,
                    heading=event.heading,
                    status=status,
                    trip_id=event.trip_id,
                    timestamp=event.timestamp,
                )
                return CHANNEL_DRIVER_UPDATES, driver_msg
            else:
                rider_msg = RiderUpdateMessage(
                    rider_id=event.entity_id,
                    location=event.location,
                    trip_id=event.trip_id,
                    timestamp=event.timestamp,
                )
                return CHANNEL_RIDER_UPDATES, rider_msg

        if isinstance(event, TripEvent):
            state = event.event_type.replace("trip.", "")
            trip_msg = TripUpdateMessage(
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
            return CHANNEL_TRIP_UPDATES, trip_msg

        if isinstance(event, DriverStatusEvent):
            status_msg = DriverUpdateMessage(
                driver_id=event.driver_id,
                location=event.location,
                heading=None,
                status=event.new_status,
                trip_id=None,
                timestamp=event.timestamp,
            )
            return CHANNEL_DRIVER_UPDATES, status_msg

        if isinstance(event, SurgeUpdateEvent):
            surge_msg = SurgeUpdateMessage(
                zone_id=event.zone_id,
                previous_multiplier=event.previous_multiplier,
                new_multiplier=event.new_multiplier,
                driver_count=event.available_drivers,
                request_count=event.pending_requests,
                timestamp=event.timestamp,
            )
            return CHANNEL_SURGE_UPDATES, surge_msg

        if isinstance(event, DriverProfileEvent):
            profile_msg = DriverUpdateMessage(
                driver_id=event.driver_id,
                location=event.home_location,
                heading=None,
                status="offline",
                trip_id=None,
                timestamp=event.timestamp,
            )
            return CHANNEL_DRIVER_UPDATES, profile_msg

        if isinstance(event, RiderProfileEvent):
            rider_profile_msg = RiderUpdateMessage(
                rider_id=event.rider_id,
                location=event.home_location,
                trip_id=None,
                timestamp=event.timestamp,
            )
            return CHANNEL_RIDER_UPDATES, rider_profile_msg

        raise ValueError(f"Cannot transform event of type {type(event)}")
