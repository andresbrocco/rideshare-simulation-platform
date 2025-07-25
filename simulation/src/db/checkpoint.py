"""Checkpoint and recovery manager for simulation state persistence."""

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents.dna import DriverDNA, RiderDNA
from .repositories.driver_repository import DriverRepository
from .repositories.rider_repository import RiderRepository
from .repositories.route_cache_repository import RouteCacheRepository
from .repositories.trip_repository import TripRepository
from .schema import Driver, Rider, SimulationMetadata
from .utils import utc_now

logger = logging.getLogger(__name__)

CHECKPOINT_VERSION = "1.0.0"


class CheckpointManager:
    """Manages checkpoint creation and recovery for simulation state."""

    def __init__(self, session: Session):
        self.session = session
        self.driver_repo = DriverRepository(session)
        self.rider_repo = RiderRepository(session)
        self.trip_repo = TripRepository(session)
        self.route_cache_repo = RouteCacheRepository(session)

    def create_checkpoint(
        self,
        current_time: float,
        speed_multiplier: int,
        status: str,
        drivers: list[tuple[str, DriverDNA]],
        riders: list[tuple[str, RiderDNA]],
        route_cache: dict,
    ) -> None:
        """Create a checkpoint by persisting all simulation state."""
        in_flight = self.trip_repo.count_in_flight()
        checkpoint_type = "graceful" if in_flight == 0 else "crash"

        # Save metadata
        self._save_metadata("current_time", json.dumps(current_time))
        self._save_metadata("speed_multiplier", json.dumps(speed_multiplier))
        self._save_metadata("status", status)
        self._save_metadata("checkpoint_type", checkpoint_type)
        self._save_metadata("in_flight_trips", json.dumps(in_flight))
        self._save_metadata("checkpoint_version", CHECKPOINT_VERSION)
        self._save_metadata("created_at", utc_now().isoformat())

        # Save agents
        if drivers:
            self.driver_repo.batch_create(drivers)
        if riders:
            self.rider_repo.batch_create(riders)

        # Save route cache
        if route_cache:
            routes_list = []
            for cache_key, route_data in route_cache.items():
                parts = cache_key.split("|")
                if len(parts) == 2:
                    origin_h3, dest_h3 = parts
                    routes_list.append(
                        (
                            origin_h3,
                            dest_h3,
                            route_data["distance"],
                            route_data["duration"],
                            route_data.get("polyline"),
                        )
                    )
            if routes_list:
                self.route_cache_repo.bulk_save(routes_list)

    def load_checkpoint(self) -> dict | None:
        """Load checkpoint and restore simulation state."""
        current_time_raw = self._get_metadata("current_time")
        if current_time_raw is None:
            return None

        checkpoint_type = self._get_metadata("checkpoint_type")
        if checkpoint_type == "crash":
            logger.warning(
                "Resuming from dirty checkpoint - potential duplicate events may occur. "
                "Databricks consumers will deduplicate via event_id."
            )

        # Load metadata
        metadata = {
            "current_time": json.loads(current_time_raw),
            "speed_multiplier": json.loads(self._get_metadata("speed_multiplier") or "1"),
            "status": self._get_metadata("status") or "PAUSED",
            "checkpoint_type": checkpoint_type or "graceful",
            "in_flight_trips": json.loads(self._get_metadata("in_flight_trips") or "0"),
        }

        # Load agents
        drivers = self._load_all_drivers()
        riders = self._load_all_riders()

        # Load trips
        all_trips = self._load_all_trips()

        # Load route cache
        route_cache = self.route_cache_repo.bulk_load()

        return {
            "metadata": metadata,
            "agents": {"drivers": drivers, "riders": riders},
            "trips": all_trips,
            "route_cache": route_cache,
        }

    def is_clean_checkpoint(self) -> bool:
        """Check if the checkpoint is clean (no in-flight trips)."""
        checkpoint_type = self._get_metadata("checkpoint_type")
        return checkpoint_type == "graceful"

    def get_checkpoint_info(self) -> dict | None:
        """Get checkpoint metadata without loading full state."""
        current_time_raw = self._get_metadata("current_time")
        if current_time_raw is None:
            return None

        return {
            "current_time": json.loads(current_time_raw),
            "speed_multiplier": json.loads(self._get_metadata("speed_multiplier") or "1"),
            "status": self._get_metadata("status") or "PAUSED",
            "checkpoint_type": self._get_metadata("checkpoint_type") or "graceful",
            "in_flight_trips": json.loads(self._get_metadata("in_flight_trips") or "0"),
            "checkpoint_version": self._get_metadata("checkpoint_version") or CHECKPOINT_VERSION,
            "created_at": self._get_metadata("created_at"),
        }

    def _save_metadata(self, key: str, value: str) -> None:
        """Save or update a metadata key-value pair."""
        existing = self.session.get(SimulationMetadata, key)
        if existing:
            existing.value = value
        else:
            metadata = SimulationMetadata(key=key, value=value)
            self.session.add(metadata)

    def _get_metadata(self, key: str) -> str | None:
        """Get a metadata value by key."""
        metadata = self.session.get(SimulationMetadata, key)
        return metadata.value if metadata else None

    def _load_all_drivers(self) -> list[dict]:
        """Load all drivers with deserialized DNA."""
        stmt = select(Driver)
        result = self.session.execute(stmt)
        drivers = []
        for driver in result.scalars().all():
            dna_dict = json.loads(driver.dna_json)
            lat, lon = map(float, driver.current_location.split(","))
            drivers.append(
                {
                    "id": driver.id,
                    "dna": dna_dict,
                    "location": (lat, lon),
                    "status": driver.status,
                    "active_trip": driver.active_trip,
                    "rating": driver.current_rating,
                    "rating_count": driver.rating_count,
                }
            )
        return drivers

    def _load_all_riders(self) -> list[dict]:
        """Load all riders with deserialized DNA."""
        stmt = select(Rider)
        result = self.session.execute(stmt)
        riders = []
        for rider in result.scalars().all():
            dna_dict = json.loads(rider.dna_json)
            lat, lon = map(float, rider.current_location.split(","))
            riders.append(
                {
                    "id": rider.id,
                    "dna": dna_dict,
                    "location": (lat, lon),
                    "status": rider.status,
                    "active_trip": rider.active_trip,
                    "rating": rider.current_rating,
                    "rating_count": rider.rating_count,
                }
            )
        return riders

    def _load_all_trips(self) -> list:
        """Load all trips (both in-flight and completed)."""
        from ..trip import Trip as TripDomain
        from ..trip import TripState
        from .schema import Trip

        stmt = select(Trip)
        result = self.session.execute(stmt)
        trips = []
        for trip in result.scalars().all():
            pickup_lat, pickup_lon = map(float, trip.pickup_location.split(","))
            dropoff_lat, dropoff_lon = map(float, trip.dropoff_location.split(","))

            domain_trip = TripDomain(
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
            trips.append(domain_trip)
        return trips
