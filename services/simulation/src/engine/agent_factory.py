"""Factory for dynamic agent creation."""

import random
import threading
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from agents.dna import DriverDNA, RiderDNA
from agents.dna_generator import generate_driver_dna, generate_rider_dna
from agents.driver_agent import DriverAgent
from agents.rider_agent import RiderAgent

if TYPE_CHECKING:
    from engine import SimulationEngine
    from geo.osrm_client import OSRMClient
    from geo.zones import ZoneLoader
    from kafka.producer import KafkaProducer
    from matching.agent_registry_manager import AgentRegistryManager
    from matching.surge_pricing import SurgePricingCalculator


class AgentFactory:
    """Factory for creating driver and rider agents dynamically."""

    def __init__(
        self,
        simulation_engine: "SimulationEngine",
        sqlite_db: Any,
        kafka_producer: "KafkaProducer | None",
        registry_manager: "AgentRegistryManager | None" = None,
        zone_loader: "ZoneLoader | None" = None,
        osrm_client: "OSRMClient | None" = None,
        surge_calculator: "SurgePricingCalculator | None" = None,
    ):
        self._simulation_engine = simulation_engine
        self._sqlite_db = sqlite_db
        self._kafka_producer = kafka_producer
        self._redis_publisher = getattr(simulation_engine, "_redis_client", None)
        self._registry_manager = registry_manager
        self._zone_loader = zone_loader
        self._osrm_client = osrm_client
        self._surge_calculator = surge_calculator

        self._max_drivers = 2000
        self._max_riders = 10000

        # Spawn queues for continuous agent spawning (per-mode queues)
        self._driver_immediate_requests: list[int] = []
        self._driver_scheduled_requests: list[int] = []
        self._rider_immediate_requests: list[int] = []
        self._rider_scheduled_requests: list[int] = []
        self._spawn_lock = threading.Lock()

    def create_drivers(self, count: int) -> list[str]:
        """Create N driver agents."""
        self._check_driver_capacity(count)

        created_ids = []
        for _ in range(count):
            dna = generate_driver_dna()
            driver_id = str(uuid4())

            agent = DriverAgent(
                driver_id=driver_id,
                dna=dna,
                env=self._simulation_engine._env,
                kafka_producer=self._kafka_producer,
                redis_publisher=self._redis_publisher,
                driver_repository=None,
                registry_manager=self._registry_manager,
                zone_loader=self._zone_loader,
                immediate_online=True,  # Start online immediately
                simulation_engine=self._simulation_engine,
            )

            self._simulation_engine.register_driver(agent)

            # Register in AgentRegistryManager
            if self._registry_manager:
                self._registry_manager.register_driver(agent)

            # Agent is registered but process not started yet
            # Engine will pick up pending agents on next step cycle (thread-safe)

            created_ids.append(driver_id)

        return created_ids

    def create_riders(self, count: int) -> list[str]:
        """Create N rider agents."""
        self._check_rider_capacity(count)

        created_ids = []
        for _ in range(count):
            dna = generate_rider_dna()
            rider_id = str(uuid4())

            agent = RiderAgent(
                rider_id=rider_id,
                dna=dna,
                env=self._simulation_engine._env,
                kafka_producer=self._kafka_producer,
                redis_publisher=self._redis_publisher,
                rider_repository=None,
                simulation_engine=self._simulation_engine,
                zone_loader=self._zone_loader,
                osrm_client=self._osrm_client,
                surge_calculator=self._surge_calculator,
                immediate_first_trip=False,  # Follow DNA avg_rides_per_week schedule
            )

            self._simulation_engine.register_rider(agent)

            # Register in AgentRegistryManager
            if self._registry_manager:
                self._registry_manager.register_rider(agent)

            # Agent is registered but process not started yet
            # Engine will pick up pending agents on next step cycle (thread-safe)

            created_ids.append(rider_id)

        return created_ids

    def _check_driver_capacity(self, count: int) -> None:
        """Verify adding count drivers won't exceed limit."""
        current_count = len(self._simulation_engine._active_drivers)
        if current_count + count > self._max_drivers:
            raise ValueError(
                f"Driver capacity limit exceeded: {current_count} + {count} > {self._max_drivers}"
            )

    def _check_rider_capacity(self, count: int) -> None:
        """Verify adding count riders won't exceed limit."""
        current_count = len(self._simulation_engine._active_riders)
        if current_count + count > self._max_riders:
            raise ValueError(
                f"Rider capacity limit exceeded: {current_count} + {count} > {self._max_riders}"
            )

    # --- Spawn Queue Methods (for continuous spawning) ---

    def queue_drivers(self, count: int, immediate: bool = True) -> int:
        """Queue N drivers for continuous spawning.

        Args:
            count: Number of drivers to queue
            immediate: If True, go online immediately; if False, follow DNA shift_preference

        Returns:
            Number of drivers queued

        Raises:
            ValueError: If adding count would exceed capacity
        """
        self._check_driver_capacity(count)
        with self._spawn_lock:
            if immediate:
                self._driver_immediate_requests.append(count)
            else:
                self._driver_scheduled_requests.append(count)
        return count

    def queue_riders(self, count: int, immediate: bool = False) -> int:
        """Queue N riders for continuous spawning.

        Args:
            count: Number of riders to queue
            immediate: If True, request trip immediately; if False, follow DNA avg_rides_per_week

        Returns:
            Number of riders queued

        Raises:
            ValueError: If adding count would exceed capacity
        """
        self._check_rider_capacity(count)
        with self._spawn_lock:
            if immediate:
                self._rider_immediate_requests.append(count)
            else:
                self._rider_scheduled_requests.append(count)
        return count

    def dequeue_driver_immediate(self) -> bool:
        """Dequeue one immediate-mode driver for spawning.

        Returns:
            True if dequeued, False if queue empty
        """
        with self._spawn_lock:
            while self._driver_immediate_requests:
                if self._driver_immediate_requests[0] > 0:
                    self._driver_immediate_requests[0] -= 1
                    return True
                self._driver_immediate_requests.pop(0)
            return False

    def dequeue_driver_scheduled(self) -> bool:
        """Dequeue one scheduled-mode driver for spawning.

        Returns:
            True if dequeued, False if queue empty
        """
        with self._spawn_lock:
            while self._driver_scheduled_requests:
                if self._driver_scheduled_requests[0] > 0:
                    self._driver_scheduled_requests[0] -= 1
                    return True
                self._driver_scheduled_requests.pop(0)
            return False

    def dequeue_rider_immediate(self) -> bool:
        """Dequeue one immediate-mode rider for spawning.

        Returns:
            True if dequeued, False if queue empty
        """
        with self._spawn_lock:
            while self._rider_immediate_requests:
                if self._rider_immediate_requests[0] > 0:
                    self._rider_immediate_requests[0] -= 1
                    return True
                self._rider_immediate_requests.pop(0)
            return False

    def dequeue_rider_scheduled(self) -> bool:
        """Dequeue one scheduled-mode rider for spawning.

        Returns:
            True if dequeued, False if queue empty
        """
        with self._spawn_lock:
            while self._rider_scheduled_requests:
                if self._rider_scheduled_requests[0] > 0:
                    self._rider_scheduled_requests[0] -= 1
                    return True
                self._rider_scheduled_requests.pop(0)
            return False

    def get_spawn_queue_status(self) -> dict[str, int]:
        """Get current spawn queue status.

        Returns:
            Dictionary with per-mode queue counts
        """
        with self._spawn_lock:
            return {
                "drivers_queued": sum(self._driver_immediate_requests)
                + sum(self._driver_scheduled_requests),
                "riders_queued": sum(self._rider_immediate_requests)
                + sum(self._rider_scheduled_requests),
                "drivers_immediate_queued": sum(self._driver_immediate_requests),
                "drivers_scheduled_queued": sum(self._driver_scheduled_requests),
                "riders_immediate_queued": sum(self._rider_immediate_requests),
                "riders_scheduled_queued": sum(self._rider_scheduled_requests),
            }

    def clear_spawn_queues(self) -> None:
        """Clear all spawn queues. Used during reset."""
        with self._spawn_lock:
            self._driver_immediate_requests.clear()
            self._driver_scheduled_requests.clear()
            self._rider_immediate_requests.clear()
            self._rider_scheduled_requests.clear()

    def _get_random_location_in_zone(self, zone_id: str) -> tuple[float, float] | None:
        """Get a random location within a zone.

        Uses the zone's centroid with a small random offset (~500m).

        Args:
            zone_id: The zone ID to place the agent in

        Returns:
            (lat, lon) tuple or None if zone not found
        """
        if not self._zone_loader:
            return None

        zone = self._zone_loader.get_zone(zone_id)
        if not zone:
            return None

        # Use zone centroid with small random offset
        centroid = zone.centroid
        # centroid is (lon, lat) from GeoJSON convention
        centroid_lon, centroid_lat = centroid

        # Add small random offset (up to ~500m = 0.005 degrees)
        lat = centroid_lat + random.uniform(-0.005, 0.005)
        lon = centroid_lon + random.uniform(-0.005, 0.005)

        return (lat, lon)

    def _generate_destinations_for_home(
        self, home_lat: float, home_lon: float
    ) -> list[dict[str, Any]]:
        """Generate frequent destinations near a home location.

        All destinations are validated to be inside São Paulo zone polygons.

        Args:
            home_lat: Home latitude
            home_lon: Home longitude

        Returns:
            List of destination dictionaries
        """
        from agents.dna_generator import SAO_PAULO_BOUNDS
        from agents.zone_validator import is_location_in_any_zone

        num_destinations = random.randint(2, 5)
        destinations: list[dict[str, Any]] = []
        total_weight = 0.0

        max_attempts_per_destination = 50
        for _ in range(num_destinations):
            # Try to generate a valid destination within zone boundaries
            dest_lat, dest_lon = None, None
            for _attempt in range(max_attempts_per_destination):
                # Generate destination within 0.8-20km of home
                distance_factor = random.uniform(0.01, 0.15)
                lat_offset = random.uniform(-distance_factor, distance_factor)
                lon_offset = random.uniform(-distance_factor, distance_factor)

                candidate_lat = home_lat + lat_offset
                candidate_lon = home_lon + lon_offset

                # Clamp to Sao Paulo bounds
                candidate_lat = max(
                    SAO_PAULO_BOUNDS["lat_min"],
                    min(SAO_PAULO_BOUNDS["lat_max"], candidate_lat),
                )
                candidate_lon = max(
                    SAO_PAULO_BOUNDS["lon_min"],
                    min(SAO_PAULO_BOUNDS["lon_max"], candidate_lon),
                )

                # Validate destination is inside a zone polygon
                if is_location_in_any_zone(candidate_lat, candidate_lon):
                    dest_lat, dest_lon = candidate_lat, candidate_lon
                    break

            # If no valid destination found after retries, use home location
            # (which should already be validated)
            if dest_lat is None or dest_lon is None:
                dest_lat, dest_lon = home_lat, home_lon

            weight = random.random()
            total_weight += weight

            # Optional time affinity
            time_affinity = None
            if random.random() < 0.4:
                affinity_type = random.choice(["morning_commute", "evening_return", "leisure"])
                if affinity_type == "morning_commute":
                    time_affinity = list(range(7, 10))
                elif affinity_type == "evening_return":
                    time_affinity = list(range(17, 20))
                else:
                    time_affinity = list(range(10, 23))

            dest = {
                "coordinates": (dest_lat, dest_lon),
                "weight": weight,
            }
            if time_affinity:
                dest["time_affinity"] = time_affinity

            destinations.append(dest)

        # Normalize weights
        for dest in destinations:
            dest["weight"] = cast(float, dest["weight"]) / total_weight

        return destinations

    # --- Puppet Agent Creation Methods ---

    def create_puppet_driver(
        self,
        location: tuple[float, float],
        dna_override: dict[str, Any] | None = None,
        zone_id: str | None = None,
        ephemeral: bool = True,
    ) -> str:
        """Create a puppet driver at the specified location.

        Puppet drivers:
        - Start in 'offline' status
        - Emit GPS pings but take no autonomous actions
        - All state transitions triggered via API
        - Support optional DNA overrides for testing specific behaviors

        Args:
            location: (lat, lon) tuple for initial position
            dna_override: Optional partial DNA fields to override
            zone_id: If provided, place agent at random location within this zone
            ephemeral: If True, skip SQLite persistence (in-memory only)

        Returns:
            The driver_id of the created puppet agent
        """
        self._check_driver_capacity(1)

        # Generate DNA with home_location set to the specified location
        base_dna = generate_driver_dna()
        dna_dict = base_dna.model_dump()
        dna_dict["home_location"] = location

        # Handle zone-based placement
        if zone_id:
            zone_location = self._get_random_location_in_zone(zone_id)
            if zone_location:
                dna_dict["home_location"] = zone_location

        # Apply explicit overrides (takes precedence over zone)
        if dna_override:
            for key, value in dna_override.items():
                if value is not None and key != "zone_id":
                    dna_dict[key] = value

        dna = DriverDNA.model_validate(dna_dict)
        driver_id = str(uuid4())

        agent = DriverAgent(
            driver_id=driver_id,
            dna=dna,
            env=self._simulation_engine._env,
            kafka_producer=self._kafka_producer,
            redis_publisher=self._redis_publisher,
            driver_repository=None,
            registry_manager=self._registry_manager,
            zone_loader=self._zone_loader,
            immediate_online=False,  # Puppet stays offline until API call
            puppet=True,  # Enable puppet mode
            simulation_engine=self._simulation_engine,
        )
        agent._is_ephemeral = ephemeral
        agent._is_puppet = True

        self._simulation_engine.register_driver(agent)

        if self._registry_manager:
            self._registry_manager.register_driver(agent)

        return driver_id

    def create_puppet_rider(
        self,
        location: tuple[float, float],
        dna_override: dict[str, Any] | None = None,
        zone_id: str | None = None,
        ephemeral: bool = True,
    ) -> str:
        """Create a puppet rider at the specified location.

        Puppet riders:
        - Start in 'offline' status
        - Emit GPS pings but take no autonomous actions
        - All state transitions triggered via API
        - Support optional DNA overrides for testing specific behaviors

        Args:
            location: (lat, lon) tuple for initial position
            dna_override: Optional partial DNA fields to override
            zone_id: If provided, place agent at random location within this zone
            ephemeral: If True, skip SQLite persistence (in-memory only)

        Returns:
            The rider_id of the created puppet agent
        """
        self._check_rider_capacity(1)

        # Generate DNA with home_location set to the specified location
        base_dna = generate_rider_dna()
        dna_dict = base_dna.model_dump()
        dna_dict["home_location"] = location
        # Regenerate frequent_destinations based on new home location
        dna_dict["frequent_destinations"] = self._generate_destinations_for_home(
            location[0], location[1]
        )

        # Handle zone-based placement
        if zone_id:
            zone_location = self._get_random_location_in_zone(zone_id)
            if zone_location:
                dna_dict["home_location"] = zone_location
                # Regenerate frequent_destinations based on zone location
                dna_dict["frequent_destinations"] = self._generate_destinations_for_home(
                    zone_location[0], zone_location[1]
                )

        # Apply explicit overrides (takes precedence over zone)
        if dna_override:
            for key, value in dna_override.items():
                if value is not None and key != "zone_id":
                    dna_dict[key] = value

        dna = RiderDNA.model_validate(dna_dict)
        rider_id = str(uuid4())

        agent = RiderAgent(
            rider_id=rider_id,
            dna=dna,
            env=self._simulation_engine._env,
            kafka_producer=self._kafka_producer,
            redis_publisher=self._redis_publisher,
            rider_repository=None,
            simulation_engine=self._simulation_engine,
            zone_loader=self._zone_loader,
            osrm_client=self._osrm_client,
            surge_calculator=self._surge_calculator,
            immediate_first_trip=False,  # Puppet waits for API call
            puppet=True,  # Enable puppet mode
        )
        agent._is_ephemeral = ephemeral
        agent._is_puppet = True

        self._simulation_engine.register_rider(agent)

        if self._registry_manager:
            self._registry_manager.register_rider(agent)

        return rider_id
