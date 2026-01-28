"""Thread safety tests for matching components.

These tests verify that concurrent access to matching components doesn't cause
race conditions, data corruption, or RuntimeError from dictionary mutations.

Tests are expected to FAIL initially (no locks exist yet) and PASS after
adding proper locking in the GREEN phase.

Note: Race conditions are probabilistic. These tests use high iteration counts
and multiple runs to increase the likelihood of detecting issues.
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock

from src.matching.agent_registry_manager import AgentRegistryManager
from src.matching.driver_geospatial_index import DriverGeospatialIndex
from src.matching.driver_registry import DriverRegistry
from src.matching.matching_server import MatchingServer
from src.trip import Trip

# Number of times to run each test to catch probabilistic race conditions
STRESS_ITERATIONS = 5


def create_matching_server() -> MatchingServer:
    """Create a fresh MatchingServer instance for testing."""
    env = Mock()
    osrm_client = Mock()
    notification_dispatch = Mock()
    driver_index = DriverGeospatialIndex()
    return MatchingServer(
        env=env,
        driver_index=driver_index,
        notification_dispatch=notification_dispatch,
        osrm_client=osrm_client,
    )


class TestDriverRegistryConcurrentStatusUpdates:
    """Test that concurrent status updates don't corrupt counts."""

    def test_concurrent_status_updates_preserve_count_integrity(self):
        """Concurrent status updates should not corrupt status counts.

        Without proper locking, the read-modify-write pattern in update_driver_status
        can cause lost updates when multiple threads update concurrently.
        """
        num_drivers = 100
        num_threads = 20
        updates_per_thread = 100
        statuses = ["online", "en_route_pickup", "en_route_destination"]

        for iteration in range(STRESS_ITERATIONS):
            driver_registry = DriverRegistry()

            for i in range(num_drivers):
                driver_registry.register_driver(
                    f"driver_{i}",
                    "online",
                    zone_id="zone_a",
                    location=(-23.56, -46.65),
                )

            def update_statuses(
                thread_id: int,
                registry: DriverRegistry = driver_registry,
                num_d: int = num_drivers,
                upt: int = updates_per_thread,
                sts: list = statuses,
            ):
                for j in range(upt):
                    driver_id = f"driver_{(thread_id * upt + j) % num_d}"
                    new_status = sts[j % len(sts)]
                    registry.update_driver_status(driver_id, new_status)

            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(update_statuses, i) for i in range(num_threads)]
                for future in as_completed(futures):
                    future.result()

            # Verify total count equals number of drivers
            total_count = sum(driver_registry.get_status_count(s) for s in statuses)
            total_count += driver_registry.get_status_count("offline")

            assert total_count == num_drivers, (
                f"Iteration {iteration}: Total status count ({total_count}) doesn't match "
                f"driver count ({num_drivers}). Race condition detected."
            )

    def test_concurrent_register_and_update(self):
        """Concurrent registration and updates should not cause errors."""
        num_drivers = 100

        for iteration in range(STRESS_ITERATIONS):
            driver_registry = DriverRegistry()
            errors: list = []

            def register_drivers(
                registry: DriverRegistry = driver_registry,
                errs: list = errors,
                num_d: int = num_drivers,
            ):
                for i in range(num_d):
                    try:
                        registry.register_driver(
                            f"driver_{i}",
                            "online",
                            zone_id="zone_a",
                            location=(-23.56, -46.65),
                        )
                    except Exception as e:
                        errs.append(("register", e))

            def update_drivers(
                registry: DriverRegistry = driver_registry,
                errs: list = errors,
                num_d: int = num_drivers,
            ):
                for i in range(num_d):
                    try:
                        registry.update_driver_status(f"driver_{i}", "en_route_pickup")
                    except Exception as e:
                        errs.append(("update", e))

            threads = [
                threading.Thread(target=register_drivers),
                threading.Thread(target=update_drivers),
                threading.Thread(target=update_drivers),
                threading.Thread(target=update_drivers),
            ]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert (
                not errors
            ), f"Iteration {iteration}: Errors occurred during concurrent operations: {errors}"


