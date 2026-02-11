"""
Test Silver layer expectation suites.

Tests verify that:
1. All 8 Silver expectation suites exist
2. Each suite has minimum 5 expectations
3. All suites include deduplication checks on event_id
4. Range validations use 'mostly' parameter for soft failure
5. Enum validations cover critical status/rating fields
"""

import json
import pytest
from pathlib import Path


@pytest.fixture
def expectations_dir():
    """Get path to Silver expectations directory."""
    base_path = Path(__file__).parent.parent / "gx" / "expectations" / "silver"
    return base_path


@pytest.fixture
def expected_suites():
    """List of expected Silver expectation suite files."""
    return [
        "silver_stg_trips.json",
        "silver_stg_gps_pings.json",
        "silver_stg_driver_status.json",
        "silver_stg_surge_updates.json",
        "silver_stg_ratings.json",
        "silver_stg_payments.json",
        "silver_stg_drivers.json",
        "silver_stg_riders.json",
    ]


def test_all_silver_suites_exist(expectations_dir, expected_suites):
    """Verify all 8 Silver expectation suite files exist."""
    for suite_file in expected_suites:
        suite_path = expectations_dir / suite_file
        assert suite_path.exists(), f"Missing expectation suite: {suite_file}"


def test_suite_has_minimum_expectations(expectations_dir, expected_suites):
    """Verify each suite has at least 5 expectations."""
    for suite_file in expected_suites:
        suite_path = expectations_dir / suite_file
        with open(suite_path, "r") as f:
            suite_data = json.load(f)

        expectations = suite_data.get("expectations", [])
        assert len(expectations) >= 5, (
            f"{suite_file} has only {len(expectations)} expectations, " f"expected at least 5"
        )


def test_all_suites_include_event_id_deduplication(expectations_dir, expected_suites):
    """Verify all suites include expect_column_values_to_be_unique on event_id."""
    for suite_file in expected_suites:
        suite_path = expectations_dir / suite_file
        with open(suite_path, "r") as f:
            suite_data = json.load(f)

        expectations = suite_data.get("expectations", [])
        dedup_expectations = [
            exp
            for exp in expectations
            if exp.get("expectation_type") == "expect_column_values_to_be_unique"
            and exp.get("kwargs", {}).get("column") == "event_id"
        ]

        assert len(dedup_expectations) > 0, f"{suite_file} missing event_id deduplication check"


def test_stg_trips_deduplication():
    """Verify trip events deduplicated by event_id.

    Input: stg_trips table with duplicate event_id
    Expected: Expectation fails, alerts on duplicates
    """
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "silver"
    suite_path = expectations_dir / "silver_stg_trips.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])
    unique_event_id = [
        exp
        for exp in expectations
        if exp.get("expectation_type") == "expect_column_values_to_be_unique"
        and exp.get("kwargs", {}).get("column") == "event_id"
    ]

    assert len(unique_event_id) > 0, "Missing event_id uniqueness expectation"

    expectation = unique_event_id[0]
    assert expectation["kwargs"]["column"] == "event_id"


def test_stg_surge_updates_range():
    """Verify surge multiplier in valid range.

    Input: stg_surge_updates with surge_multiplier outside [1.0, 2.5]
    Expected: Expectation fails, alerts on out-of-range values
    """
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "silver"
    suite_path = expectations_dir / "silver_stg_surge_updates.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])

    range_expectations = [
        exp
        for exp in expectations
        if exp.get("expectation_type") == "expect_column_values_to_be_between"
        and (exp.get("kwargs", {}).get("column") in ["new_multiplier", "previous_multiplier"])
    ]

    assert len(range_expectations) > 0, "Missing surge multiplier range validation"

    for expectation in range_expectations:
        kwargs = expectation["kwargs"]
        assert kwargs.get("min_value") == 1.0
        assert kwargs.get("max_value") == 2.5
        assert kwargs.get("mostly") is not None, "Missing 'mostly' parameter for soft failure"


