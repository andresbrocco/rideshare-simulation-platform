"""Checkpoint and recovery manager for simulation state persistence."""

import json
import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents.dna import DriverDNA, RiderDNA
from .repositories.driver_repository import DriverRepository
from .repositories.rider_repository import RiderRepository
from .repositories.route_cache_repository import RouteCacheRepository
from .repositories.trip_repository import TripRepository
from .schema import Driver, Rider, SimulationMetadata
from .utils import utc_now

if TYPE_CHECKING:
    from ..engine import SimulationEngine

logger = logging.getLogger(__name__)

CHECKPOINT_VERSION = "1.0.0"


class CheckpointError(Exception):
    """Raised when checkpoint operations fail."""

    pass


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

    def save_from_engine(self, engine: "SimulationEngine") -> None:
        """Save complete simulation state from a running engine.

        This captures all agent states including DNA, active trips,
        and matching server state for later restoration.
        """
        from ..trip import TripState

        # Collect driver data
        drivers = []
        for driver in engine._active_drivers.values():
            drivers.append((driver.driver_id, driver.dna))

        # Collect rider data
        riders = []
        for rider in engine._active_riders.values():
            riders.append((rider.rider_id, rider.dna))

        # Get in-flight trips count
        in_flight_trips = engine._matching_server.get_active_trips()
        in_flight_count = len(
            [
                t
                for t in in_flight_trips
                if t.state not in (TripState.COMPLETED, TripState.CANCELLED)
            ]
        )

        # Save checkpoint with engine state
        self.create_checkpoint(
            current_time=engine._env.now,
            speed_multiplier=engine._speed_multiplier,
            status=engine._state.value,
            drivers=drivers,
            riders=riders,
            route_cache={},  # Route cache is persisted separately
        )

        # Also save surge multipliers if available
        if (
            hasattr(engine._matching_server, "_surge_calculator")
            and engine._matching_server._surge_calculator
        ):
            surge_data = {}
            calculator = engine._matching_server._surge_calculator
            if hasattr(calculator, "_zone_multipliers"):
                surge_data = dict(calculator._zone_multipliers)
            self._save_metadata("surge_multipliers", json.dumps(surge_data))

        # Save reserved drivers
        if hasattr(engine._matching_server, "_reserved_drivers"):
            reserved = list(engine._matching_server._reserved_drivers)
            self._save_metadata("reserved_drivers", json.dumps(reserved))

        self.session.commit()
        logger.info(
            f"Checkpoint saved: time={engine._env.now:.1f}s, "
            f"drivers={len(drivers)}, riders={len(riders)}, "
            f"in_flight_trips={in_flight_count}"
        )

    def has_checkpoint(self) -> bool:
        """Check if a checkpoint exists."""
        return self._get_metadata("current_time") is not None

    def restore_to_engine(self, engine: "SimulationEngine") -> None:
        """Restore simulation state from checkpoint into an engine.

        This rebuilds all agents, trips, and matching server state
        from the persisted checkpoint data.

        Raises:
            CheckpointError: If no checkpoint exists or restoration fails
        """
        import simpy

        from ..agents.driver_agent import DriverAgent
        from ..agents.rider_agent import RiderAgent
        from ..trip import TripState

        checkpoint = self.load_checkpoint()
        if checkpoint is None:
            raise CheckpointError("No checkpoint found")

        metadata = checkpoint["metadata"]
        version = self._get_metadata("checkpoint_version") or "1.0.0"

        if version != CHECKPOINT_VERSION:
            logger.warning(f"Checkpoint version mismatch: {version} vs {CHECKPOINT_VERSION}")

        # Restore simulation time by creating a new environment with initial time
        initial_time = metadata["current_time"]
        engine._env = simpy.Environment(initial_time=initial_time)
        engine._speed_multiplier = metadata["speed_multiplier"]

        # Update matching server's environment reference
        if hasattr(engine._matching_server, "_env"):
            engine._matching_server._env = engine._env

        # Restore drivers
        restored_drivers = 0
        for driver_data in checkpoint["agents"]["drivers"]:
            try:
                driver_dna = DriverDNA.model_validate(driver_data["dna"])
                driver = DriverAgent(
                    driver_id=driver_data["id"],
                    dna=driver_dna,
                    env=engine._env,
                    kafka_producer=engine._kafka_producer,
                    redis_publisher=engine._redis_client,
                    driver_repository=None,  # Skip DB write on restore
                    registry_manager=None,  # Will be set up after
                    simulation_engine=engine,
                    immediate_online=False,
                    puppet=False,
                )

                # Restore runtime state
                driver._status = driver_data["status"]
                driver._location = driver_data["location"]
                driver._active_trip = driver_data["active_trip"]
                driver._current_rating = driver_data["rating"]
                driver._rating_count = driver_data["rating_count"]

                engine._active_drivers[driver.driver_id] = driver
                engine._matching_server.register_driver(driver)
                restored_drivers += 1
            except Exception as e:
                logger.error(f"Failed to restore driver {driver_data.get('id')}: {e}")

        # Restore riders
        restored_riders = 0
        for rider_data in checkpoint["agents"]["riders"]:
            try:
                rider_dna = RiderDNA.model_validate(rider_data["dna"])
                rider = RiderAgent(
                    rider_id=rider_data["id"],
                    dna=rider_dna,
                    env=engine._env,
                    kafka_producer=engine._kafka_producer,
                    redis_publisher=engine._redis_client,
                    rider_repository=None,  # Skip DB write on restore
                    simulation_engine=engine,
                    immediate_first_trip=False,
                    puppet=False,
                )

                # Restore runtime state
                rider._status = rider_data["status"]
                rider._location = rider_data["location"]
                rider._active_trip = rider_data["active_trip"]
                rider._current_rating = rider_data["rating"]
                rider._rating_count = rider_data["rating_count"]

                engine._active_riders[rider.rider_id] = rider
                restored_riders += 1
            except Exception as e:
                logger.error(f"Failed to restore rider {rider_data.get('id')}: {e}")

        # Restore active trips
        restored_trips = 0
        for trip in checkpoint["trips"]:
            if trip.state not in (TripState.COMPLETED, TripState.CANCELLED):
                engine._matching_server._active_trips[trip.trip_id] = trip
                restored_trips += 1

        # Restore surge multipliers
        surge_data_raw = self._get_metadata("surge_multipliers")
        if surge_data_raw:
            surge_data = json.loads(surge_data_raw)
            if (
                hasattr(engine._matching_server, "_surge_calculator")
                and engine._matching_server._surge_calculator
            ):
                calculator = engine._matching_server._surge_calculator
                if hasattr(calculator, "_zone_multipliers"):
                    calculator._zone_multipliers.update(surge_data)

        # Restore reserved drivers
        reserved_raw = self._get_metadata("reserved_drivers")
        if reserved_raw:
            reserved = json.loads(reserved_raw)
            engine._matching_server._reserved_drivers = set(reserved)

        # Handle dirty checkpoint warning
        if metadata["checkpoint_type"] == "crash":
            logger.warning(
                f"Restored from dirty checkpoint with {metadata['in_flight_trips']} in-flight trips. "
                "These trips will be cancelled to ensure clean state."
            )
            # Cancel any in-flight trips to prevent inconsistent state
            for trip in list(engine._matching_server._active_trips.values()):
                engine._matching_server.cancel_trip(trip.trip_id, "system", "recovery_cleanup")

        logger.info(
            f"Checkpoint restored: time={initial_time:.1f}s, "
            f"drivers={restored_drivers}, riders={restored_riders}, "
            f"active_trips={restored_trips}"
        )
