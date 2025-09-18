"""Tests for immutable snapshot dataclasses used in thread-safe state transfer."""

from datetime import UTC, datetime

import pytest

from src.engine.snapshots import AgentSnapshot, SimulationSnapshot, TripSnapshot


class TestAgentSnapshotImmutability:
    """Tests for AgentSnapshot frozen dataclass."""

    def test_agent_snapshot_creation(self):
        """AgentSnapshot can be created with all fields."""
        snapshot = AgentSnapshot(
            id="driver_123",
            type="driver",
            status="online",
            location=(-23.5505, -46.6333),
            active_trip_id=None,
            zone_id="pinheiros",
        )
        assert snapshot.id == "driver_123"
        assert snapshot.type == "driver"
        assert snapshot.status == "online"
        assert snapshot.location == (-23.5505, -46.6333)
        assert snapshot.active_trip_id is None
        assert snapshot.zone_id == "pinheiros"

    def test_agent_snapshot_is_frozen(self):
        """AgentSnapshot is immutable - cannot modify fields."""
        snapshot = AgentSnapshot(
            id="driver_123",
            type="driver",
            status="online",
            location=(-23.5505, -46.6333),
            active_trip_id=None,
            zone_id="pinheiros",
        )
        with pytest.raises(AttributeError):
            snapshot.status = "offline"

    def test_agent_snapshot_id_frozen(self):
        """AgentSnapshot id field is immutable."""
        snapshot = AgentSnapshot(
            id="driver_123",
            type="driver",
            status="online",
            location=(-23.5505, -46.6333),
            active_trip_id=None,
            zone_id="pinheiros",
        )
        with pytest.raises(AttributeError):
            snapshot.id = "driver_456"

    def test_agent_snapshot_location_frozen(self):
        """AgentSnapshot location field is immutable."""
        snapshot = AgentSnapshot(
            id="driver_123",
            type="driver",
            status="online",
            location=(-23.5505, -46.6333),
            active_trip_id=None,
            zone_id="pinheiros",
        )
        with pytest.raises(AttributeError):
            snapshot.location = (-23.6, -46.7)

    def test_agent_snapshot_driver_type(self):
        """AgentSnapshot can represent a driver."""
        snapshot = AgentSnapshot(
            id="driver_001",
            type="driver",
            status="busy",
            location=(-23.5505, -46.6333),
            active_trip_id="trip_123",
            zone_id="vila_madalena",
        )
        assert snapshot.type == "driver"
        assert snapshot.active_trip_id == "trip_123"

    def test_agent_snapshot_rider_type(self):
        """AgentSnapshot can represent a rider."""
        snapshot = AgentSnapshot(
            id="rider_001",
            type="rider",
            status="waiting",
            location=(-23.5505, -46.6333),
            active_trip_id=None,
            zone_id="consolacao",
        )
        assert snapshot.type == "rider"


class TestAgentSnapshotSerialization:
    """Tests for AgentSnapshot serialization to dict."""

    def test_agent_snapshot_to_dict(self):
        """AgentSnapshot can be serialized to dict."""
        snapshot = AgentSnapshot(
            id="driver_123",
            type="driver",
            status="online",
            location=(-23.5505, -46.6333),
            active_trip_id=None,
            zone_id="pinheiros",
        )
        data = snapshot.to_dict()
        assert data["id"] == "driver_123"
        assert data["type"] == "driver"
        assert data["status"] == "online"
        assert data["location"] == (-23.5505, -46.6333)
        assert data["active_trip_id"] is None
        assert data["zone_id"] == "pinheiros"

    def test_agent_snapshot_dict_contains_all_fields(self):
        """Serialized dict contains all expected fields."""
        snapshot = AgentSnapshot(
            id="rider_456",
            type="rider",
            status="in_trip",
            location=(-23.5600, -46.6400),
            active_trip_id="trip_789",
            zone_id="moema",
        )
        data = snapshot.to_dict()
        expected_keys = {"id", "type", "status", "location", "active_trip_id", "zone_id"}
        assert set(data.keys()) == expected_keys


