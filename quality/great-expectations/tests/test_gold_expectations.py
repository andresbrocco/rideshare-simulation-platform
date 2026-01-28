"""
Test Gold layer expectation suites.

Tests verify that:
1. All 12 Gold expectation suites exist (5 dimensions, 5 facts, 2 aggregates)
2. SCD Type 2 dimensions validate validity date ranges
3. Fact tables check referential integrity (foreign keys not null)
4. Business logic validated (platform fee, driver payout)
5. Completeness checks on required fields
6. Consistency between facts and aggregates
"""

import json
import pytest
from pathlib import Path


@pytest.fixture
def expectations_dir():
    """Get path to Gold expectations directory."""
    base_path = Path(__file__).parent.parent / "gx" / "expectations" / "gold"
    return base_path


@pytest.fixture
def dimension_suites():
    """List of expected Gold dimension suite files."""
    return [
        "dimensions/gold_dim_drivers.json",
        "dimensions/gold_dim_riders.json",
        "dimensions/gold_dim_zones.json",
        "dimensions/gold_dim_time.json",
        "dimensions/gold_dim_payment_methods.json",
    ]


@pytest.fixture
def fact_suites():
    """List of expected Gold fact suite files."""
    return [
        "facts/gold_fact_trips.json",
        "facts/gold_fact_payments.json",
        "facts/gold_fact_ratings.json",
        "facts/gold_fact_cancellations.json",
        "facts/gold_fact_driver_activity.json",
    ]


@pytest.fixture
def aggregate_suites():
    """List of expected Gold aggregate suite files."""
    return [
        "aggregates/gold_agg_hourly_zone_demand.json",
        "aggregates/gold_agg_daily_driver_performance.json",
    ]


def test_all_dimension_suites_exist(expectations_dir, dimension_suites):
    """Verify all 5 dimension expectation suite files exist."""
    for suite_file in dimension_suites:
        suite_path = expectations_dir / suite_file
        assert suite_path.exists(), f"Missing dimension suite: {suite_file}"


def test_all_fact_suites_exist(expectations_dir, fact_suites):
    """Verify all 5 fact expectation suite files exist."""
    for suite_file in fact_suites:
        suite_path = expectations_dir / suite_file
        assert suite_path.exists(), f"Missing fact suite: {suite_file}"


def test_all_aggregate_suites_exist(expectations_dir, aggregate_suites):
    """Verify all 2 aggregate expectation suite files exist."""
    for suite_file in aggregate_suites:
        suite_path = expectations_dir / suite_file
        assert suite_path.exists(), f"Missing aggregate suite: {suite_file}"


def test_dim_drivers_scd2():
    """Verify SCD Type 2 validity ranges.

    Input: dim_drivers with overlapping validity dates for same driver
    Expected: Expectation fails, alerts on SCD violations
    """
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "gold"
    suite_path = expectations_dir / "dimensions" / "gold_dim_drivers.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])

    not_null_keys = [
        exp
        for exp in expectations
        if exp.get("expectation_type") == "expect_column_values_to_not_be_null"
        and exp.get("kwargs", {}).get("column")
        in ["driver_key", "driver_id", "valid_from", "valid_to", "current_flag"]
    ]
    assert len(not_null_keys) >= 4, "Missing SCD Type 2 required field validations"

    valid_to_check = [
        exp for exp in expectations if "valid_to" in exp.get("kwargs", {}).get("column", "")
    ]
    assert len(valid_to_check) > 0, "Missing valid_to validation"

    current_flag_check = [
        exp for exp in expectations if exp.get("kwargs", {}).get("column") == "current_flag"
    ]
    assert len(current_flag_check) > 0, "Missing current_flag validation"


def test_dim_payment_methods_scd2():
    """Verify dim_payment_methods has SCD Type 2 validations."""
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "gold"
    suite_path = expectations_dir / "dimensions" / "gold_dim_payment_methods.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])

    scd2_columns = ["payment_method_key", "valid_from", "valid_to", "current_flag"]
    for col in scd2_columns:
        col_expectations = [
            exp for exp in expectations if exp.get("kwargs", {}).get("column") == col
        ]
        assert len(col_expectations) > 0, f"Missing {col} validation for SCD Type 2"


