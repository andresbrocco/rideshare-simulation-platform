"""Unit tests for S3CheckpointManager with mocked S3 client."""

import gzip
import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from botocore.exceptions import ClientError

from src.agents.dna import DriverDNA, RiderDNA, ShiftPreference
from src.db.s3_checkpoint import CheckpointError, S3CheckpointManager
from src.trip import TripState


@pytest.fixture
def mock_s3_client():
    """Mock boto3 S3 client for unit tests."""
    return MagicMock()


@pytest.fixture
def s3_checkpoint_manager(mock_s3_client):
    """S3CheckpointManager instance with mocked S3 client."""
    return S3CheckpointManager(
        s3_client=mock_s3_client, bucket_name="test-checkpoint-bucket", key_prefix="sim-checkpoints"
    )


@pytest.fixture
def mock_engine():
    """Mock SimulationEngine with minimal state for testing."""
    engine = Mock()
    engine._env = Mock()
    engine._env.now = 12345.6
    engine._state = Mock()
    engine._state.value = "PAUSED"
    engine._speed_multiplier = 10
    engine._active_drivers = {}
    engine._active_riders = {}
    engine._matching_server = Mock()
    engine._matching_server.get_active_trips = Mock(return_value=[])
    engine._matching_server._surge_calculator = Mock()
    engine._matching_server._surge_calculator._zone_multipliers = {"BVI": 1.5, "PIN": 1.2}
    engine._matching_server._reserved_drivers = set()
    return engine


@pytest.fixture
def sample_driver_dna():
    """Sample driver DNA for testing checkpoint serialization."""
    return DriverDNA(
        acceptance_rate=0.85,
        cancellation_tendency=0.05,
        service_quality=0.9,
        response_time=5.0,
        min_rider_rating=3.5,
        surge_acceptance_modifier=1.5,
        home_location=(-23.55, -46.63),
        shift_preference=ShiftPreference.MORNING,
        avg_hours_per_day=8,
        avg_days_per_week=5,
        vehicle_make="Toyota",
        vehicle_model="Corolla",
        vehicle_year=2020,
        license_plate="ABC-1234",
        first_name="John",
        last_name="Doe",
        email="john.doe@test.com",
        phone="+5511999990001",
    )


@pytest.fixture
def sample_rider_dna():
    """Sample rider DNA for testing checkpoint serialization."""
    return RiderDNA(
        behavior_factor=0.75,
        patience_threshold=180,
        max_surge_multiplier=2.0,
        avg_rides_per_week=5,
        frequent_destinations=[
            {"coordinates": (-23.565, -46.695), "weight": 0.6},
            {"coordinates": (-23.55, -46.635), "weight": 0.4},
        ],
        home_location=(-23.56, -46.65),
        first_name="Jane",
        last_name="Smith",
        email="jane.smith@test.com",
        phone="+5511988880001",
        payment_method_type="credit_card",
        payment_method_masked="**** 1234",
    )


