"""Unit tests for S3CheckpointManager with mocked S3 client."""

import gzip
import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from botocore.exceptions import ClientError

from src.agents.dna import DriverDNA, RiderDNA, ShiftPreference
from src.db.s3_checkpoint import S3CheckpointManager
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
        preferred_zones=["BVI", "PIN"],
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
        trip1.state = TripState.MATCHED

        trip2 = Mock()
        trip2.state = TripState.STARTED

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
