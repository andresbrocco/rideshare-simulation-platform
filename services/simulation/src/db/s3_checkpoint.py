"""S3-based checkpoint manager for simulation state persistence."""

import gzip
import json
import logging
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError

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