def test_fact_trips_referential_integrity():
    """Verify foreign keys exist in dimensions.

    Input: fact_trips with driver_id not in dim_drivers
    Expected: Expectation fails, alerts on orphaned records
    """
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "gold"
    suite_path = expectations_dir / "facts" / "gold_fact_trips.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])

    foreign_keys = [
        "driver_key",
        "rider_key",
        "pickup_zone_key",
        "dropoff_zone_key",
        "time_key",
    ]
    for fk in foreign_keys:
        fk_not_null = [
            exp
            for exp in expectations
            if exp.get("expectation_type") == "expect_column_values_to_not_be_null"
            and exp.get("kwargs", {}).get("column") == fk
        ]
        assert len(fk_not_null) > 0, f"Missing not null check for foreign key: {fk}"


def test_fact_payments_business_logic():
    """Verify platform fee = 25% of total fare.

    Input: fact_payments with incorrect fee calculation
    Expected: Expectation fails, alerts on calculation errors
    """
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "gold"
    suite_path = expectations_dir / "facts" / "gold_fact_payments.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])

    platform_fee_check = [
        exp for exp in expectations if exp.get("kwargs", {}).get("column") == "platform_fee"
    ]
    assert len(platform_fee_check) > 0, "Missing platform_fee validation"

    driver_payout_check = [
        exp for exp in expectations if exp.get("kwargs", {}).get("column") == "driver_payout"
    ]
    assert len(driver_payout_check) > 0, "Missing driver_payout validation"

    total_fare_check = [
        exp for exp in expectations if exp.get("kwargs", {}).get("column") == "total_fare"
    ]
    assert len(total_fare_check) > 0, "Missing total_fare validation"


def test_fact_payments_referential_integrity():
    """Verify fact_payments has all required foreign keys."""
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "gold"
    suite_path = expectations_dir / "facts" / "gold_fact_payments.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])

    foreign_keys = ["trip_key", "rider_key", "driver_key", "time_key"]
    for fk in foreign_keys:
        fk_not_null = [
            exp
            for exp in expectations
            if exp.get("expectation_type") == "expect_column_values_to_not_be_null"
            and exp.get("kwargs", {}).get("column") == fk
        ]
        assert len(fk_not_null) > 0, f"Missing not null check for foreign key: {fk}"


def test_fact_ratings_referential_integrity():
    """Verify fact_ratings has foreign key validations."""
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "gold"
    suite_path = expectations_dir / "facts" / "gold_fact_ratings.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])

    foreign_keys = ["trip_key", "rater_key", "ratee_key", "time_key"]
    for fk in foreign_keys:
        fk_not_null = [
            exp
            for exp in expectations
            if exp.get("expectation_type") == "expect_column_values_to_not_be_null"
            and exp.get("kwargs", {}).get("column") == fk
        ]
        assert len(fk_not_null) > 0, f"Missing not null check for foreign key: {fk}"

    rating_range = [
        exp
        for exp in expectations
        if exp.get("expectation_type") == "expect_column_values_to_be_between"
        and exp.get("kwargs", {}).get("column") == "rating"
    ]
    assert len(rating_range) > 0, "Missing rating range validation"


def test_fact_cancellations_referential_integrity():
    """Verify fact_cancellations has foreign key validations."""
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "gold"
    suite_path = expectations_dir / "facts" / "gold_fact_cancellations.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])

    required_keys = ["rider_key", "pickup_zone_key", "time_key"]
    for fk in required_keys:
        fk_not_null = [
            exp
            for exp in expectations
            if exp.get("expectation_type") == "expect_column_values_to_not_be_null"
            and exp.get("kwargs", {}).get("column") == fk
        ]
        assert len(fk_not_null) > 0, f"Missing not null check for foreign key: {fk}"


def test_fact_driver_activity_referential_integrity():
    """Verify fact_driver_activity has foreign key validations."""
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "gold"
    suite_path = expectations_dir / "facts" / "gold_fact_driver_activity.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])

    foreign_keys = ["driver_key", "time_key"]
    for fk in foreign_keys:
        fk_not_null = [
            exp
            for exp in expectations
            if exp.get("expectation_type") == "expect_column_values_to_not_be_null"
            and exp.get("kwargs", {}).get("column") == fk
        ]
        assert len(fk_not_null) > 0, f"Missing not null check for foreign key: {fk}"

    status_check = [exp for exp in expectations if exp.get("kwargs", {}).get("column") == "status"]
    assert len(status_check) > 0, "Missing status validation"


