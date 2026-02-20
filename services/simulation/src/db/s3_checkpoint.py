"""S3-based checkpoint manager for simulation state persistence."""

import gzip
import json
import logging
from typing import TYPE_CHECKING, Any

import simpy
from botocore.exceptions import ClientError

from agents.dna import DriverDNA, RiderDNA
from agents.driver_agent import DriverAgent
from agents.rider_agent import RiderAgent
from db.checkpoint import CheckpointError
from db.utils import utc_now

if TYPE_CHECKING:
    from engine import SimulationEngine

logger = logging.getLogger(__name__)

CHECKPOINT_VERSION = "1.0.0"


class S3CheckpointManager:
    """Manages checkpoint creation and recovery using S3 storage.

    Stores simulation state as gzip-compressed JSON in S3, matching the
    same checkpoint format used by the SQLite-based CheckpointManager
    for backend interchangeability.
    """

    def __init__(self, s3_client: Any, bucket_name: str, key_prefix: str) -> None:
        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self.key = f"{key_prefix}/latest.json.gz"

    def save_from_engine(self, engine: "SimulationEngine") -> None:
        """Save complete simulation state from a running engine to S3.

        Serializes engine state, compresses with gzip, and writes to S3.
        Checkpoint format matches the SQLite version for compatibility.
        """
        from trip import TripState

        # Collect driver data with full runtime state
        drivers = []
        for driver in engine._active_drivers.values():
            drivers.append(
                {
                    "id": driver.driver_id,
                    "dna": driver.dna.model_dump(),
                    "location": driver._location or driver.dna.home_location,
                    "status": driver._status,
                    "active_trip": driver._active_trip,
                    "rating": driver._current_rating,
                    "rating_count": driver._rating_count,
                }
            )

        # Collect rider data with full runtime state
        riders = []
        for rider in engine._active_riders.values():
            riders.append(
                {
                    "id": rider.rider_id,
                    "dna": rider.dna.model_dump(),
                    "location": rider._location or rider.dna.home_location,
                    "status": rider._status,
                    "active_trip": rider._active_trip,
                    "rating": rider._current_rating,
                    "rating_count": rider._rating_count,
                }
            )

        # Count in-flight trips to determine checkpoint type
        active_trips = engine._matching_server.get_active_trips()
        in_flight_count = len(
            [t for t in active_trips if t.state not in (TripState.COMPLETED, TripState.CANCELLED)]
        )
        checkpoint_type = "graceful" if in_flight_count == 0 else "crash"

        # Collect surge multipliers
        surge_data: dict[str, float] = {}
        if (
            hasattr(engine._matching_server, "_surge_calculator")
            and engine._matching_server._surge_calculator
        ):
            calculator = engine._matching_server._surge_calculator
            if hasattr(calculator, "_zone_multipliers"):
                surge_data = dict(calculator._zone_multipliers)

        # Collect reserved drivers
        reserved_drivers: list[str] = []
        if hasattr(engine._matching_server, "_reserved_drivers"):
            reserved_drivers = list(engine._matching_server._reserved_drivers)

        # Build checkpoint structure (matches SQLite format)
        checkpoint = {
            "version": CHECKPOINT_VERSION,
            "created_at": utc_now().isoformat(),
            "metadata": {
                "current_time": engine._env.now,
                "speed_multiplier": engine._speed_multiplier,
                "status": engine._state.value,
                "checkpoint_type": checkpoint_type,
                "in_flight_trips": in_flight_count,
            },
            "drivers": drivers,
            "riders": riders,
            "trips": [],
            "route_cache": {},
            "surge_multipliers": surge_data,
            "reserved_drivers": reserved_drivers,
        }

        # Gzip compress and write to S3
        body = gzip.compress(json.dumps(checkpoint).encode("utf-8"))
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=self.key,
            Body=body,
            ContentType="application/json",
            ContentEncoding="gzip",
        )

        logger.info(
            "Checkpoint saved to S3: s3://%s/%s, time=%.1fs, "
            "drivers=%d, riders=%d, in_flight=%d",
            self.bucket_name,
            self.key,
            engine._env.now,
            len(drivers),
            len(riders),
            in_flight_count,
        )

    def load_checkpoint(self) -> dict[str, Any] | None:
        """Load checkpoint from S3 and decompress.

        Returns:
            Checkpoint data dictionary, or None if no checkpoint exists.
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=self.key)
            compressed_data = response["Body"].read()
            decompressed = gzip.decompress(compressed_data)
            data: dict[str, Any] = json.loads(decompressed)
            return data
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.info(
                    "No checkpoint found at s3://%s/%s",
                    self.bucket_name,
                    self.key,
                )
                return None
            raise

    def has_checkpoint(self) -> bool:
        """Check if a checkpoint exists in S3 using HEAD request.

        Uses head_object instead of get_object to avoid downloading
        the full checkpoint data just for an existence check.
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=self.key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return False
            raise

    def restore_to_engine(self, engine: "SimulationEngine") -> None:
        """Restore simulation state from S3 checkpoint into an engine.

        Rebuilds all agents and matching server state from the persisted
        checkpoint data. S3 format stores drivers/riders at top level
        (not nested under 'agents' like SQLite).

        Raises:
            CheckpointError: If no checkpoint exists or restoration fails
        """
        checkpoint = self.load_checkpoint()
        if checkpoint is None:
            raise CheckpointError("No checkpoint found in S3")

        metadata = checkpoint["metadata"]
        version = checkpoint.get("version", "1.0.0")

        if version != CHECKPOINT_VERSION:
            logger.warning("Checkpoint version mismatch: %s vs %s", version, CHECKPOINT_VERSION)

        # Restore simulation time by creating a new environment with initial time
        initial_time = metadata["current_time"]
        engine._env = simpy.Environment(initial_time=initial_time)
        engine._speed_multiplier = metadata["speed_multiplier"]

        # Update matching server's environment reference
        if hasattr(engine._matching_server, "_env"):
            engine._matching_server._env = engine._env

        # Extract shared dependencies from agent factory for restored agents
        registry_manager = None
        zone_loader = None
        osrm_client = None
        surge_calculator = None
        if hasattr(engine, "_agent_factory") and engine._agent_factory:
            registry_manager = getattr(engine._agent_factory, "_registry_manager", None)
            zone_loader = getattr(engine._agent_factory, "_zone_loader", None)
            osrm_client = getattr(engine._agent_factory, "_osrm_client", None)
            surge_calculator = getattr(engine._agent_factory, "_surge_calculator", None)

        # S3 format: drivers/riders at top level (not nested under 'agents')
        driver_list = checkpoint.get("drivers", [])
        rider_list = checkpoint.get("riders", [])

        # Restore drivers
        restored_drivers = 0
        failed_drivers = 0
        for driver_data in driver_list:
            try:
                driver_dna = DriverDNA.model_validate(driver_data["dna"])
                has_active_trip = driver_data["active_trip"] is not None
                is_online_idle = driver_data["status"] == "available" and not has_active_trip

                driver = DriverAgent(
                    driver_id=driver_data["id"],
                    dna=driver_dna,
                    env=engine._env,
                    kafka_producer=engine._kafka_producer,
                    redis_publisher=engine._redis_client,
                    driver_repository=None,
                    registry_manager=registry_manager,
                    zone_loader=zone_loader,
                    simulation_engine=engine,
                    immediate_online=is_online_idle,
                    puppet=False,
                )

                # Restore runtime state
                driver._status = driver_data["status"]
                driver._location = tuple(driver_data["location"])
                driver._active_trip = driver_data["active_trip"]
                driver._current_rating = driver_data["rating"]
                driver._rating_count = driver_data["rating_count"]

                engine._active_drivers[driver.driver_id] = driver
                engine._matching_server.register_driver(driver)

                # Register in AgentRegistryManager for status counts
                if registry_manager:
                    registry_manager.register_driver(driver)
                    if driver_data["status"] != "offline":
                        registry_manager._driver_registry.update_driver_status(
                            driver.driver_id, driver_data["status"]
                        )

                    # Populate geospatial index for non-offline drivers
                    if driver_data["status"] != "offline" and driver_data["location"]:
                        lat, lon = driver_data["location"]
                        zone_id = driver._determine_zone(driver_data["location"])
                        registry_manager._driver_index.add_driver(
                            driver.driver_id, lat, lon, driver_data["status"]
                        )
                        registry_manager._driver_registry.update_driver_location(
                            driver.driver_id, tuple(driver_data["location"])
                        )
                        if zone_id:
                            registry_manager._driver_registry.update_driver_zone(
                                driver.driver_id, zone_id
                            )

                restored_drivers += 1
            except Exception as e:
                logger.error("Failed to restore driver %s: %s", driver_data.get("id"), e)
                failed_drivers += 1

        # Restore riders
        restored_riders = 0
        failed_riders = 0
        for rider_data in rider_list:
            try:
                rider_dna = RiderDNA.model_validate(rider_data["dna"])
                rider = RiderAgent(
                    rider_id=rider_data["id"],
                    dna=rider_dna,
                    env=engine._env,
                    kafka_producer=engine._kafka_producer,
                    redis_publisher=engine._redis_client,
                    rider_repository=None,
                    simulation_engine=engine,
                    zone_loader=zone_loader,
                    osrm_client=osrm_client,
                    surge_calculator=surge_calculator,
                    immediate_first_trip=False,
                    puppet=False,
                )

                # Restore runtime state
                rider._status = rider_data["status"]
                rider._location = tuple(rider_data["location"])
                rider._active_trip = rider_data["active_trip"]
                rider._current_rating = rider_data["rating"]
                rider._rating_count = rider_data["rating_count"]

                engine._active_riders[rider.rider_id] = rider
                restored_riders += 1
            except Exception as e:
                logger.error("Failed to restore rider %s: %s", rider_data.get("id"), e)
                failed_riders += 1

        # Restore surge multipliers from top-level key
        surge_data = checkpoint.get("surge_multipliers", {})
        if (
            surge_data
            and hasattr(engine._matching_server, "_surge_calculator")
            and engine._matching_server._surge_calculator
        ):
            calculator = engine._matching_server._surge_calculator
            if hasattr(calculator, "_zone_multipliers"):
                calculator._zone_multipliers.update(surge_data)

        # Restore reserved drivers from top-level key
        reserved_drivers = checkpoint.get("reserved_drivers", [])
        if reserved_drivers:
            engine._matching_server._reserved_drivers = set(reserved_drivers)

        # Handle crash checkpoint: cancel in-flight trips
        if metadata.get("checkpoint_type") == "crash":
            logger.warning(
                "Restored from crash checkpoint with %d in-flight trips. "
                "These trips will be cancelled to ensure clean state.",
                metadata.get("in_flight_trips", 0),
            )
            if hasattr(engine._matching_server, "_active_trips"):
                for trip in list(engine._matching_server._active_trips.values()):
                    engine._matching_server.cancel_trip(trip.trip_id, "system", "recovery_cleanup")

        # Warn about incomplete restoration
        if failed_drivers or failed_riders:
            logger.warning(
                "Checkpoint restore incomplete: %d drivers and %d riders failed to restore",
                failed_drivers,
                failed_riders,
            )

        if registry_manager:
            index_count = len(registry_manager._driver_index._driver_locations)
            logger.info(
                "Restored agent summary: %d drivers in geospatial index, %d riders",
                index_count,
                restored_riders,
            )

        logger.info(
            "S3 checkpoint restored: time=%.1fs, drivers=%d, riders=%d",
            initial_time,
            restored_drivers,
            restored_riders,
        )