@pytest.mark.unit
class TestS3CheckpointSave:
    """Tests for saving checkpoints to S3."""

    @patch("src.db.s3_checkpoint.utc_now")
    def test_save_checkpoint_gzip_compressed(
        self, mock_utc_now, s3_checkpoint_manager, mock_s3_client, mock_engine, sample_driver_dna
    ):
        """Verify S3 put_object with gzip compression and proper headers."""
        mock_utc_now.return_value = datetime(2026, 2, 14, 12, 0, 0)

        driver = Mock()
        driver.driver_id = "driver-001"
        driver.dna = sample_driver_dna
        driver._location = (-23.55, -46.63)
        driver._status = "available"
        driver._active_trip = None
        driver._current_rating = 4.8
        driver._rating_count = 100

        mock_engine._active_drivers = {"driver-001": driver}

        s3_checkpoint_manager.save_from_engine(mock_engine)

        mock_s3_client.put_object.assert_called_once()
        call_kwargs = mock_s3_client.put_object.call_args.kwargs

        assert call_kwargs["Bucket"] == "test-checkpoint-bucket"
        assert call_kwargs["Key"] == "sim-checkpoints/latest.json.gz"
        assert call_kwargs["ContentType"] == "application/json"
        assert call_kwargs["ContentEncoding"] == "gzip"

        compressed_body = call_kwargs["Body"]
        decompressed = gzip.decompress(compressed_body)
        checkpoint_data = json.loads(decompressed)

        assert checkpoint_data["version"] == "1.0.0"
        assert checkpoint_data["created_at"] == "2026-02-14T12:00:00"
        assert checkpoint_data["metadata"]["current_time"] == 12345.6
        assert checkpoint_data["metadata"]["speed_multiplier"] == 10
        assert checkpoint_data["metadata"]["status"] == "PAUSED"
        assert len(checkpoint_data["drivers"]) == 1

    def test_load_checkpoint_decompresses(self, s3_checkpoint_manager, mock_s3_client):
        """Load and decompress gzipped checkpoint, verify all keys present."""
        checkpoint_data = {
            "version": "1.0.0",
            "created_at": "2026-02-14T12:00:00",
            "metadata": {
                "current_time": 12345.6,
                "speed_multiplier": 10,
                "status": "PAUSED",
                "checkpoint_type": "graceful",
                "in_flight_trips": 0,
            },
            "drivers": [],
            "riders": [],
            "trips": [],
            "route_cache": {},
            "surge_multipliers": {},
            "reserved_drivers": [],
        }

        compressed = gzip.compress(json.dumps(checkpoint_data).encode("utf-8"))
        mock_s3_client.get_object.return_value = {"Body": Mock(read=Mock(return_value=compressed))}

        loaded = s3_checkpoint_manager.load_checkpoint()

        assert loaded is not None
        assert loaded["version"] == "1.0.0"
        assert loaded["metadata"]["current_time"] == 12345.6
        assert "drivers" in loaded
        assert "riders" in loaded
        assert "trips" in loaded
        assert "route_cache" in loaded
        assert "surge_multipliers" in loaded
        assert "reserved_drivers" in loaded

    def test_load_checkpoint_returns_none_when_not_found(
        self, s3_checkpoint_manager, mock_s3_client
    ):
        """Handle NoSuchKey gracefully."""
        mock_s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}},
            "GetObject",
        )

        result = s3_checkpoint_manager.load_checkpoint()

        assert result is None

    def test_has_checkpoint_uses_head_request(self, s3_checkpoint_manager, mock_s3_client):
        """Use HEAD not GET, return True/False."""
        mock_s3_client.head_object.return_value = {"ContentLength": 1024}

        assert s3_checkpoint_manager.has_checkpoint() is True
        mock_s3_client.head_object.assert_called_once_with(
            Bucket="test-checkpoint-bucket", Key="sim-checkpoints/latest.json.gz"
        )

        mock_s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
        )

        assert s3_checkpoint_manager.has_checkpoint() is False


@pytest.mark.unit
class TestS3CheckpointFormat:
    """Tests for checkpoint format compatibility."""

    @patch("src.db.s3_checkpoint.utc_now")
    def test_checkpoint_format_matches_sqlite(
        self,
        mock_utc_now,
        s3_checkpoint_manager,
        mock_s3_client,
        mock_engine,
        sample_driver_dna,
        sample_rider_dna,
    ):
        """Compare structure with SQLite version - verify top-level keys match."""
        mock_utc_now.return_value = datetime(2026, 2, 14, 12, 0, 0)

        driver = Mock()
        driver.driver_id = "driver-001"
        driver.dna = sample_driver_dna
        driver._location = (-23.55, -46.63)
        driver._status = "available"
        driver._active_trip = None
        driver._current_rating = 4.8
        driver._rating_count = 100

        rider = Mock()
        rider.rider_id = "rider-001"
        rider.dna = sample_rider_dna
        rider._location = (-23.56, -46.65)
        rider._status = "idle"
        rider._active_trip = None
        rider._current_rating = 4.9
        rider._rating_count = 50

        mock_engine._active_drivers = {"driver-001": driver}
        mock_engine._active_riders = {"rider-001": rider}

        s3_checkpoint_manager.save_from_engine(mock_engine)

        call_kwargs = mock_s3_client.put_object.call_args.kwargs
        compressed_body = call_kwargs["Body"]
        decompressed = gzip.decompress(compressed_body)
        checkpoint_data = json.loads(decompressed)

        expected_keys = {
            "version",
            "created_at",
            "metadata",
            "drivers",
            "riders",
            "trips",
            "route_cache",
            "surge_multipliers",
            "reserved_drivers",
        }
        assert set(checkpoint_data.keys()) == expected_keys

        assert checkpoint_data["metadata"]["checkpoint_type"] in ("graceful", "crash")
        assert isinstance(checkpoint_data["metadata"]["in_flight_trips"], int)
        assert isinstance(checkpoint_data["drivers"], list)
        assert isinstance(checkpoint_data["riders"], list)

        driver_data = checkpoint_data["drivers"][0]
        assert "id" in driver_data
        assert "dna" in driver_data
        assert "location" in driver_data
        assert "status" in driver_data
        assert "active_trip" in driver_data
        assert "rating" in driver_data
        assert "rating_count" in driver_data


