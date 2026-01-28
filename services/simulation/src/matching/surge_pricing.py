from collections.abc import Generator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from events.schemas import SurgeUpdateEvent
from geo.zones import ZoneLoader
from matching.driver_registry import DriverRegistry

if TYPE_CHECKING:
    import simpy

    from kafka.producer import KafkaProducer
    from redis_client.publisher import RedisPublisher


class SurgePricingCalculator:
    def __init__(
        self,
        env: "simpy.Environment",
        zone_loader: ZoneLoader,
        driver_registry: DriverRegistry,
        kafka_producer: "KafkaProducer | None" = None,
        redis_publisher: "RedisPublisher | None" = None,
        update_interval_seconds: int = 60,
    ) -> None:
        self.env = env
        self.zone_loader = zone_loader
        self.driver_registry = driver_registry
        self.kafka_producer = kafka_producer
        self.redis_publisher = redis_publisher
        self.update_interval_seconds = update_interval_seconds

        self.current_surge: dict[str, float] = {}
        self.pending_requests: dict[str, int] = {}

        self.env.process(self._surge_calculation_loop())

    def _surge_calculation_loop(self) -> Generator[Any, Any]:
        while True:
            self._calculate_surge_all_zones()
            yield self.env.timeout(self.update_interval_seconds)

    def _calculate_surge_all_zones(self) -> None:
        zones = self.zone_loader.get_all_zones()
        for zone in zones:
            self._calculate_zone_surge(zone.zone_id)

    def _calculate_zone_surge(self, zone_id: str) -> None:
        pending = self.pending_requests.get(zone_id, 0)
        available = self.driver_registry.get_zone_driver_count(zone_id, "online")

        if available == 0:
            new_multiplier = 2.5 if pending > 0 else 1.0
        else:
            ratio = pending / available
            new_multiplier = self._calculate_multiplier(ratio)

        self._update_zone_surge(zone_id, new_multiplier, available, pending)

    def _calculate_multiplier(self, ratio: float) -> float:
        if ratio <= 1.0:
            return 1.0
        elif ratio <= 2.0:
            return 1.0 + (ratio - 1.0) * 0.5
        elif ratio <= 3.0:
            return 1.5 + (ratio - 2.0) * 1.0
        else:
            return 2.5

    def _update_zone_surge(
        self,
        zone_id: str,
        new_multiplier: float,
        available_drivers: int,
        pending_requests: int,
    ) -> None:
        old_multiplier = self.current_surge.get(zone_id, 1.0)

        if new_multiplier != old_multiplier:
            timestamp = datetime.now(UTC).isoformat()

            if self.kafka_producer:
                event = SurgeUpdateEvent(
                    zone_id=zone_id,
                    timestamp=timestamp,
                    previous_multiplier=old_multiplier,
                    new_multiplier=new_multiplier,
                    available_drivers=available_drivers,
                    pending_requests=pending_requests,
                    calculation_window_seconds=self.update_interval_seconds,
                )
                self.kafka_producer.produce(
                    topic="surge_updates", key=zone_id, value=event
                )

            self.current_surge[zone_id] = new_multiplier

    def get_surge(self, zone_id: str) -> float:
        return self.current_surge.get(zone_id, 1.0)

    def set_pending_requests(self, zone_id: str, count: int) -> None:
        self.pending_requests[zone_id] = count

    def increment_pending_request(self, zone_id: str) -> None:
        """Increment pending request count for a zone.

        Called when a rider requests a trip in this zone.
        """
        self.pending_requests[zone_id] = self.pending_requests.get(zone_id, 0) + 1

    def decrement_pending_request(self, zone_id: str) -> None:
        """Decrement pending request count for a zone.

        Called when a trip is matched, completed, or cancelled.
        """
        if zone_id in self.pending_requests and self.pending_requests[zone_id] > 0:
            self.pending_requests[zone_id] -= 1

    def clear(self) -> None:
        """Clear all surge state for simulation reset."""
        self.current_surge.clear()
        self.pending_requests.clear()