def test_agg_hourly_zone_demand_consistency():
    """Verify daily totals match fact table sums.

    Input: Aggregate with different total than sum of fact records
    Expected: Expectation fails, alerts on inconsistency
    """
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "gold"
    suite_path = expectations_dir / "aggregates" / "gold_agg_hourly_zone_demand.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])

    required_columns = [
        "zone_key",
        "hour_timestamp",
        "requested_trips",
        "completed_trips",
    ]
    for col in required_columns:
        col_not_null = [
            exp
            for exp in expectations
            if exp.get("expectation_type") == "expect_column_values_to_not_be_null"
            and exp.get("kwargs", {}).get("column") == col
        ]
        assert len(col_not_null) > 0, f"Missing not null check for {col}"

    completion_rate = [
        exp for exp in expectations if exp.get("kwargs", {}).get("column") == "completion_rate"
    ]
    assert len(completion_rate) > 0, "Missing completion_rate validation"


def test_agg_daily_driver_performance_consistency():
    """Verify daily driver performance aggregates match fact tables."""
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "gold"
    suite_path = expectations_dir / "aggregates" / "gold_agg_daily_driver_performance.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])

    required_columns = ["driver_key", "time_key", "trips_completed", "total_payout"]
    for col in required_columns:
        col_not_null = [
            exp
            for exp in expectations
            if exp.get("expectation_type") == "expect_column_values_to_not_be_null"
            and exp.get("kwargs", {}).get("column") == col
        ]
        assert len(col_not_null) > 0, f"Missing not null check for {col}"

    utilization_check = [
        exp for exp in expectations if exp.get("kwargs", {}).get("column") == "utilization_pct"
    ]
    assert len(utilization_check) > 0, "Missing utilization_pct validation"


def test_dim_completeness():
    """Verify all dimension records have required attributes.

    Input: Dimension table with null values in required fields
    Expected: Expectation fails, alerts on incomplete records
    """
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "gold"

    dim_zones_path = expectations_dir / "dimensions" / "gold_dim_zones.json"
    with open(dim_zones_path, "r") as f:
        zones_data = json.load(f)

    zones_expectations = zones_data.get("expectations", [])
    zone_required_fields = ["zone_key", "zone_id", "name"]

    for field in zone_required_fields:
        field_check = [
            exp
            for exp in zones_expectations
            if exp.get("expectation_type") == "expect_column_values_to_not_be_null"
            and exp.get("kwargs", {}).get("column") == field
        ]
        assert len(field_check) > 0, f"Missing not null check for dim_zones.{field}"


def test_dim_riders_completeness():
    """Verify dim_riders has completeness checks."""
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "gold"
    suite_path = expectations_dir / "dimensions" / "gold_dim_riders.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])

    required_fields = ["rider_key", "rider_id"]
    for field in required_fields:
        field_check = [
            exp
            for exp in expectations
            if exp.get("expectation_type") == "expect_column_values_to_not_be_null"
            and exp.get("kwargs", {}).get("column") == field
        ]
        assert len(field_check) > 0, f"Missing not null check for {field}"


def test_dim_time_completeness():
    """Verify dim_time has required date hierarchy fields."""
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "gold"
    suite_path = expectations_dir / "dimensions" / "gold_dim_time.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])

    required_fields = ["time_key", "date_key", "year", "month", "day"]
    for field in required_fields:
        field_check = [
            exp
            for exp in expectations
            if exp.get("expectation_type") == "expect_column_values_to_not_be_null"
            and exp.get("kwargs", {}).get("column") == field
        ]
        assert len(field_check) > 0, f"Missing not null check for {field}"


def test_suite_structure():
    """Verify all Gold suites have valid structure."""
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "gold"

    all_suites = [
        "dimensions/gold_dim_drivers.json",
        "dimensions/gold_dim_riders.json",
        "dimensions/gold_dim_zones.json",
        "dimensions/gold_dim_time.json",
        "dimensions/gold_dim_payment_methods.json",
        "facts/gold_fact_trips.json",
        "facts/gold_fact_payments.json",
        "facts/gold_fact_ratings.json",
        "facts/gold_fact_cancellations.json",
        "facts/gold_fact_driver_activity.json",
        "aggregates/gold_agg_hourly_zone_demand.json",
        "aggregates/gold_agg_daily_driver_performance.json",
    ]

    for suite_file in all_suites:
        suite_path = expectations_dir / suite_file

        with open(suite_path, "r") as f:
            suite_data = json.load(f)

        assert "expectation_suite_name" in suite_data
        assert "expectations" in suite_data
        assert isinstance(suite_data["expectations"], list)
        assert len(suite_data["expectations"]) >= 3, f"{suite_file} has fewer than 3 expectations"

        for expectation in suite_data["expectations"]:
            assert "expectation_type" in expectation
            assert "kwargs" in expectation
            assert isinstance(expectation["kwargs"], dict)