class TestDriverRegistryConcurrentZoneQueries:
    """Test that zone queries don't raise RuntimeError during updates."""

    def test_zone_queries_during_status_updates(self):
        """Zone queries should not raise 'dictionary changed size during iteration'.

        Without proper locking, iterating over _drivers.items() while another
        thread modifies the dictionary can cause RuntimeError.
        """
        num_drivers = 100
        zone_id = "pinheiros"

        for iteration in range(STRESS_ITERATIONS):
            driver_registry = DriverRegistry()

            for i in range(num_drivers):
                driver_registry.register_driver(
                    f"driver_{i}",
                    "online",
                    zone_id=zone_id,
                    location=(-23.56, -46.65),
                )

            errors: list = []
            stop_event = threading.Event()

            def query_zone(
                registry: DriverRegistry = driver_registry,
                errs: list = errors,
                stop: threading.Event = stop_event,
                zid: str = zone_id,
            ):
                while not stop.is_set():
                    try:
                        registry.get_available_drivers_in_zone(zid)
                    except RuntimeError as e:
                        if "dictionary changed size during iteration" in str(e):
                            errs.append(e)
                            break

            def update_statuses(
                registry: DriverRegistry = driver_registry,
                num_d: int = num_drivers,
            ):
                for i in range(500):
                    driver_id = f"driver_{i % num_d}"
                    status = "en_route_pickup" if i % 2 == 0 else "online"
                    registry.update_driver_status(driver_id, status)

            query_threads = [threading.Thread(target=query_zone) for _ in range(10)]
            update_thread = threading.Thread(target=update_statuses)

            for t in query_threads:
                t.start()
            update_thread.start()

            update_thread.join()
            stop_event.set()
            for t in query_threads:
                t.join()

            assert not errors, (
                f"Iteration {iteration}: RuntimeError occurred during concurrent zone queries. "
                "Dictionary changed size during iteration."
            )

    def test_zone_update_during_queries(self):
        """Zone updates should not corrupt zone counts during iteration."""
        num_drivers = 100
        zones = ["zone_a", "zone_b", "zone_c"]

        for iteration in range(STRESS_ITERATIONS):
            driver_registry = DriverRegistry()

            for i in range(num_drivers):
                driver_registry.register_driver(
                    f"driver_{i}",
                    "online",
                    zone_id=zones[i % len(zones)],
                    location=(-23.56, -46.65),
                )

            errors: list = []

            def query_all_zones(
                registry: DriverRegistry = driver_registry,
                errs: list = errors,
                zs: list = zones,
            ):
                for _ in range(200):
                    try:
                        for zone in zs:
                            registry.get_zone_driver_count(zone, "online")
                    except (RuntimeError, KeyError) as e:
                        errs.append(e)

            def update_zones(
                registry: DriverRegistry = driver_registry,
                num_d: int = num_drivers,
                zs: list = zones,
            ):
                for i in range(200):
                    driver_id = f"driver_{i % num_d}"
                    new_zone = zs[(i + 1) % len(zs)]
                    registry.update_driver_zone(driver_id, new_zone)

            threads = [
                threading.Thread(target=query_all_zones),
                threading.Thread(target=query_all_zones),
                threading.Thread(target=query_all_zones),
                threading.Thread(target=update_zones),
                threading.Thread(target=update_zones),
            ]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert (
                not errors
            ), f"Iteration {iteration}: Errors during concurrent zone operations: {errors}"


