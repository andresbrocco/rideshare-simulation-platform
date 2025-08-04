"""Tests for driver DNA generator."""

import re

import pytest

from agents.dna import DriverDNA, ShiftPreference
from agents.dna_generator import generate_driver_dna


def test_generate_driver_dna_valid():
    """Test that generate_driver_dna returns a valid DriverDNA instance."""
    dna = generate_driver_dna()
    assert isinstance(dna, DriverDNA)


def test_driver_home_location_in_sao_paulo():
    """Test all home locations are within Sao Paulo bounds."""
    for _ in range(100):
        dna = generate_driver_dna()
        lat, lon = dna.home_location
        assert -24.0 <= lat <= -23.0, f"Latitude {lat} out of bounds"
        assert -47.0 <= lon <= -46.0, f"Longitude {lon} out of bounds"


def test_driver_acceptance_rate_range():
    """Test all acceptance_rate values are in [0.7, 0.95]."""
    for _ in range(100):
        dna = generate_driver_dna()
        assert 0.7 <= dna.acceptance_rate <= 0.95


def test_driver_response_time_range():
    """Test all response_time values are in [3.0, 12.0] seconds."""
    for _ in range(100):
        dna = generate_driver_dna()
        assert 3.0 <= dna.response_time <= 12.0


def test_driver_service_quality_range():
    """Test all service_quality values are in [0.6, 1.0]."""
    for _ in range(100):
        dna = generate_driver_dna()
        assert 0.6 <= dna.service_quality <= 1.0


def test_driver_shift_preference_distribution():
    """Test shift_preference uses all enum values."""
    shifts = [generate_driver_dna().shift_preference for _ in range(200)]
    unique_shifts = set(shifts)

    assert len(unique_shifts) >= 3, "Should have at least 3 different shift preferences"
    assert all(isinstance(s, ShiftPreference) for s in shifts)


def test_driver_vehicle_info_plausible():
    """Test vehicle info is plausible (valid makes, years 2015-2025)."""
    valid_makes = {"Volkswagen", "Fiat", "Chevrolet", "Toyota", "Honda", "Hyundai"}

    for _ in range(50):
        dna = generate_driver_dna()
        assert dna.vehicle_make in valid_makes
        assert 2015 <= dna.vehicle_year <= 2025
        assert len(dna.vehicle_model) > 0


def test_driver_license_plate_format():
    """Test license plates match ABC-1234 or ABC1D23 format."""
    old_pattern = re.compile(r"^[A-Z]{3}-\d{4}$")
    new_pattern = re.compile(r"^[A-Z]{3}\d[A-Z]\d{2}$")

    for _ in range(20):
        dna = generate_driver_dna()
        plate = dna.license_plate
        assert old_pattern.match(plate) or new_pattern.match(
            plate
        ), f"Invalid license plate format: {plate}"


def test_driver_name_from_pool():
    """Test names come from predefined Brazilian name list."""
    first_names = set()
    last_names = set()

    for _ in range(30):
        dna = generate_driver_dna()
        first_names.add(dna.first_name)
        last_names.add(dna.last_name)

    assert len(first_names) >= 5, "Should have variety in first names"
    assert len(last_names) >= 5, "Should have variety in last names"


def test_driver_email_phone_generated():
    """Test email has valid format and phone has 11 digits."""
    email_pattern = re.compile(r"^[\w.]+@[\w.]+\.\w+$")
    phone_pattern = re.compile(r"^11\d{9}$")

    for _ in range(20):
        dna = generate_driver_dna()
        assert email_pattern.match(dna.email), f"Invalid email: {dna.email}"
        assert phone_pattern.match(dna.phone), f"Invalid phone: {dna.phone}"


def test_driver_unique_ids():
    """Test no duplicate driver_id values (if exposed in future)."""
    dnas = [generate_driver_dna() for _ in range(100)]

    # For now, just verify all combinations of name+email are unique
    identifiers = [(d.first_name, d.last_name, d.email) for d in dnas]
    assert len(identifiers) == len(set(identifiers))


def test_driver_preferred_zones_valid():
    """Test preferred_zones contains 1-3 zone IDs."""
    for _ in range(20):
        dna = generate_driver_dna()
        assert 1 <= len(dna.preferred_zones) <= 3
        assert all(isinstance(zone, str) for zone in dna.preferred_zones)
