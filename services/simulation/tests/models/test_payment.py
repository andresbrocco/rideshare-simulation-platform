from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.payment import Payment


@pytest.mark.unit
class TestPayment:
    def test_payment_valid(self):
        payment = Payment(
            payment_id=uuid4(),
            trip_id=uuid4(),
            rider_id="rider_123",
            driver_id="driver_456",
            payment_method_type="credit_card",
            payment_method_masked="****1234",
            fare_amount=40.0,
            timestamp="2025-01-15T10:30:00Z",
        )
        assert payment.fare_amount == 40.0

    def test_payment_fee_calculation(self):
        payment = Payment(
            payment_id=uuid4(),
            trip_id=uuid4(),
            rider_id="rider_123",
            driver_id="driver_456",
            payment_method_type="credit_card",
            payment_method_masked="****1234",
            fare_amount=100.0,
            timestamp="2025-01-15T10:30:00Z",
        )
        assert payment.platform_fee_amount == pytest.approx(25.0)
        assert payment.driver_payout_amount == pytest.approx(75.0)

    def test_payment_auto_calculate_breakdown(self):
        payment = Payment(
            payment_id=uuid4(),
            trip_id=uuid4(),
            rider_id="rider_123",
            driver_id="driver_456",
            payment_method_type="digital_wallet",
            payment_method_masked="PayPal",
            fare_amount=50.0,
            timestamp="2025-01-15T10:30:00Z",
        )
        assert payment.platform_fee_amount == pytest.approx(12.50)
        assert payment.driver_payout_amount == pytest.approx(37.50)

    def test_payment_method_type_validation(self):
        payment = Payment(
            payment_id=uuid4(),
            trip_id=uuid4(),
            rider_id="rider_123",
            driver_id="driver_456",
            payment_method_type="credit_card",
            payment_method_masked="****1234",
            fare_amount=30.0,
            timestamp="2025-01-15T10:30:00Z",
        )
        assert payment.payment_method_type == "credit_card"

    def test_payment_negative_fare(self):
        with pytest.raises(ValidationError):
            Payment(
                payment_id=uuid4(),
                trip_id=uuid4(),
                rider_id="rider_123",
                driver_id="driver_456",
                payment_method_type="credit_card",
                payment_method_masked="****1234",
                fare_amount=-10.0,
                timestamp="2025-01-15T10:30:00Z",
            )
