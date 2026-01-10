import pytest

from src.fare import FareBreakdown, FareCalculator


class TestFareCalculator:
    @pytest.fixture
    def calculator(self):
        return FareCalculator()

    def test_fare_basic_calculation(self, calculator):
        breakdown = calculator.calculate(distance_km=5.0, duration_min=10.0, surge_multiplier=1.0)

        assert breakdown.base_fee == pytest.approx(4.00)
        assert breakdown.distance_charge == pytest.approx(7.50)
        assert breakdown.time_charge == pytest.approx(2.50)
        assert breakdown.subtotal == pytest.approx(14.00)
        assert breakdown.surge_multiplier == pytest.approx(1.0)
        assert breakdown.total_fare == pytest.approx(14.00)

    def test_fare_minimum_enforced(self, calculator):
        breakdown = calculator.calculate(distance_km=1.0, duration_min=1.0, surge_multiplier=1.0)

        assert breakdown.subtotal == pytest.approx(5.75)
        assert breakdown.total_fare == pytest.approx(8.00)

    def test_fare_with_surge(self, calculator):
        breakdown = calculator.calculate(distance_km=10.0, duration_min=20.0, surge_multiplier=2.0)

        assert breakdown.subtotal == pytest.approx(24.00)
        assert breakdown.surge_multiplier == pytest.approx(2.0)
        assert breakdown.total_fare == pytest.approx(48.00)

    def test_fare_minimum_with_surge(self, calculator):
        breakdown = calculator.calculate(distance_km=0.5, duration_min=1.0, surge_multiplier=1.5)

        assert breakdown.subtotal == pytest.approx(5.00)
        assert breakdown.total_fare == pytest.approx(12.00)

    def test_fare_breakdown(self, calculator):
        breakdown = calculator.calculate(distance_km=8.0, duration_min=15.0, surge_multiplier=1.0)

        assert isinstance(breakdown, FareBreakdown)
        assert breakdown.base_fee == pytest.approx(4.00)
        assert breakdown.distance_charge == pytest.approx(12.00)
        assert breakdown.time_charge == pytest.approx(3.75)
        assert breakdown.subtotal == pytest.approx(19.75)
        assert breakdown.surge_multiplier == pytest.approx(1.0)
        assert breakdown.total_fare == pytest.approx(19.75)

    def test_fare_zero_distance(self, calculator):
        breakdown = calculator.calculate(distance_km=0.0, duration_min=5.0, surge_multiplier=1.0)

        assert breakdown.subtotal == pytest.approx(5.25)
        assert breakdown.total_fare == pytest.approx(8.00)

    def test_fare_invalid_surge(self, calculator):
        with pytest.raises(ValueError):
            calculator.calculate(distance_km=5.0, duration_min=10.0, surge_multiplier=0.5)

    def test_fare_negative_distance(self, calculator):
        with pytest.raises(ValueError):
            calculator.calculate(distance_km=-5.0, duration_min=10.0, surge_multiplier=1.0)

    def test_fare_negative_duration(self, calculator):
        with pytest.raises(ValueError):
            calculator.calculate(distance_km=5.0, duration_min=-10.0, surge_multiplier=1.0)

    def test_fare_deterministic(self, calculator):
        breakdown1 = calculator.calculate(5.0, 10.0, 1.5)
        breakdown2 = calculator.calculate(5.0, 10.0, 1.5)

        assert breakdown1.total_fare == breakdown2.total_fare
        assert breakdown1.subtotal == breakdown2.subtotal