class TestMatchingServerConcurrentTripAccess:
    """Test that concurrent trip access doesn't raise errors."""

    def test_get_active_trips_during_modifications(self):
        """Reading active trips while modifying should not raise RuntimeError.

        Without proper locking, calling list(self._active_trips.values()) while
        another thread adds/removes trips can cause RuntimeError.
        """
        for iteration in range(STRESS_ITERATIONS):
            matching_server = create_matching_server()
            errors: list = []
            stop_event = threading.Event()

            def read_trips(
                server: MatchingServer = matching_server,
                errs: list = errors,
                stop: threading.Event = stop_event,
            ):
                while not stop.is_set():
                    try:
                        server.get_active_trips()
                    except RuntimeError as e:
                        if "dictionary changed size during iteration" in str(e):
                            errs.append(e)
                            break

            def modify_trips(server: MatchingServer = matching_server):
                for i in range(500):
                    trip = Trip(
                        trip_id=f"trip_{i}",
                        rider_id=f"rider_{i}",
                        pickup_location=(-23.56, -46.65),
                        dropoff_location=(-23.57, -46.66),
                        pickup_zone_id="zone_a",
                        dropoff_zone_id="zone_b",
                        surge_multiplier=1.0,
                        fare=25.0,
                    )
                    server._active_trips[trip.trip_id] = trip

                for i in range(500):
                    server._active_trips.pop(f"trip_{i}", None)

            read_threads = [threading.Thread(target=read_trips) for _ in range(10)]
            modify_thread = threading.Thread(target=modify_trips)

            for t in read_threads:
                t.start()
            modify_thread.start()

            modify_thread.join()
            stop_event.set()
            for t in read_threads:
                t.join()

            assert not errors, (
                f"Iteration {iteration}: RuntimeError occurred during concurrent trip access. "
                "Dictionary changed size during iteration."
            )

    def test_complete_trip_concurrent_access(self):
        """Concurrent complete_trip calls should not corrupt trip lists."""
        num_trips = 100

        for iteration in range(STRESS_ITERATIONS):
            matching_server = create_matching_server()

            for i in range(num_trips):
                trip = Trip(
                    trip_id=f"trip_{i}",
                    rider_id=f"rider_{i}",
                    pickup_location=(-23.56, -46.65),
                    dropoff_location=(-23.57, -46.66),
                    pickup_zone_id="zone_a",
                    dropoff_zone_id="zone_b",
                    surge_multiplier=1.0,
                    fare=25.0,
                )
                matching_server._active_trips[trip.trip_id] = trip

            errors: list = []

            def complete_trips(
                start: int,
                end: int,
                server: MatchingServer = matching_server,
                errs: list = errors,
            ):
                for i in range(start, end):
                    try:
                        server.complete_trip(f"trip_{i}")
                    except Exception as e:
                        errs.append(e)

            threads = [
                threading.Thread(target=complete_trips, args=(0, 25)),
                threading.Thread(target=complete_trips, args=(25, 50)),
                threading.Thread(target=complete_trips, args=(50, 75)),
                threading.Thread(target=complete_trips, args=(75, 100)),
            ]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert (
                not errors
            ), f"Iteration {iteration}: Errors during concurrent complete_trip: {errors}"
            assert len(matching_server._active_trips) == 0

    def test_pending_offers_concurrent_access(self):
        """Concurrent access to pending offers should not cause errors."""
        for iteration in range(STRESS_ITERATIONS):
            matching_server = create_matching_server()
            errors: list = []
            stop_event = threading.Event()

            def read_offers(
                server: MatchingServer = matching_server,
                errs: list = errors,
                stop: threading.Event = stop_event,
            ):
                while not stop.is_set():
                    try:
                        server.get_pending_offer_for_driver("driver_0")
                    except RuntimeError as e:
                        errs.append(e)
                        break

            def modify_offers(server: MatchingServer = matching_server):
                for i in range(500):
                    driver_id = f"driver_{i % 20}"
                    server._pending_offers[driver_id] = {
                        "trip_id": f"trip_{i}",
                        "surge_multiplier": 1.5,
                    }

                for i in range(20):
                    server._pending_offers.pop(f"driver_{i}", None)

            read_threads = [threading.Thread(target=read_offers) for _ in range(5)]
            modify_thread = threading.Thread(target=modify_offers)

            for t in read_threads:
                t.start()
            modify_thread.start()

            modify_thread.join()
            stop_event.set()
            for t in read_threads:
                t.join()

            assert (
                not errors
            ), f"Iteration {iteration}: Errors during concurrent pending offers access: {errors}"


