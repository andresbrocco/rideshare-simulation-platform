from datetime import datetime
from unittest.mock import MagicMock

import pytest
import simpy

from events.schemas import SurgeUpdateEvent
from src.geo.zones import Zone
from src.matching.driver_registry import DriverRegistry
from src.matching.surge_pricing import SurgePricingCalculator


@pytest.fixture
def env():
    return simpy.Environment()


@pytest.fixture
def mock_zone_loader():
    loader = MagicMock()
    zones = [
        Zone(
            zone_id="pinheiros",
            name="Pinheiros",
            demand_multiplier=1.0,
            surge_sensitivity=1.0,
            geometry=[(-46.68, -23.56)],
            centroid=(-46.68, -23.56),
        ),
        Zone(
            zone_id="vila_madalena",
            name="Vila Madalena",
            demand_multiplier=1.0,
            surge_sensitivity=1.0,
            geometry=[(-46.69, -23.55)],
            centroid=(-46.69, -23.55),
        ),
    ]
    loader.get_all_zones.return_value = zones
    return loader


@pytest.fixture
def driver_registry():
    return DriverRegistry()


@pytest.fixture
def mock_kafka_producer():
    return MagicMock()


def test_surge_calculator_init(env, mock_zone_loader, driver_registry):
    calculator = SurgePricingCalculator(
        env=env,
        zone_loader=mock_zone_loader,
        driver_registry=driver_registry,
    )

    assert calculator is not None
    assert calculator.get_surge("pinheiros") == 1.0


def test_surge_no_demand(env, mock_zone_loader, driver_registry, mock_kafka_producer):
    calculator = SurgePricingCalculator(
        env=env,
        zone_loader=mock_zone_loader,
        driver_registry=driver_registry,
        kafka_producer=mock_kafka_producer,
    )

    for i in range(10):
        driver_registry.register_driver(f"driver{i}", "online", zone_id="pinheiros")

    calculator.set_pending_requests("pinheiros", 5)

    env.run(until=60)

    assert calculator.get_surge("pinheiros") == 1.0


def test_surge_balanced(env, mock_zone_loader, driver_registry, mock_kafka_producer):
    calculator = SurgePricingCalculator(
        env=env,
        zone_loader=mock_zone_loader,
        driver_registry=driver_registry,
        kafka_producer=mock_kafka_producer,
    )

    for i in range(10):
        driver_registry.register_driver(f"driver{i}", "online", zone_id="pinheiros")

    calculator.set_pending_requests("pinheiros", 10)

    env.run(until=60)

    assert calculator.get_surge("pinheiros") == 1.0


def test_surge_ratio_2_0(env, mock_zone_loader, driver_registry, mock_kafka_producer):
    calculator = SurgePricingCalculator(
        env=env,
        zone_loader=mock_zone_loader,
        driver_registry=driver_registry,
        kafka_producer=mock_kafka_producer,
    )

    for i in range(10):
        driver_registry.register_driver(f"driver{i}", "online", zone_id="pinheiros")

    calculator.set_pending_requests("pinheiros", 20)

    env.run(until=60)

    assert calculator.get_surge("pinheiros") == 1.5


def test_surge_ratio_3_0(env, mock_zone_loader, driver_registry, mock_kafka_producer):
    calculator = SurgePricingCalculator(
        env=env,
        zone_loader=mock_zone_loader,
        driver_registry=driver_registry,
        kafka_producer=mock_kafka_producer,
    )

    for i in range(10):
        driver_registry.register_driver(f"driver{i}", "online", zone_id="pinheiros")

    calculator.set_pending_requests("pinheiros", 30)

    env.run(until=60)

    assert calculator.get_surge("pinheiros") == 2.5


def test_surge_ratio_above_3_0(env, mock_zone_loader, driver_registry, mock_kafka_producer):
    calculator = SurgePricingCalculator(
        env=env,
        zone_loader=mock_zone_loader,
        driver_registry=driver_registry,
        kafka_producer=mock_kafka_producer,
    )

    for i in range(10):
        driver_registry.register_driver(f"driver{i}", "online", zone_id="pinheiros")

    calculator.set_pending_requests("pinheiros", 50)

    env.run(until=60)

    assert calculator.get_surge("pinheiros") == 2.5