class TestTripSnapshotImmutability:
    """Tests for TripSnapshot frozen dataclass."""

    def test_trip_snapshot_creation(self):
        """TripSnapshot can be created with all fields."""
        created = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
        snapshot = TripSnapshot(
            trip_id="trip_123",
            state="STARTED",
            driver_id="driver_001",
            rider_id="rider_001",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5700, -46.6500),
            created_at=created,
        )
        assert snapshot.trip_id == "trip_123"
        assert snapshot.state == "STARTED"
        assert snapshot.driver_id == "driver_001"
        assert snapshot.rider_id == "rider_001"
        assert snapshot.pickup_location == (-23.5505, -46.6333)
        assert snapshot.dropoff_location == (-23.5700, -46.6500)
        assert snapshot.created_at == created

    def test_trip_snapshot_is_frozen(self):
        """TripSnapshot is immutable - cannot modify fields."""
        snapshot = TripSnapshot(
            trip_id="trip_123",
            state="STARTED",
            driver_id="driver_001",
            rider_id="rider_001",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5700, -46.6500),
            created_at=datetime.now(UTC),
        )
        with pytest.raises(AttributeError):
            snapshot.state = "COMPLETED"

    def test_trip_snapshot_driver_id_frozen(self):
        """TripSnapshot driver_id field is immutable."""
        snapshot = TripSnapshot(
            trip_id="trip_123",
            state="MATCHED",
            driver_id="driver_001",
            rider_id="rider_001",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5700, -46.6500),
            created_at=datetime.now(UTC),
        )
        with pytest.raises(AttributeError):
            snapshot.driver_id = "driver_002"

    def test_trip_snapshot_without_driver(self):
        """TripSnapshot can have None driver_id (unmatched trip)."""
        snapshot = TripSnapshot(
            trip_id="trip_456",
            state="REQUESTED",
            driver_id=None,
            rider_id="rider_002",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5700, -46.6500),
            created_at=datetime.now(UTC),
        )
        assert snapshot.driver_id is None
        assert snapshot.state == "REQUESTED"


class TestTripSnapshotSerialization:
    """Tests for TripSnapshot serialization to dict."""

    def test_trip_snapshot_to_dict(self):
        """TripSnapshot can be serialized to dict."""
        created = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
        snapshot = TripSnapshot(
            trip_id="trip_123",
            state="DRIVER_EN_ROUTE",
            driver_id="driver_001",
            rider_id="rider_001",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5700, -46.6500),
            created_at=created,
        )
        data = snapshot.to_dict()
        assert data["trip_id"] == "trip_123"
        assert data["state"] == "DRIVER_EN_ROUTE"
        assert data["driver_id"] == "driver_001"
        assert data["rider_id"] == "rider_001"

    def test_trip_snapshot_dict_datetime_serializable(self):
        """Serialized dict has datetime as ISO string or datetime object."""
        created = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
        snapshot = TripSnapshot(
            trip_id="trip_123",
            state="STARTED",
            driver_id="driver_001",
            rider_id="rider_001",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5700, -46.6500),
            created_at=created,
        )
        data = snapshot.to_dict()
        # created_at should be present and be either datetime or ISO string
        assert "created_at" in data
        if isinstance(data["created_at"], str):
            assert "2025-01-15" in data["created_at"]
        else:
            assert data["created_at"] == created


class TestSimulationSnapshotImmutability:
    """Tests for SimulationSnapshot frozen dataclass."""

    def test_simulation_snapshot_creation(self):
        """SimulationSnapshot can be created with all fields."""
        now = datetime.now(UTC)
        driver = AgentSnapshot(
            id="d1",
            type="driver",
            status="online",
            location=(-23.55, -46.63),
            active_trip_id=None,
            zone_id="zone_a",
        )
        rider = AgentSnapshot(
            id="r1",
            type="rider",
            status="waiting",
            location=(-23.56, -46.64),
            active_trip_id=None,
            zone_id="zone_b",
        )
        trip = TripSnapshot(
            trip_id="t1",
            state="STARTED",
            driver_id="d1",
            rider_id="r1",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.57, -46.65),
            created_at=now,
        )

        snapshot = SimulationSnapshot(
            timestamp=now,
            simulation_time=3600.0,
            is_running=True,
            is_paused=False,
            speed_multiplier=10.0,
            driver_count=1,
            rider_count=1,
            active_trip_count=1,
            drivers=(driver,),
            riders=(rider,),
            active_trips=(trip,),
            status_counts={"online": 1, "waiting": 1},
            zone_counts={"zone_a": {"driver": 1}, "zone_b": {"rider": 1}},
        )

        assert snapshot.simulation_time == 3600.0
        assert snapshot.is_running is True
        assert snapshot.speed_multiplier == 10.0

    def test_simulation_snapshot_is_frozen(self):
        """SimulationSnapshot is immutable - cannot modify fields."""
        now = datetime.now(UTC)
        snapshot = SimulationSnapshot(
            timestamp=now,
            simulation_time=0.0,
            is_running=False,
            is_paused=False,
            speed_multiplier=1.0,
            driver_count=0,
            rider_count=0,
            active_trip_count=0,
            drivers=(),
            riders=(),
            active_trips=(),
            status_counts={},
            zone_counts={},
        )
        with pytest.raises(AttributeError):
            snapshot.is_running = True

    def test_simulation_snapshot_drivers_is_tuple(self):
        """SimulationSnapshot drivers field is a tuple (immutable)."""
        now = datetime.now(UTC)
        driver = AgentSnapshot(
            id="d1",
            type="driver",
            status="online",
            location=(-23.55, -46.63),
            active_trip_id=None,
            zone_id="zone_a",
        )
        snapshot = SimulationSnapshot(
            timestamp=now,
            simulation_time=0.0,
            is_running=True,
            is_paused=False,
            speed_multiplier=1.0,
            driver_count=1,
            rider_count=0,
            active_trip_count=0,
            drivers=(driver,),
            riders=(),
            active_trips=(),
            status_counts={"online": 1},
            zone_counts={},
        )
        assert isinstance(snapshot.drivers, tuple)

    def test_simulation_snapshot_riders_is_tuple(self):
        """SimulationSnapshot riders field is a tuple (immutable)."""
        now = datetime.now(UTC)
        snapshot = SimulationSnapshot(
            timestamp=now,
            simulation_time=0.0,
            is_running=True,
            is_paused=False,
            speed_multiplier=1.0,
            driver_count=0,
            rider_count=0,
            active_trip_count=0,
            drivers=(),
            riders=(),
            active_trips=(),
            status_counts={},
            zone_counts={},
        )
        assert isinstance(snapshot.riders, tuple)

    def test_simulation_snapshot_active_trips_is_tuple(self):
        """SimulationSnapshot active_trips field is a tuple (immutable)."""
        now = datetime.now(UTC)
        snapshot = SimulationSnapshot(
            timestamp=now,
            simulation_time=0.0,
            is_running=True,
            is_paused=False,
            speed_multiplier=1.0,
            driver_count=0,
            rider_count=0,
            active_trip_count=0,
            drivers=(),
            riders=(),
            active_trips=(),
            status_counts={},
            zone_counts={},
        )
        assert isinstance(snapshot.active_trips, tuple)


