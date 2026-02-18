from math import sqrt

import pytest

from src.geo.gps_simulation import GPSSimulator, precompute_headings


@pytest.fixture
def gps_simulator():
    return GPSSimulator(noise_meters=10.0, dropout_probability=0.05)


@pytest.fixture
def no_noise_simulator():
    return GPSSimulator(noise_meters=0.0, dropout_probability=0.0)


@pytest.mark.unit
@pytest.mark.slow
def test_gaussian_noise_applied(gps_simulator):
    coords = (-23.55, -46.63)
    noisy_lat, noisy_lon = gps_simulator.add_noise(*coords)

    assert noisy_lat != coords[0] or noisy_lon != coords[1]

    lat_diff_meters = abs(noisy_lat - coords[0]) * 111000
    lon_diff_meters = abs(noisy_lon - coords[1]) * 111000
    offset_meters = sqrt(lat_diff_meters**2 + lon_diff_meters**2)

    assert offset_meters < 100


@pytest.mark.unit
@pytest.mark.slow
def test_noise_distribution():
    simulator = GPSSimulator(noise_meters=10.0, dropout_probability=0.0)
    coords = (-23.55, -46.63)
    samples = 1000

    offsets = []
    for _ in range(samples):
        noisy_lat, noisy_lon = simulator.add_noise(*coords)
        lat_diff_meters = abs(noisy_lat - coords[0]) * 111000
        lon_diff_meters = abs(noisy_lon - coords[1]) * 111000
        offset = sqrt(lat_diff_meters**2 + lon_diff_meters**2)
        offsets.append(offset)

    mean_offset = sum(offsets) / len(offsets)

    assert 5 < mean_offset < 15


@pytest.mark.unit
@pytest.mark.slow
def test_no_noise_when_disabled(no_noise_simulator):
    coords = (-23.55, -46.63)
    noisy_lat, noisy_lon = no_noise_simulator.add_noise(*coords)

    assert noisy_lat == coords[0]
    assert noisy_lon == coords[1]


@pytest.mark.unit
@pytest.mark.slow
def test_gps_dropout_probability():
    simulator = GPSSimulator(noise_meters=10.0, dropout_probability=0.1)
    trials = 1000

    dropouts = sum(1 for _ in range(trials) if simulator.should_dropout())

    assert 50 < dropouts < 150


@pytest.mark.unit
@pytest.mark.slow
def test_no_dropout_when_disabled(no_noise_simulator):
    trials = 100

    dropouts = sum(1 for _ in range(trials) if no_noise_simulator.should_dropout())

    assert dropouts == 0


@pytest.mark.unit
@pytest.mark.slow
def test_polyline_interpolation_start(gps_simulator):
    polyline = [
        (-23.55, -46.63),
        (-23.56, -46.64),
        (-23.57, -46.65),
    ]

    lat, lon = gps_simulator.interpolate_position(polyline, progress=0.0)

    assert lat == polyline[0][0]
    assert lon == polyline[0][1]


@pytest.mark.unit
@pytest.mark.slow
def test_polyline_interpolation_end(gps_simulator):
    polyline = [
        (-23.55, -46.63),
        (-23.56, -46.64),
        (-23.57, -46.65),
    ]

    lat, lon = gps_simulator.interpolate_position(polyline, progress=1.0)

    assert lat == polyline[-1][0]
    assert lon == polyline[-1][1]


@pytest.mark.unit
@pytest.mark.slow
def test_polyline_interpolation_midpoint(gps_simulator):
    polyline = [
        (-23.55, -46.63),
        (-23.57, -46.65),
    ]

    lat, lon = gps_simulator.interpolate_position(polyline, progress=0.5)

    assert -23.57 < lat < -23.55
    assert -46.65 < lon < -46.63


@pytest.mark.unit
@pytest.mark.slow
def test_heading_calculation(gps_simulator):
    from_coords = (-23.55, -46.63)
    to_coords = (-23.54, -46.63)

    heading = gps_simulator.calculate_heading(from_coords, to_coords)

    assert 0 <= heading < 360
    assert heading > 350 or heading < 10


@pytest.mark.unit
@pytest.mark.slow
def test_heading_calculation_east(gps_simulator):
    from_coords = (-23.55, -46.63)
    to_coords = (-23.55, -46.62)

    heading = gps_simulator.calculate_heading(from_coords, to_coords)

    assert 80 < heading < 100


@pytest.mark.unit
@pytest.mark.slow
def test_speed_calculation(gps_simulator):
    distance_meters = 100
    time_seconds = 10

    speed = gps_simulator.calculate_speed(distance_meters, time_seconds)

    assert speed == 10.0


@pytest.mark.unit
@pytest.mark.slow
def test_speed_calculation_zero_time(gps_simulator):
    distance_meters = 100
    time_seconds = 0

    speed = gps_simulator.calculate_speed(distance_meters, time_seconds)

    assert speed == 0.0


@pytest.mark.unit
@pytest.mark.slow
def test_gps_accuracy_field(gps_simulator):
    accuracy = gps_simulator.get_gps_accuracy()

    assert 8 < accuracy < 12


@pytest.mark.unit
def test_calculate_heading_as_staticmethod():
    """calculate_heading() can be called as a static method without instantiation."""
    heading = GPSSimulator.calculate_heading((-23.55, -46.63), (-23.54, -46.63))
    assert 0 <= heading < 360
    # Northward heading
    assert heading > 350 or heading < 10


@pytest.mark.unit
def test_calculate_heading_staticmethod_matches_instance(gps_simulator):
    """Static call and instance call produce identical results."""
    from_coords = (-23.55, -46.63)
    to_coords = (-23.56, -46.64)
    static_result = GPSSimulator.calculate_heading(from_coords, to_coords)
    instance_result = gps_simulator.calculate_heading(from_coords, to_coords)
    assert static_result == instance_result


@pytest.mark.unit
def test_precompute_headings_length():
    """precompute_headings() returns len(geometry) - 1 headings."""
    geometry = [(-23.55, -46.63), (-23.56, -46.64), (-23.57, -46.65)]
    headings = precompute_headings(geometry)
    assert len(headings) == 2


@pytest.mark.unit
def test_precompute_headings_values_in_range():
    """All precomputed headings are in [0, 360)."""
    geometry = [(-23.55, -46.63), (-23.56, -46.64), (-23.57, -46.65), (-23.58, -46.66)]
    headings = precompute_headings(geometry)
    assert all(0 <= h < 360 for h in headings)


@pytest.mark.unit
def test_precompute_headings_single_point():
    """Single-point geometry returns empty list."""
    assert precompute_headings([(-23.55, -46.63)]) == []


@pytest.mark.unit
def test_precompute_headings_empty_geometry():
    """Empty geometry returns empty list."""
    assert precompute_headings([]) == []


@pytest.mark.unit
def test_precompute_headings_two_points_northward():
    """Two-point northward geometry returns one heading near 0/360."""
    headings = precompute_headings([(-23.55, -46.63), (-23.54, -46.63)])
    assert len(headings) == 1
    assert headings[0] > 350 or headings[0] < 10


@pytest.mark.unit
def test_precompute_headings_cardinal_directions():
    """Verify headings for cardinal directions."""
    center = (-23.55, -46.63)
    # East
    east_headings = precompute_headings([center, (-23.55, -46.62)])
    assert 80 < east_headings[0] < 100

    # South
    south_headings = precompute_headings([center, (-23.56, -46.63)])
    assert 170 < south_headings[0] < 190

    # West
    west_headings = precompute_headings([center, (-23.55, -46.64)])
    assert 260 < west_headings[0] < 280
