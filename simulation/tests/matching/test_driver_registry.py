import pytest

from src.matching.driver_registry import DriverRegistry


@pytest.fixture
def registry():
    return DriverRegistry()


@pytest.fixture
def populated_registry():
    reg = DriverRegistry()
    reg.register_driver("driver1", "online", zone_id="pinheiros", location=(-23.561, -46.682))
    reg.register_driver("driver2", "online", zone_id="pinheiros", location=(-23.562, -46.683))
    reg.register_driver("driver3", "busy", zone_id="pinheiros", location=(-23.563, -46.684))
    reg.register_driver("driver4", "online", zone_id="vila_madalena", location=(-23.545, -46.690))
    reg.register_driver("driver5", "offline", zone_id="vila_madalena", location=(-23.546, -46.691))
    return reg


def test_registry_init(registry):
    assert registry.get_status_count("online") == 0
    assert registry.get_status_count("offline") == 0
    assert registry.get_status_count("busy") == 0
    assert registry.get_status_count("en_route_pickup") == 0
    assert registry.get_status_count("en_route_destination") == 0


def test_register_driver(registry):
    registry.register_driver("driver1", "offline", zone_id="pinheiros")
    assert registry.get_status_count("offline") == 1
    assert registry.get_zone_driver_count("pinheiros", "offline") == 1


def test_update_driver_status(registry):
    registry.register_driver("driver1", "online", zone_id="pinheiros")
    registry.update_driver_status("driver1", "busy")

    assert registry.get_status_count("online") == 0
    assert registry.get_status_count("busy") == 1
    assert registry.get_zone_driver_count("pinheiros", "online") == 0
    assert registry.get_zone_driver_count("pinheiros", "busy") == 1


def test_unregister_driver(registry):
    registry.register_driver("driver1", "online", zone_id="pinheiros")
    assert registry.get_status_count("online") == 1

    registry.unregister_driver("driver1")
    assert registry.get_status_count("online") == 0
    assert registry.get_zone_driver_count("pinheiros", "online") == 0


def test_get_status_count(populated_registry):
    assert populated_registry.get_status_count("online") == 3
    assert populated_registry.get_status_count("busy") == 1
    assert populated_registry.get_status_count("offline") == 1
    assert populated_registry.get_status_count("en_route_pickup") == 0


def test_get_zone_driver_count(populated_registry):
    assert populated_registry.get_zone_driver_count("pinheiros", "online") == 2
    assert populated_registry.get_zone_driver_count("pinheiros", "busy") == 1
    assert populated_registry.get_zone_driver_count("vila_madalena", "online") == 1
    assert populated_registry.get_zone_driver_count("vila_madalena", "offline") == 1


def test_get_available_drivers_in_zone(populated_registry):
    available = populated_registry.get_available_drivers_in_zone("pinheiros")
    assert len(available) == 2
    assert "driver1" in available
    assert "driver2" in available
    assert "driver3" not in available  # busy, not available


def test_status_transition_online_to_busy(registry):
    registry.register_driver("driver1", "online", zone_id="pinheiros")
    registry.update_driver_status("driver1", "busy")

    assert registry.get_status_count("online") == 0
    assert registry.get_status_count("busy") == 1


def test_status_transition_busy_to_en_route(registry):
    registry.register_driver("driver1", "busy", zone_id="pinheiros")
    registry.update_driver_status("driver1", "en_route_pickup")

    assert registry.get_status_count("busy") == 0
    assert registry.get_status_count("en_route_pickup") == 1


def test_status_transition_en_route_to_online(registry):
    registry.register_driver("driver1", "en_route_destination", zone_id="pinheiros")
    registry.update_driver_status("driver1", "online")

    assert registry.get_status_count("en_route_destination") == 0
    assert registry.get_status_count("online") == 1


def test_status_transition_online_to_offline(registry):
    registry.register_driver("driver1", "online", zone_id="pinheiros")
    registry.update_driver_status("driver1", "offline")

    assert registry.get_status_count("online") == 0
    assert registry.get_status_count("offline") == 1


def test_multiple_zones(populated_registry):
    assert populated_registry.get_zone_driver_count("pinheiros", "online") == 2
    assert populated_registry.get_zone_driver_count("vila_madalena", "online") == 1
    assert populated_registry.get_zone_driver_count("pinheiros", "busy") == 1


def test_driver_zone_update(registry):
    registry.register_driver("driver1", "online", zone_id="pinheiros")
    assert registry.get_zone_driver_count("pinheiros", "online") == 1

    registry.update_driver_zone("driver1", "vila_madalena")
    assert registry.get_zone_driver_count("pinheiros", "online") == 0
    assert registry.get_zone_driver_count("vila_madalena", "online") == 1


def test_get_all_statuses_summary(populated_registry):
    summary = populated_registry.get_all_status_counts()

    assert summary["online"] == 3
    assert summary["busy"] == 1
    assert summary["offline"] == 1
    assert summary["en_route_pickup"] == 0
    assert summary["en_route_destination"] == 0


def test_unregister_nonexistent_driver(registry):
    registry.unregister_driver("nonexistent")
    assert registry.get_status_count("online") == 0


def test_update_status_of_nonexistent_driver(registry):
    registry.update_driver_status("nonexistent", "busy")
    assert registry.get_status_count("busy") == 0


def test_update_driver_location(registry):
    registry.register_driver("driver1", "online", zone_id="pinheiros", location=(-23.561, -46.682))

    new_location = (-23.570, -46.690)
    registry.update_driver_location("driver1", new_location)

    drivers = registry.get_available_drivers_in_zone("pinheiros")
    assert "driver1" in drivers


def test_register_driver_without_zone(registry):
    registry.register_driver("driver1", "offline")
    assert registry.get_status_count("offline") == 1


def test_available_drivers_excludes_all_non_online_statuses(registry):
    registry.register_driver("driver1", "online", zone_id="pinheiros")
    registry.register_driver("driver2", "busy", zone_id="pinheiros")
    registry.register_driver("driver3", "offline", zone_id="pinheiros")
    registry.register_driver("driver4", "en_route_pickup", zone_id="pinheiros")
    registry.register_driver("driver5", "en_route_destination", zone_id="pinheiros")

    available = registry.get_available_drivers_in_zone("pinheiros")
    assert len(available) == 1
    assert "driver1" in available