def test_surge_linear_interpolation(env, mock_zone_loader, driver_registry, mock_kafka_producer):
    calculator = SurgePricingCalculator(
        env=env,
        zone_loader=mock_zone_loader,
        driver_registry=driver_registry,
        kafka_producer=mock_kafka_producer,
    )

    for i in range(10):
        driver_registry.register_driver(f"driver{i}", "online", zone_id="pinheiros")

    calculator.set_pending_requests("pinheiros", 15)

    env.run(until=60)

    assert calculator.get_surge("pinheiros") == 1.25


def test_surge_update_every_60_seconds(env, mock_zone_loader, driver_registry, mock_kafka_producer):
    calculator = SurgePricingCalculator(
        env=env,
        zone_loader=mock_zone_loader,
        driver_registry=driver_registry,
        kafka_producer=mock_kafka_producer,
    )

    for i in range(10):
        driver_registry.register_driver(f"driver{i}", "online", zone_id="pinheiros")

    calculator.set_pending_requests("pinheiros", 20)

    env.run(until=120)

    assert env.now == 120


def test_surge_per_zone(env, mock_zone_loader, driver_registry, mock_kafka_producer):
    calculator = SurgePricingCalculator(
        env=env,
        zone_loader=mock_zone_loader,
        driver_registry=driver_registry,
        kafka_producer=mock_kafka_producer,
    )

    for i in range(10):
        driver_registry.register_driver(f"driver{i}", "online", zone_id="pinheiros")
        driver_registry.register_driver(f"driver_vm{i}", "online", zone_id="vila_madalena")

    calculator.set_pending_requests("pinheiros", 20)
    calculator.set_pending_requests("vila_madalena", 10)

    env.run(until=60)

    assert calculator.get_surge("pinheiros") == 1.5
    assert calculator.get_surge("vila_madalena") == 1.0


def test_surge_event_emission(env, mock_zone_loader, driver_registry, mock_kafka_producer):
    calculator = SurgePricingCalculator(
        env=env,
        zone_loader=mock_zone_loader,
        driver_registry=driver_registry,
        kafka_producer=mock_kafka_producer,
    )

    for i in range(10):
        driver_registry.register_driver(f"driver{i}", "online", zone_id="pinheiros")

    calculator.set_pending_requests("pinheiros", 20)

    env.run(until=60)

    assert mock_kafka_producer.produce.called
    call_args = mock_kafka_producer.produce.call_args
    event = call_args[1]["value"]

    assert isinstance(event, SurgeUpdateEvent)
    assert event.zone_id == "pinheiros"
    assert event.previous_multiplier == 1.0
    assert event.new_multiplier == 1.5
    assert event.available_drivers == 10
    assert event.pending_requests == 20


def test_no_event_if_unchanged(env, mock_zone_loader, driver_registry, mock_kafka_producer):
    calculator = SurgePricingCalculator(
        env=env,
        zone_loader=mock_zone_loader,
        driver_registry=driver_registry,
        kafka_producer=mock_kafka_producer,
    )

    for i in range(10):
        driver_registry.register_driver(f"driver{i}", "online", zone_id="pinheiros")

    calculator.set_pending_requests("pinheiros", 5)

    env.run(until=120)

    assert not mock_kafka_producer.produce.called


def test_zero_drivers_available(env, mock_zone_loader, driver_registry, mock_kafka_producer):
    calculator = SurgePricingCalculator(
        env=env,
        zone_loader=mock_zone_loader,
        driver_registry=driver_registry,
        kafka_producer=mock_kafka_producer,
    )

    calculator.set_pending_requests("pinheiros", 10)

    env.run(until=60)

    assert calculator.get_surge("pinheiros") == 2.5


def test_zero_requests(env, mock_zone_loader, driver_registry, mock_kafka_producer):
    calculator = SurgePricingCalculator(
        env=env,
        zone_loader=mock_zone_loader,
        driver_registry=driver_registry,
        kafka_producer=mock_kafka_producer,
    )

    for i in range(10):
        driver_registry.register_driver(f"driver{i}", "online", zone_id="pinheiros")

    calculator.set_pending_requests("pinheiros", 0)

    env.run(until=60)

    assert calculator.get_surge("pinheiros") == 1.0


def test_get_current_surge(env, mock_zone_loader, driver_registry):
    calculator = SurgePricingCalculator(
        env=env,
        zone_loader=mock_zone_loader,
        driver_registry=driver_registry,
    )

    for i in range(10):
        driver_registry.register_driver(f"driver{i}", "online", zone_id="pinheiros")

    calculator.set_pending_requests("pinheiros", 20)

    env.run(until=60)

    assert calculator.get_surge("pinheiros") == 1.5
