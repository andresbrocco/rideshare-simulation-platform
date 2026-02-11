import pytest

from src.geo.traffic import TrafficModel


@pytest.fixture
def traffic_model():
    return TrafficModel()


@pytest.mark.unit
class TestMorningRushHour:
    def test_morning_rush_peak(self, traffic_model):
        """Peak morning rush hour at 8:00 AM should have ~1.40 multiplier."""
        multiplier = traffic_model.get_multiplier(hour=8)
        assert 1.35 <= multiplier <= 1.45

    def test_rush_hour_boundary_morning_start(self, traffic_model):
        """Morning rush start at 7:00 AM should be between baseline and peak."""
        multiplier = traffic_model.get_multiplier(hour=7)
        assert 1.0 < multiplier < 1.40


@pytest.mark.unit
class TestEveningRushHour:
    def test_evening_rush_peak(self, traffic_model):
        """Peak evening rush hour at 6:00 PM should have ~1.40 multiplier."""
        multiplier = traffic_model.get_multiplier(hour=18)
        assert 1.35 <= multiplier <= 1.45

    def test_rush_hour_boundary_evening_start(self, traffic_model):
        """Evening rush start at 5:00 PM should be between baseline and peak."""
        multiplier = traffic_model.get_multiplier(hour=17)
        assert 1.0 < multiplier < 1.40


@pytest.mark.unit
class TestNightHours:
    def test_night_hours_peak(self, traffic_model):
        """Peak night hours at 2:00 AM should have ~0.85 multiplier."""
        multiplier = traffic_model.get_multiplier(hour=2)
        assert 0.80 <= multiplier <= 0.90

    def test_night_to_morning_transition(self, traffic_model):
        """Transition at 5:00 AM should be smooth from night to morning."""
        multiplier = traffic_model.get_multiplier(hour=5)
        # Should be transitioning from night (0.85) toward baseline (1.0)
        assert 0.85 <= multiplier <= 1.05


@pytest.mark.unit
class TestBaselineHours:
    def test_midday_baseline(self, traffic_model):
        """Midday at 1:00 PM should have ~1.0 baseline multiplier."""
        multiplier = traffic_model.get_multiplier(hour=13)
        assert 0.95 <= multiplier <= 1.05

    def test_late_morning_baseline(self, traffic_model):
        """Late morning at 11:00 AM should be near baseline."""
        multiplier = traffic_model.get_multiplier(hour=11)
        assert 0.95 <= multiplier <= 1.10


@pytest.mark.unit
class TestSigmoidSmoothing:
    def test_sigmoid_smoothing_transition(self, traffic_model):
        """7:30 AM should show smooth transition into rush hour."""
        multiplier = traffic_model.get_multiplier(hour=7.5)
        # Should be between baseline and peak
        assert 1.0 < multiplier < 1.40

    def test_time_float_support(self, traffic_model):
        """Should support fractional hours like 7.25 (7:15 AM)."""
        multiplier = traffic_model.get_multiplier(hour=7.25)
        # Valid multiplier somewhere between baseline and rush
        assert 0.85 <= multiplier <= 1.45


@pytest.mark.unit
class TestMultiplierBounds:
    def test_multiplier_never_below_minimum(self, traffic_model):
        """Multiplier should never go below 0.85."""
        for hour in range(24):
            multiplier = traffic_model.get_multiplier(hour=hour)
            assert multiplier >= 0.85, f"Hour {hour} has multiplier {multiplier} < 0.85"

    def test_multiplier_never_above_maximum(self, traffic_model):
        """Multiplier should never exceed 1.40."""
        for hour in range(24):
            multiplier = traffic_model.get_multiplier(hour=hour)
            assert multiplier <= 1.40, f"Hour {hour} has multiplier {multiplier} > 1.40"


@pytest.mark.unit
class TestApplyToRoute:
    def test_apply_multiplier_to_duration(self, traffic_model):
        """Applying 1.4x multiplier to 600s duration should give 840s."""
        result = traffic_model.apply_to_duration(duration_seconds=600, hour=8)
        # At 8 AM (rush hour), multiplier is ~1.4, so 600 * 1.4 = 840
        assert 810 <= result <= 870

    def test_apply_night_multiplier(self, traffic_model):
        """Night multiplier should reduce duration."""
        result = traffic_model.apply_to_duration(duration_seconds=600, hour=2)
        # At 2 AM (night), multiplier is ~0.85, so 600 * 0.85 = 510
        assert 480 <= result <= 540

    def test_apply_baseline_multiplier(self, traffic_model):
        """Baseline multiplier should keep duration roughly the same."""
        result = traffic_model.apply_to_duration(duration_seconds=600, hour=13)
        # At 1 PM (baseline), multiplier is ~1.0
        assert 570 <= result <= 630