class TestAgentRegistryManagerAtomicUpdates:
    """Test that multi-registry updates are atomic."""

    def test_driver_went_online_atomic_update(self):
        """driver_went_online should update all registries atomically.

        Without locking, concurrent calls could leave registries in inconsistent
        states (e.g., driver in index but not in registry).
        """
        num_drivers = 100

        for iteration in range(STRESS_ITERATIONS):
            driver_index = DriverGeospatialIndex()
            driver_registry = DriverRegistry()
            matching_server = Mock()

            registry_manager = AgentRegistryManager(
                driver_index=driver_index,
                driver_registry=driver_registry,
                matching_server=matching_server,
            )

            errors: list = []

            # Pre-register drivers in offline state
            for i in range(num_drivers):
                driver_registry.register_driver(
                    f"driver_{i}",
                    "offline",
                    zone_id=None,
                    location=(-23.56, -46.65),
                )

            def driver_online(
                driver_id: str,
                manager: AgentRegistryManager = registry_manager,
                errs: list = errors,
            ):
                try:
                    manager.driver_went_online(
                        driver_id=driver_id,
                        location=(-23.56, -46.65),
                        zone_id="zone_a",
                    )
                except Exception as e:
                    errs.append((driver_id, e))

            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [
                    executor.submit(driver_online, f"driver_{i}") for i in range(num_drivers)
                ]
                for future in as_completed(futures):
                    future.result()

            assert (
                not errors
            ), f"Iteration {iteration}: Errors during concurrent driver_went_online: {errors}"

            # Verify consistency: all drivers should be online in both registries
            online_in_registry = driver_registry.get_status_count("online")
            assert online_in_registry == num_drivers, (
                f"Iteration {iteration}: Registry has {online_in_registry} online drivers, "
                f"expected {num_drivers}"
            )

    def test_driver_status_changed_consistency(self):
        """driver_status_changed should update all registries consistently."""
        num_drivers = 50
        statuses = ["online", "en_route_pickup", "en_route_destination"]

        for iteration in range(STRESS_ITERATIONS):
            driver_index = DriverGeospatialIndex()
            driver_registry = DriverRegistry()
            matching_server = Mock()

            registry_manager = AgentRegistryManager(
                driver_index=driver_index,
                driver_registry=driver_registry,
                matching_server=matching_server,
            )

            for i in range(num_drivers):
                driver_registry.register_driver(
                    f"driver_{i}",
                    "online",
                    zone_id="zone_a",
                    location=(-23.56, -46.65),
                )
                driver_index.add_driver(f"driver_{i}", -23.56, -46.65, "online")

            errors: list = []

            def change_status(
                driver_id: str,
                iter_num: int,
                manager: AgentRegistryManager = registry_manager,
                errs: list = errors,
                sts: list = statuses,
            ):
                try:
                    new_status = sts[iter_num % len(sts)]
                    manager.driver_status_changed(driver_id, new_status)
                except Exception as e:
                    errs.append((driver_id, e))

            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = []
                for i in range(200):
                    driver_id = f"driver_{i % num_drivers}"
                    futures.append(executor.submit(change_status, driver_id, i))

                for future in as_completed(futures):
                    future.result()

            assert (
                not errors
            ), f"Iteration {iteration}: Errors during concurrent status changes: {errors}"

            # Verify no negative counts
            for status in statuses + ["offline", "en_route_destination"]:
                count = driver_registry.get_status_count(status)
                assert (
                    count >= 0
                ), f"Iteration {iteration}: Negative count for status {status}: {count}"

    def test_concurrent_online_offline_transitions(self):
        """Concurrent online/offline transitions should maintain consistency."""
        num_drivers = 30

        for iteration in range(STRESS_ITERATIONS):
            driver_index = DriverGeospatialIndex()
            driver_registry = DriverRegistry()
            matching_server = Mock()

            registry_manager = AgentRegistryManager(
                driver_index=driver_index,
                driver_registry=driver_registry,
                matching_server=matching_server,
            )

            errors: list = []

            for i in range(num_drivers):
                driver_registry.register_driver(
                    f"driver_{i}",
                    "offline",
                    zone_id=None,
                    location=(-23.56, -46.65),
                )

            def toggle_online_offline(
                driver_id: str,
                manager: AgentRegistryManager = registry_manager,
                errs: list = errors,
            ):
                for _ in range(20):
                    try:
                        manager.driver_went_online(
                            driver_id=driver_id,
                            location=(-23.56, -46.65),
                            zone_id="zone_a",
                        )
                        manager.driver_went_offline(driver_id)
                    except Exception as e:
                        errs.append((driver_id, e))

            with ThreadPoolExecutor(max_workers=15) as executor:
                futures = [
                    executor.submit(toggle_online_offline, f"driver_{i}")
                    for i in range(num_drivers)
                ]
                for future in as_completed(futures):
                    future.result()

            assert (
                not errors
            ), f"Iteration {iteration}: Errors during concurrent online/offline: {errors}"

            # All drivers should end up offline
            total_online = driver_registry.get_status_count("online")
            total_offline = driver_registry.get_status_count("offline")

            assert total_online + total_offline == num_drivers, (
                f"Iteration {iteration}: Total drivers ({total_online + total_offline}) "
                f"doesn't match expected ({num_drivers})"
            )
