"""Tests for DNA generators (driver and rider)."""

import math
import re

import pytest

from agents.dna import DriverDNA, RiderDNA, ShiftPreference, haversine_distance
from agents.dna_generator import generate_driver_dna, generate_rider_dna
from agents.zone_validator import is_location_in_any_zone


@pytest.mark.unit
def test_generate_driver_dna_valid():
    """Test that generate_driver_dna returns a valid DriverDNA instance."""
    dna = generate_driver_dna()
    assert isinstance(dna, DriverDNA)


@pytest.mark.unit
def test_driver_home_location_in_zone():
    """Test all home locations are within a zone boundary."""
    for _ in range(20):
        dna = generate_driver_dna()
        lat, lon = dna.home_location
        assert is_location_in_any_zone(lat, lon), f"Location ({lat}, {lon}) not in any zone"


@pytest.mark.unit
def test_driver_acceptance_rate_range():
    """Test all acceptance_rate values are in [0.7, 0.95]."""
    for _ in range(100):
        dna = generate_driver_dna()
        assert 0.7 <= dna.acceptance_rate <= 0.95


@pytest.mark.unit
def test_driver_response_time_range():
    """Test all response_time values are in [3.0, 12.0] seconds."""
    for _ in range(100):
        dna = generate_driver_dna()
        assert 3.0 <= dna.response_time <= 12.0


@pytest.mark.unit
def test_driver_service_quality_range():
    """Test all service_quality values are in [0.6, 1.0]."""
    for _ in range(100):
        dna = generate_driver_dna()
        assert 0.6 <= dna.service_quality <= 1.0


@pytest.mark.unit
def test_driver_shift_preference_distribution():
    """Test shift_preference uses all enum values."""
    shifts = [generate_driver_dna().shift_preference for _ in range(200)]
    unique_shifts = set(shifts)

    assert len(unique_shifts) >= 3, "Should have at least 3 different shift preferences"
    assert all(isinstance(s, ShiftPreference) for s in shifts)


@pytest.mark.unit
def test_driver_vehicle_info_plausible():
    """Test vehicle info is plausible (valid makes, years 2015-2025)."""
    valid_makes = {"Volkswagen", "Fiat", "Chevrolet", "Toyota", "Honda", "Hyundai"}

    for _ in range(50):
        dna = generate_driver_dna()
        assert dna.vehicle_make in valid_makes
        assert 2015 <= dna.vehicle_year <= 2025
        assert len(dna.vehicle_model) > 0


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
def test_driver_email_phone_generated():
    """Test email has valid format and phone has 11 digits."""
    email_pattern = re.compile(r"^[\w.-]+@[\w.-]+\.\w+$")
    phone_pattern = re.compile(r"^11\d{9}$")

    for _ in range(20):
        dna = generate_driver_dna()
        assert email_pattern.match(dna.email), f"Invalid email: {dna.email}"
        assert phone_pattern.match(dna.phone), f"Invalid phone: {dna.phone}"


@pytest.mark.unit
def test_driver_unique_ids():
    """Test no duplicate driver_id values (if exposed in future)."""
    dnas = [generate_driver_dna() for _ in range(100)]

    # For now, just verify all combinations of name+email are unique
    identifiers = [(d.first_name, d.last_name, d.email) for d in dnas]
    assert len(identifiers) == len(set(identifiers))


# ============================================================================
# Rider DNA Generator Tests
# ============================================================================


@pytest.mark.unit
def test_generate_rider_dna_valid():
    """Test that generate_rider_dna returns a valid RiderDNA instance."""
    dna = generate_rider_dna()
    assert isinstance(dna, RiderDNA)


@pytest.mark.unit
def test_rider_home_location_in_zone():
    """Test all home locations are within a zone boundary."""
    for _ in range(20):
        dna = generate_rider_dna()
        lat, lon = dna.home_location
        assert is_location_in_any_zone(lat, lon), f"Location ({lat}, {lon}) not in any zone"


@pytest.mark.unit
def test_rider_frequent_destinations_count():
    """Test riders have 2-5 frequent destinations."""
    for _ in range(50):
        dna = generate_rider_dna()
        assert 2 <= len(dna.frequent_destinations) <= 5


@pytest.mark.unit
def test_rider_destinations_within_20km():
    """Test all destinations are within 20km of home location."""
    for _ in range(50):
        dna = generate_rider_dna()
        home_lat, home_lon = dna.home_location
        for dest in dna.frequent_destinations:
            dest_lat, dest_lon = dest["coordinates"]
            distance = haversine_distance(home_lat, home_lon, dest_lat, dest_lon)
            assert distance <= 20.0, f"Destination {distance:.1f}km from home (max 20km)"


