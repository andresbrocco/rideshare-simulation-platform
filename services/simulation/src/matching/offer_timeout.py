from collections.abc import Callable, Generator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import simpy

if TYPE_CHECKING:
    from trip import Trip


@dataclass
class PendingOffer:
    trip: "Trip"
    driver_id: str
    offer_sequence: int
    timeout_process: simpy.Process


class OfferTimeoutManager:
    """Pure SimPy timer that fires a callback when an offer expires.

    All side effects (Kafka emission, state transitions, driver release) are
    handled by the callback — typically ``MatchingServer._handle_offer_expired``.
    """

    def __init__(
        self,
        env: simpy.Environment,
        timeout_seconds: int = 10,
        on_expire: Callable[[str, str], None] | None = None,
    ) -> None:
        self.env = env
        self.timeout_seconds = timeout_seconds
        self._on_expire = on_expire
        self.pending_offers: dict[str, PendingOffer] = {}

    def start_offer_timeout(self, trip: "Trip", driver_id: str, offer_sequence: int) -> None:
        process = self.env.process(self._timeout_process(trip.trip_id))
        pending_offer = PendingOffer(
            trip=trip,
            driver_id=driver_id,
            offer_sequence=offer_sequence,
            timeout_process=process,
        )
        self.pending_offers[trip.trip_id] = pending_offer

    def _timeout_process(self, trip_id: str) -> Generator[Any]:
        try:
            yield self.env.timeout(self.timeout_seconds)

            if trip_id in self.pending_offers:
                pending_offer = self.pending_offers.pop(trip_id)
                if self._on_expire:
                    self._on_expire(trip_id, pending_offer.driver_id)
        except simpy.Interrupt:
            pass

    def clear_offer(self, trip_id: str, reason: str) -> None:
        if trip_id in self.pending_offers:
            pending_offer = self.pending_offers[trip_id]
            if not pending_offer.timeout_process.triggered:
                pending_offer.timeout_process.interrupt()
            del self.pending_offers[trip_id]

    def invalidate_offer(self, trip_id: str) -> None:
        self.clear_offer(trip_id, "invalidated")