@pytest.mark.unit
class TestS3CheckpointType:
    """Tests for graceful vs crash checkpoint detection."""

    @patch("src.db.s3_checkpoint.utc_now")
    def test_graceful_checkpoint_no_in_flight(
        self, mock_utc_now, s3_checkpoint_manager, mock_s3_client, mock_engine
    ):
        """checkpoint_type='graceful' when 0 active trips."""
        mock_utc_now.return_value = datetime(2026, 2, 14, 12, 0, 0)
        mock_engine._matching_server.get_active_trips.return_value = []

        s3_checkpoint_manager.save_from_engine(mock_engine)

        call_kwargs = mock_s3_client.put_object.call_args.kwargs
        compressed_body = call_kwargs["Body"]
        decompressed = gzip.decompress(compressed_body)
        checkpoint_data = json.loads(decompressed)

        assert checkpoint_data["metadata"]["checkpoint_type"] == "graceful"
        assert checkpoint_data["metadata"]["in_flight_trips"] == 0

    @patch("src.db.s3_checkpoint.utc_now")
    def test_crash_checkpoint_with_in_flight(
        self, mock_utc_now, s3_checkpoint_manager, mock_s3_client, mock_engine
    ):
        """checkpoint_type='crash' when active trips exist."""
        mock_utc_now.return_value = datetime(2026, 2, 14, 12, 0, 0)

        trip1 = Mock()
        trip1.state = TripState.DRIVER_ASSIGNED

        trip2 = Mock()
        trip2.state = TripState.IN_TRANSIT

        trip3 = Mock()
        trip3.state = TripState.COMPLETED

        mock_engine._matching_server.get_active_trips.return_value = [trip1, trip2, trip3]

        s3_checkpoint_manager.save_from_engine(mock_engine)

        call_kwargs = mock_s3_client.put_object.call_args.kwargs
        compressed_body = call_kwargs["Body"]
        decompressed = gzip.decompress(compressed_body)
        checkpoint_data = json.loads(decompressed)

        assert checkpoint_data["metadata"]["checkpoint_type"] == "crash"
        assert checkpoint_data["metadata"]["in_flight_trips"] == 2


def _make_s3_checkpoint(
    drivers: list[dict[str, object]] | None = None,
    riders: list[dict[str, object]] | None = None,
    current_time: float = 5000.0,
    speed_multiplier: int = 10,
    checkpoint_type: str = "graceful",
    in_flight_trips: int = 0,
    surge_multipliers: dict[str, float] | None = None,
    reserved_drivers: list[str] | None = None,
) -> dict[str, object]:
    """Build an S3-format checkpoint dict for restore tests."""
    return {
        "version": "1.0.0",
        "created_at": "2026-02-14T12:00:00",
        "metadata": {
            "current_time": current_time,
            "speed_multiplier": speed_multiplier,
            "status": "PAUSED",
            "checkpoint_type": checkpoint_type,
            "in_flight_trips": in_flight_trips,
        },
        "drivers": drivers or [],
        "riders": riders or [],
        "trips": [],
        "route_cache": {},
        "surge_multipliers": surge_multipliers or {},
        "reserved_drivers": reserved_drivers or [],
    }


def _gzip_checkpoint(data: dict[str, object]) -> bytes:
    """Compress checkpoint dict for S3 mock response."""
    return gzip.compress(json.dumps(data).encode("utf-8"))


@pytest.fixture
def restore_engine():
    """Mock engine for restore tests with agent factory dependencies."""
    engine = Mock()
    engine._env = Mock()
    engine._env.now = 0.0
    engine._speed_multiplier = 1
    engine._active_drivers = {}
    engine._active_riders = {}
    engine._kafka_producer = Mock()
    engine._redis_client = Mock()
    engine._matching_server = Mock()
    engine._matching_server._surge_calculator = Mock()
    engine._matching_server._surge_calculator._zone_multipliers = {}
    engine._matching_server._reserved_drivers = set()
    engine._matching_server._active_trips = {}
    engine._agent_factory = Mock()
    engine._agent_factory._registry_manager = None
    engine._agent_factory._zone_loader = None
    engine._agent_factory._osrm_client = None
    engine._agent_factory._surge_calculator = None
    return engine