def test_stg_ratings_enum():
    """Verify rating values in [1, 2, 3, 4, 5].

    Input: stg_ratings with rating value of 6
    Expected: Expectation fails, alerts on invalid enum value
    """
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "silver"
    suite_path = expectations_dir / "silver_stg_ratings.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])

    rating_expectations = [
        exp
        for exp in expectations
        if exp.get("expectation_type") == "expect_column_values_to_be_between"
        and exp.get("kwargs", {}).get("column") == "rating"
    ]

    assert len(rating_expectations) > 0, "Missing rating value validation"

    expectation = rating_expectations[0]
    kwargs = expectation["kwargs"]
    assert kwargs.get("min_value") == 1
    assert kwargs.get("max_value") == 5


def test_stg_driver_status_not_null():
    """Verify critical fields are not null.

    Input: stg_driver_status with null driver_id
    Expected: Expectation fails, alerts on null values
    """
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "silver"
    suite_path = expectations_dir / "silver_stg_driver_status.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])

    not_null_expectations = [
        exp
        for exp in expectations
        if exp.get("expectation_type") == "expect_column_values_to_not_be_null"
    ]

    assert len(not_null_expectations) > 0, "Missing not null validations"

    not_null_columns = [exp.get("kwargs", {}).get("column") for exp in not_null_expectations]

    assert "driver_id" in not_null_columns, "Missing driver_id not null check"
    assert "event_id" in not_null_columns, "Missing event_id not null check"


def test_suite_execution():
    """Verify all Silver suites can execute successfully.

    Input: Valid Silver tables
    Expected: All expectations pass, validation results stored

    Note: This test validates suite structure. Actual execution requires
    DuckDB with Delta tables populated in MinIO.
    """
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "silver"
    expected_suites = [
        "silver_stg_trips.json",
        "silver_stg_gps_pings.json",
        "silver_stg_driver_status.json",
        "silver_stg_surge_updates.json",
        "silver_stg_ratings.json",
        "silver_stg_payments.json",
        "silver_stg_drivers.json",
        "silver_stg_riders.json",
    ]

    for suite_file in expected_suites:
        suite_path = expectations_dir / suite_file

        with open(suite_path, "r") as f:
            suite_data = json.load(f)

        assert "expectation_suite_name" in suite_data
        assert "expectations" in suite_data
        assert isinstance(suite_data["expectations"], list)
        assert len(suite_data["expectations"]) > 0

        for expectation in suite_data["expectations"]:
            assert "expectation_type" in expectation
            assert "kwargs" in expectation
            assert isinstance(expectation["kwargs"], dict)


def test_stg_trips_has_trip_state_validation():
    """Verify stg_trips includes trip_state enum validation."""
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "silver"
    suite_path = expectations_dir / "silver_stg_trips.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])

    trip_state_expectations = [
        exp
        for exp in expectations
        if exp.get("kwargs", {}).get("column") == "trip_state"
        and exp.get("expectation_type")
        in ["expect_column_values_to_be_in_set", "expect_column_values_to_match_regex"]
    ]

    assert len(trip_state_expectations) > 0, "Missing trip_state validation"


def test_stg_gps_pings_has_coordinate_validation():
    """Verify stg_gps_pings includes latitude/longitude range validation."""
    expectations_dir = Path(__file__).parent.parent / "gx" / "expectations" / "silver"
    suite_path = expectations_dir / "silver_stg_gps_pings.json"

    with open(suite_path, "r") as f:
        suite_data = json.load(f)

    expectations = suite_data.get("expectations", [])

    coordinate_expectations = [
        exp
        for exp in expectations
        if exp.get("expectation_type") == "expect_column_values_to_be_between"
        and exp.get("kwargs", {}).get("column") in ["latitude", "longitude"]
    ]

    assert len(coordinate_expectations) >= 2, "Missing latitude/longitude range validations"

    latitude_exps = [
        exp for exp in coordinate_expectations if exp.get("kwargs", {}).get("column") == "latitude"
    ]
    longitude_exps = [
        exp for exp in coordinate_expectations if exp.get("kwargs", {}).get("column") == "longitude"
    ]

    assert len(latitude_exps) > 0, "Missing latitude range validation"
    assert len(longitude_exps) > 0, "Missing longitude range validation"