class TestSimulationSnapshotSerialization:
    """Tests for SimulationSnapshot serialization to dict."""

    def test_simulation_snapshot_to_dict(self):
        """SimulationSnapshot can be serialized to dict."""
        now = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
        snapshot = SimulationSnapshot(
            timestamp=now,
            simulation_time=7200.0,
            is_running=True,
            is_paused=False,
            speed_multiplier=5.0,
            driver_count=10,
            rider_count=20,
            active_trip_count=5,
            drivers=(),
            riders=(),
            active_trips=(),
            status_counts={"online": 8, "busy": 2},
            zone_counts={"zone_a": {"online": 5}},
        )
        data = snapshot.to_dict()

        assert data["simulation_time"] == 7200.0
        assert data["is_running"] is True
        assert data["is_paused"] is False
        assert data["speed_multiplier"] == 5.0
        assert data["driver_count"] == 10
        assert data["rider_count"] == 20

    def test_simulation_snapshot_dict_nested_agents(self):
        """Serialized dict contains nested agent snapshots as dicts."""
        now = datetime.now(UTC)
        driver = AgentSnapshot(
            id="d1",
            type="driver",
            status="online",
            location=(-23.55, -46.63),
            active_trip_id=None,
            zone_id="zone_a",
        )
        snapshot = SimulationSnapshot(
            timestamp=now,
            simulation_time=0.0,
            is_running=True,
            is_paused=False,
            speed_multiplier=1.0,
            driver_count=1,
            rider_count=0,
            active_trip_count=0,
            drivers=(driver,),
            riders=(),
            active_trips=(),
            status_counts={"online": 1},
            zone_counts={},
        )
        data = snapshot.to_dict()

        assert "drivers" in data
        assert len(data["drivers"]) == 1
        assert data["drivers"][0]["id"] == "d1"

    def test_simulation_snapshot_dict_nested_trips(self):
        """Serialized dict contains nested trip snapshots as dicts."""
        now = datetime.now(UTC)
        trip = TripSnapshot(
            trip_id="t1",
            state="STARTED",
            driver_id="d1",
            rider_id="r1",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.57, -46.65),
            created_at=now,
        )
        snapshot = SimulationSnapshot(
            timestamp=now,
            simulation_time=0.0,
            is_running=True,
            is_paused=False,
            speed_multiplier=1.0,
            driver_count=1,
            rider_count=1,
            active_trip_count=1,
            drivers=(),
            riders=(),
            active_trips=(trip,),
            status_counts={},
            zone_counts={},
        )
        data = snapshot.to_dict()

        assert "active_trips" in data
        assert len(data["active_trips"]) == 1
        assert data["active_trips"][0]["trip_id"] == "t1"
        assert data["active_trips"][0]["state"] == "STARTED"

    def test_simulation_snapshot_contains_all_fields(self):
        """Serialized dict contains all expected top-level fields."""
        now = datetime.now(UTC)
        snapshot = SimulationSnapshot(
            timestamp=now,
            simulation_time=0.0,
            is_running=False,
            is_paused=True,
            speed_multiplier=1.0,
            driver_count=0,
            rider_count=0,
            active_trip_count=0,
            drivers=(),
            riders=(),
            active_trips=(),
            status_counts={},
            zone_counts={},
        )
        data = snapshot.to_dict()

        expected_keys = {
            "timestamp",
            "simulation_time",
            "is_running",
            "is_paused",
            "speed_multiplier",
            "driver_count",
            "rider_count",
            "active_trip_count",
            "drivers",
            "riders",
            "active_trips",
            "status_counts",
            "zone_counts",
        }
        assert set(data.keys()) == expected_keys