@pytest.mark.unit
class TestS3CheckpointRestore:
    """Tests for restoring simulation state from S3 checkpoints."""

    @patch("src.db.s3_checkpoint.DriverAgent")
    @patch("src.db.s3_checkpoint.simpy")
    def test_restore_recreates_environment_with_checkpoint_time(
        self,
        mock_simpy,
        mock_driver_agent_cls,
        s3_checkpoint_manager,
        mock_s3_client,
        restore_engine,
    ):
        """Verify simpy.Environment created with correct initial_time."""
        checkpoint = _make_s3_checkpoint(current_time=5000.0, speed_multiplier=15)
        compressed = _gzip_checkpoint(checkpoint)
        mock_s3_client.get_object.return_value = {"Body": Mock(read=Mock(return_value=compressed))}

        mock_env = Mock()
        mock_simpy.Environment.return_value = mock_env

        s3_checkpoint_manager.restore_to_engine(restore_engine)

        mock_simpy.Environment.assert_called_once_with(initial_time=5000.0)
        assert restore_engine._env is mock_env
        assert restore_engine._speed_multiplier == 15

    @patch("src.db.s3_checkpoint.RiderAgent")
    @patch("src.db.s3_checkpoint.DriverAgent")
    @patch("src.db.s3_checkpoint.simpy")
    def test_restore_drivers_and_riders(
        self,
        mock_simpy,
        mock_driver_agent_cls,
        mock_rider_agent_cls,
        s3_checkpoint_manager,
        mock_s3_client,
        restore_engine,
        sample_driver_dna,
        sample_rider_dna,
    ):
        """Verify agents created with correct DNA and runtime state."""
        driver_data = {
            "id": "driver-001",
            "dna": sample_driver_dna.model_dump(),
            "location": [-23.55, -46.63],
            "status": "available",
            "active_trip": None,
            "rating": 4.8,
            "rating_count": 100,
        }
        rider_data = {
            "id": "rider-001",
            "dna": sample_rider_dna.model_dump(),
            "location": [-23.56, -46.65],
            "status": "idle",
            "active_trip": None,
            "rating": 4.9,
            "rating_count": 50,
        }
        checkpoint = _make_s3_checkpoint(drivers=[driver_data], riders=[rider_data])
        compressed = _gzip_checkpoint(checkpoint)
        mock_s3_client.get_object.return_value = {"Body": Mock(read=Mock(return_value=compressed))}
        mock_simpy.Environment.return_value = Mock()

        mock_driver_instance = Mock()
        mock_driver_instance.driver_id = "driver-001"
        mock_driver_instance._determine_zone.return_value = None
        mock_driver_agent_cls.return_value = mock_driver_instance

        mock_rider_instance = Mock()
        mock_rider_instance.rider_id = "rider-001"
        mock_rider_agent_cls.return_value = mock_rider_instance

        s3_checkpoint_manager.restore_to_engine(restore_engine)

        mock_driver_agent_cls.assert_called_once()
        driver_call_kwargs = mock_driver_agent_cls.call_args.kwargs
        assert driver_call_kwargs["driver_id"] == "driver-001"
        assert driver_call_kwargs["puppet"] is False
        # online with no active trip → immediate_online=True
        assert driver_call_kwargs["immediate_online"] is True

        mock_rider_agent_cls.assert_called_once()
        rider_call_kwargs = mock_rider_agent_cls.call_args.kwargs
        assert rider_call_kwargs["rider_id"] == "rider-001"
        assert rider_call_kwargs["puppet"] is False

        assert "driver-001" in restore_engine._active_drivers
        assert "rider-001" in restore_engine._active_riders

        # Verify runtime state was set on driver
        assert mock_driver_instance._status == "available"
        assert mock_driver_instance._location == (-23.55, -46.63)
        assert mock_driver_instance._active_trip is None
        assert mock_driver_instance._current_rating == 4.8
        assert mock_driver_instance._rating_count == 100

        # Verify runtime state was set on rider
        assert mock_rider_instance._status == "idle"
        assert mock_rider_instance._location == (-23.56, -46.65)

        # Verify driver registered in matching server
        restore_engine._matching_server.register_driver.assert_called_once_with(
            mock_driver_instance
        )

    @patch("src.db.s3_checkpoint.simpy")
    def test_restore_surge_and_reserved_drivers(
        self,
        mock_simpy,
        s3_checkpoint_manager,
        mock_s3_client,
        restore_engine,
    ):
        """Verify surge multipliers and reserved drivers restored from top-level keys."""
        checkpoint = _make_s3_checkpoint(
            surge_multipliers={"BVI": 2.0, "PIN": 1.5},
            reserved_drivers=["driver-100", "driver-200"],
        )
        compressed = _gzip_checkpoint(checkpoint)
        mock_s3_client.get_object.return_value = {"Body": Mock(read=Mock(return_value=compressed))}
        mock_simpy.Environment.return_value = Mock()

        s3_checkpoint_manager.restore_to_engine(restore_engine)

        assert restore_engine._matching_server._surge_calculator._zone_multipliers == {
            "BVI": 2.0,
            "PIN": 1.5,
        }
        assert restore_engine._matching_server._reserved_drivers == {
            "driver-100",
            "driver-200",
        }

    def test_restore_raises_error_when_no_checkpoint(
        self,
        s3_checkpoint_manager,
        mock_s3_client,
        restore_engine,
    ):
        """Verify CheckpointError raised when no checkpoint exists."""
        mock_s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "GetObject",
        )

        with pytest.raises(CheckpointError, match="No checkpoint found"):
            s3_checkpoint_manager.restore_to_engine(restore_engine)

    @patch("src.db.s3_checkpoint.simpy")
    def test_restore_cancels_trips_on_crash_checkpoint(
        self,
        mock_simpy,
        s3_checkpoint_manager,
        mock_s3_client,
        restore_engine,
    ):
        """Verify cancel_trip called for in-flight trips on crash checkpoint."""
        checkpoint = _make_s3_checkpoint(
            checkpoint_type="crash",
            in_flight_trips=2,
        )
        compressed = _gzip_checkpoint(checkpoint)
        mock_s3_client.get_object.return_value = {"Body": Mock(read=Mock(return_value=compressed))}
        mock_simpy.Environment.return_value = Mock()

        trip1 = Mock()
        trip1.trip_id = "trip-001"
        trip2 = Mock()
        trip2.trip_id = "trip-002"
        restore_engine._matching_server._active_trips = {
            "trip-001": trip1,
            "trip-002": trip2,
        }

        s3_checkpoint_manager.restore_to_engine(restore_engine)

        assert restore_engine._matching_server.cancel_trip.call_count == 2
        restore_engine._matching_server.cancel_trip.assert_any_call(
            "trip-001", "system", "recovery_cleanup"
        )
        restore_engine._matching_server.cancel_trip.assert_any_call(
            "trip-002", "system", "recovery_cleanup"
        )

    @patch("src.db.s3_checkpoint.DriverAgent")
    @patch("src.db.s3_checkpoint.simpy")
    def test_restore_handles_failed_agents_gracefully(
        self,
        mock_simpy,
        mock_driver_agent_cls,
        s3_checkpoint_manager,
        mock_s3_client,
        restore_engine,
        sample_driver_dna,
    ):
        """Verify partial restoration with warnings when some agents fail."""
        good_driver = {
            "id": "driver-good",
            "dna": sample_driver_dna.model_dump(),
            "location": [-23.55, -46.63],
            "status": "available",
            "active_trip": None,
            "rating": 4.8,
            "rating_count": 100,
        }
        bad_driver = {
            "id": "driver-bad",
            "dna": {"invalid": "dna"},
            "location": [-23.55, -46.63],
            "status": "available",
            "active_trip": None,
            "rating": 4.0,
            "rating_count": 10,
        }
        checkpoint = _make_s3_checkpoint(drivers=[good_driver, bad_driver])
        compressed = _gzip_checkpoint(checkpoint)
        mock_s3_client.get_object.return_value = {"Body": Mock(read=Mock(return_value=compressed))}
        mock_simpy.Environment.return_value = Mock()

        mock_driver_instance = Mock()
        mock_driver_instance.driver_id = "driver-good"
        mock_driver_instance._determine_zone.return_value = None
        mock_driver_agent_cls.return_value = mock_driver_instance

        # Should not raise — failed agent is logged and skipped
        s3_checkpoint_manager.restore_to_engine(restore_engine)

        # Only the good driver should be in active_drivers
        assert "driver-good" in restore_engine._active_drivers
        assert "driver-bad" not in restore_engine._active_drivers