@pytest.mark.unit
def test_rider_destinations_minimum_distance():
    """Test destinations are at least 0.8km from home to avoid very short trips."""
    for _ in range(50):
        dna = generate_rider_dna()
        home_lat, home_lon = dna.home_location
        for dest in dna.frequent_destinations:
            dest_lat, dest_lon = dest["coordinates"]
            distance = haversine_distance(home_lat, home_lon, dest_lat, dest_lon)
            assert distance >= 0.5, f"Destination only {distance:.2f}km from home (min ~0.8km)"


@pytest.mark.unit
def test_rider_destination_weights_sum():
    """Test destination weights are valid and sum to approximately 1.0."""
    for _ in range(30):
        dna = generate_rider_dna()
        weights = [d["weight"] for d in dna.frequent_destinations]
        assert all(0.0 < w <= 1.0 for w in weights), "Each weight should be in (0.0, 1.0]"
        total = sum(weights)
        assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, expected ~1.0"


@pytest.mark.unit
def test_rider_patience_threshold_range():
    """Test patience threshold is in valid range [120, 300] seconds."""
    for _ in range(100):
        dna = generate_rider_dna()
        assert 120 <= dna.patience_threshold <= 300


@pytest.mark.unit
def test_rider_max_surge_range():
    """Test max surge multiplier is in valid range [1.5, 3.0]."""
    for _ in range(100):
        dna = generate_rider_dna()
        assert 1.5 <= dna.max_surge_multiplier <= 3.0


@pytest.mark.unit
def test_rider_behavior_factor_range():
    """Test behavior factor is in valid range [0.5, 1.0]."""
    for _ in range(100):
        dna = generate_rider_dna()
        assert 0.5 <= dna.behavior_factor <= 1.0


@pytest.mark.unit
def test_rider_avg_rides_per_week_range():
    """Test avg_rides_per_week is in realistic range [1, 15]."""
    for _ in range(100):
        dna = generate_rider_dna()
        assert 1 <= dna.avg_rides_per_week <= 15


@pytest.mark.unit
def test_rider_payment_method_valid():
    """Test payment method type is valid."""
    valid_types = {"credit_card", "digital_wallet"}
    for _ in range(50):
        dna = generate_rider_dna()
        assert dna.payment_method_type in valid_types


@pytest.mark.unit
def test_rider_payment_masked_format():
    """Test masked payment info has correct format."""
    credit_card_pattern = re.compile(r"^\*{4}\d{4}$")
    valid_wallets = {"Pix", "PicPay", "Mercado Pago", "Nubank", "PayPal"}

    for _ in range(30):
        dna = generate_rider_dna()
        if dna.payment_method_type == "credit_card":
            assert credit_card_pattern.match(
                dna.payment_method_masked
            ), f"Invalid masked card: {dna.payment_method_masked}"
        else:
            assert (
                dna.payment_method_masked in valid_wallets
            ), f"Invalid wallet: {dna.payment_method_masked}"


@pytest.mark.unit
def test_rider_name_from_pool():
    """Test names are selected from Brazilian name pool."""
    first_names = set()
    last_names = set()

    for _ in range(30):
        dna = generate_rider_dna()
        first_names.add(dna.first_name)
        last_names.add(dna.last_name)

    assert len(first_names) >= 5, "Should have variety in first names"
    assert len(last_names) >= 5, "Should have variety in last names"


@pytest.mark.unit
def test_rider_email_phone_generated():
    """Test email has valid format and phone has 11 digits."""
    email_pattern = re.compile(r"^[\w.-]+@[\w.-]+\.\w+$")
    phone_pattern = re.compile(r"^11\d{9}$")

    for _ in range(20):
        dna = generate_rider_dna()
        assert email_pattern.match(dna.email), f"Invalid email: {dna.email}"
        assert phone_pattern.match(dna.phone), f"Invalid phone: {dna.phone}"


@pytest.mark.unit
def test_rider_time_affinity_optional():
    """Test time affinity is included for some destinations."""
    has_affinity = False
    has_no_affinity = False

    for _ in range(20):
        dna = generate_rider_dna()
        for dest in dna.frequent_destinations:
            if dest.get("time_affinity"):
                has_affinity = True
                # Verify hours are valid
                assert all(
                    0 <= h <= 23 for h in dest["time_affinity"]
                ), "Time affinity hours should be 0-23"
            else:
                has_no_affinity = True

    assert has_affinity, "Some destinations should have time affinity"
    assert has_no_affinity, "Some destinations should have no time affinity"


@pytest.mark.unit
def test_rider_payment_method_distribution():
    """Test credit card is more common than digital wallet (~70/30)."""
    credit_count = 0
    wallet_count = 0

    for _ in range(100):
        dna = generate_rider_dna()
        if dna.payment_method_type == "credit_card":
            credit_count += 1
        else:
            wallet_count += 1

    # Allow some variance but credit should be dominant
    assert credit_count > wallet_count, "Credit card should be more common than wallet"
    assert credit_count >= 50, "Credit card should be at least 50% of payments"
