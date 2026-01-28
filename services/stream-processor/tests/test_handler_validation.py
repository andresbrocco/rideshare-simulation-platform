"""Tests for handler Pydantic validation.

RED PHASE: These tests define the expected validation behavior for handlers.
They should FAIL until Pydantic validation is added to handlers.
"""

import json
from unittest.mock import MagicMock, patch


# Valid event fixtures based on simulation/src/events/schemas.py


def make_valid_gps_event() -> dict:
    """Create a valid GPS ping event."""
    return {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "entity_type": "driver",
        "entity_id": "driver-123",
        "timestamp": "2024-01-15T10:00:00Z",
        "location": [-46.6333, -23.5505],
        "heading": 90.0,
        "speed": 45.5,
        "accuracy": 5.0,
        "trip_id": "trip-456",
    }


def make_valid_trip_event() -> dict:
    """Create a valid trip event."""
    return {
        "event_id": "550e8400-e29b-41d4-a716-446655440001",
        "event_type": "trip.requested",
        "trip_id": "trip-789",
        "timestamp": "2024-01-15T10:00:00Z",
        "rider_id": "rider-123",
        "driver_id": None,
        "pickup_location": [-46.6333, -23.5505],
        "dropoff_location": [-46.6500, -23.5600],
        "pickup_zone_id": "zone-1",
        "dropoff_zone_id": "zone-2",
        "surge_multiplier": 1.5,
        "fare": 35.50,
    }


def make_valid_driver_status_event() -> dict:
    """Create a valid driver status event."""
    return {
        "event_id": "550e8400-e29b-41d4-a716-446655440002",
        "driver_id": "driver-456",
        "timestamp": "2024-01-15T10:00:00Z",
        "previous_status": "offline",
        "new_status": "online",
        "trigger": "app_open",
        "location": [-46.6333, -23.5505],
    }


def make_valid_surge_event() -> dict:
    """Create a valid surge update event."""
    return {
        "event_id": "550e8400-e29b-41d4-a716-446655440003",
        "zone_id": "zone-central",
        "timestamp": "2024-01-15T10:00:00Z",
        "previous_multiplier": 1.0,
        "new_multiplier": 1.8,
        "available_drivers": 5,
        "pending_requests": 15,
        "calculation_window_seconds": 60,
    }


def make_valid_driver_profile_event() -> dict:
    """Create a valid driver profile event."""
    return {
        "event_id": "550e8400-e29b-41d4-a716-446655440004",
        "event_type": "driver.created",
        "driver_id": "driver-789",
        "timestamp": "2024-01-15T10:00:00Z",
        "first_name": "Carlos",
        "last_name": "Silva",
        "email": "carlos.silva@example.com",
        "phone": "+55-11-99999-8888",
        "home_location": [-46.6400, -23.5550],
        "preferred_zones": ["zone-1", "zone-2"],
        "shift_preference": "morning",
        "vehicle_make": "Toyota",
        "vehicle_model": "Corolla",
        "vehicle_year": 2022,
        "license_plate": "ABC-1234",
    }


def make_valid_rider_profile_event() -> dict:
    """Create a valid rider profile event."""
    return {
        "event_id": "550e8400-e29b-41d4-a716-446655440005",
        "event_type": "rider.created",
        "rider_id": "rider-456",
        "timestamp": "2024-01-15T10:00:00Z",
        "first_name": "Maria",
        "last_name": "Santos",
        "email": "maria.santos@example.com",
        "phone": "+55-11-88888-7777",
        "home_location": [-46.6350, -23.5520],
        "payment_method_type": "credit_card",
        "payment_method_masked": "**** **** **** 1234",
    }


class TestGPSHandlerValidation:
    """Test Pydantic validation in GPS handler."""

    def test_valid_gps_event_passes_validation(self):
        """Valid GPS event should pass validation and be processed."""
        from src.handlers.gps_handler import GPSHandler

        handler = GPSHandler()
        event = make_valid_gps_event()
        message = json.dumps(event).encode()

        # Should not raise, returns empty list (windowed handler)
        result = handler.handle(message)
        assert result == []
        assert handler.messages_received == 1

    def test_invalid_gps_event_missing_entity_type_returns_empty(self):
        """Invalid GPS event (missing required field) should return empty list."""
        from src.handlers.gps_handler import GPSHandler

        handler = GPSHandler()
        event = make_valid_gps_event()
        del event["entity_type"]  # Remove required field
        message = json.dumps(event).encode()

        result = handler.handle(message)
        assert result == []
        # Should not increment messages_received for invalid events
        assert handler.messages_received == 0

    def test_invalid_gps_event_wrong_entity_type_returns_empty(self):
        """GPS event with invalid entity_type literal should return empty list."""
        from src.handlers.gps_handler import GPSHandler

        handler = GPSHandler()
        event = make_valid_gps_event()
        event["entity_type"] = "vehicle"  # Invalid literal value
        message = json.dumps(event).encode()

        result = handler.handle(message)
        assert result == []
        assert handler.messages_received == 0

    def test_invalid_gps_event_wrong_location_type_returns_empty(self):
        """GPS event with wrong location type should return empty list."""
        from src.handlers.gps_handler import GPSHandler

        handler = GPSHandler()
        event = make_valid_gps_event()
        event["location"] = "invalid"  # Should be tuple of floats
        message = json.dumps(event).encode()

        result = handler.handle(message)
        assert result == []
        assert handler.messages_received == 0

    def test_validation_error_metrics_incremented(self):
        """Validation errors should increment metrics."""
        from src.handlers.gps_handler import GPSHandler

        handler = GPSHandler()
        event = {"invalid": "event"}
        message = json.dumps(event).encode()

        with patch("src.handlers.gps_handler.get_metrics_collector") as mock_metrics:
            mock_collector = MagicMock()
            mock_metrics.return_value = mock_collector

            handler.handle(message)

            mock_collector.record_validation_error.assert_called_once_with("gps")


class TestTripHandlerValidation:
    """Test Pydantic validation in Trip handler."""

    def test_valid_trip_event_passes_validation(self):
        """Valid trip event should pass validation and be emitted."""
        from src.handlers.trip_handler import TripHandler

        handler = TripHandler()
        event = make_valid_trip_event()
        message = json.dumps(event).encode()

        result = handler.handle(message)
        assert len(result) == 1
        assert result[0][0] == "trip-updates"
        assert handler.messages_processed == 1

    def test_invalid_trip_event_missing_trip_id_returns_empty(self):
        """Invalid trip event (missing trip_id) should return empty list."""
        from src.handlers.trip_handler import TripHandler

        handler = TripHandler()
        event = make_valid_trip_event()
        del event["trip_id"]
        message = json.dumps(event).encode()

        result = handler.handle(message)
        assert result == []
        assert handler.messages_processed == 0

    def test_invalid_trip_event_wrong_event_type_returns_empty(self):
        """Trip event with invalid event_type literal should return empty list."""
        from src.handlers.trip_handler import TripHandler

        handler = TripHandler()
        event = make_valid_trip_event()
        event["event_type"] = "trip.invalid"  # Invalid literal
        message = json.dumps(event).encode()

        result = handler.handle(message)
        assert result == []
        assert handler.messages_processed == 0

    def test_trip_validation_error_metrics_incremented(self):
        """Trip validation errors should increment metrics."""
        from src.handlers.trip_handler import TripHandler

        handler = TripHandler()
        event = {"invalid": "event"}
        message = json.dumps(event).encode()

        with patch("src.handlers.trip_handler.get_metrics_collector") as mock_metrics:
            mock_collector = MagicMock()
            mock_metrics.return_value = mock_collector

            handler.handle(message)

            mock_collector.record_validation_error.assert_called_once_with("trip")


class TestDriverStatusHandlerValidation:
    """Test Pydantic validation in DriverStatus handler."""

    def test_valid_driver_status_event_passes_validation(self):
        """Valid driver status event should pass validation."""
        from src.handlers.driver_status_handler import DriverStatusHandler

        handler = DriverStatusHandler()
        event = make_valid_driver_status_event()
        message = json.dumps(event).encode()

        result = handler.handle(message)
        assert len(result) == 1
        assert result[0][0] == "driver-updates"

    def test_invalid_driver_status_wrong_new_status_returns_empty(self):
        """Driver status with invalid new_status should return empty list."""
        from src.handlers.driver_status_handler import DriverStatusHandler

        handler = DriverStatusHandler()
        event = make_valid_driver_status_event()
        event["new_status"] = "invalid_status"  # Invalid literal
        message = json.dumps(event).encode()

        result = handler.handle(message)
        assert result == []
        assert handler.messages_processed == 0

    def test_driver_status_validation_error_metrics(self):
        """Driver status validation errors should increment metrics."""
        from src.handlers.driver_status_handler import DriverStatusHandler

        handler = DriverStatusHandler()
        event = {"missing": "fields"}
        message = json.dumps(event).encode()

        with patch("src.handlers.driver_status_handler.get_metrics_collector") as mock_metrics:
            mock_collector = MagicMock()
            mock_metrics.return_value = mock_collector

            handler.handle(message)

            mock_collector.record_validation_error.assert_called_once_with("driver_status")


class TestSurgeHandlerValidation:
    """Test Pydantic validation in Surge handler."""

    def test_valid_surge_event_passes_validation(self):
        """Valid surge event should pass validation."""
        from src.handlers.surge_handler import SurgeHandler

        handler = SurgeHandler()
        event = make_valid_surge_event()
        message = json.dumps(event).encode()

        result = handler.handle(message)
        assert len(result) == 1
        assert result[0][0] == "surge_updates"

    def test_invalid_surge_missing_zone_id_returns_empty(self):
        """Surge event missing zone_id should return empty list."""
        from src.handlers.surge_handler import SurgeHandler

        handler = SurgeHandler()
        event = make_valid_surge_event()
        del event["zone_id"]
        message = json.dumps(event).encode()

        result = handler.handle(message)
        assert result == []
        assert handler.messages_processed == 0

    def test_invalid_surge_negative_multiplier_returns_empty(self):
        """Surge event with negative multiplier should return empty list."""
        from src.handlers.surge_handler import SurgeHandler

        handler = SurgeHandler()
        event = make_valid_surge_event()
        event["new_multiplier"] = -1.0  # Invalid: should be >= 1.0
        message = json.dumps(event).encode()

        result = handler.handle(message)
        assert result == []
        assert handler.messages_processed == 0

    def test_surge_validation_error_metrics(self):
        """Surge validation errors should increment metrics."""
        from src.handlers.surge_handler import SurgeHandler

        handler = SurgeHandler()
        event = {"incomplete": "data"}
        message = json.dumps(event).encode()

        with patch("src.handlers.surge_handler.get_metrics_collector") as mock_metrics:
            mock_collector = MagicMock()
            mock_metrics.return_value = mock_collector

            handler.handle(message)

            mock_collector.record_validation_error.assert_called_once_with("surge")


class TestDriverProfileHandlerValidation:
    """Test Pydantic validation in DriverProfile handler."""

    def test_valid_driver_profile_event_passes_validation(self):
        """Valid driver profile event should pass validation."""
        from src.handlers.driver_profile_handler import DriverProfileHandler

        handler = DriverProfileHandler()
        event = make_valid_driver_profile_event()
        message = json.dumps(event).encode()

        result = handler.handle(message)
        assert len(result) == 1
        assert result[0][0] == "driver-updates"

    def test_invalid_driver_profile_wrong_event_type_returns_empty(self):
        """Driver profile with invalid event_type should return empty list."""
        from src.handlers.driver_profile_handler import DriverProfileHandler

        handler = DriverProfileHandler()
        event = make_valid_driver_profile_event()
        event["event_type"] = "driver.invalid"  # Invalid literal
        message = json.dumps(event).encode()

        result = handler.handle(message)
        assert result == []
        assert handler.messages_processed == 0

    def test_invalid_driver_profile_wrong_shift_preference_returns_empty(self):
        """Driver profile with invalid shift_preference should return empty list."""
        from src.handlers.driver_profile_handler import DriverProfileHandler

        handler = DriverProfileHandler()
        event = make_valid_driver_profile_event()
        event["shift_preference"] = "always"  # Invalid literal
        message = json.dumps(event).encode()

        result = handler.handle(message)
        assert result == []
        assert handler.messages_processed == 0

    def test_driver_profile_validation_error_metrics(self):
        """Driver profile validation errors should increment metrics."""
        from src.handlers.driver_profile_handler import DriverProfileHandler

        handler = DriverProfileHandler()
        event = {"only": "partial"}
        message = json.dumps(event).encode()

        with patch("src.handlers.driver_profile_handler.get_metrics_collector") as mock_metrics:
            mock_collector = MagicMock()
            mock_metrics.return_value = mock_collector

            handler.handle(message)

            mock_collector.record_validation_error.assert_called_once_with("driver_profile")


class TestRiderProfileHandlerValidation:
    """Test Pydantic validation in RiderProfile handler."""

    def test_valid_rider_profile_event_passes_validation(self):
        """Valid rider profile event should pass validation."""
        from src.handlers.rider_profile_handler import RiderProfileHandler

        handler = RiderProfileHandler()
        event = make_valid_rider_profile_event()
        message = json.dumps(event).encode()

        result = handler.handle(message)
        assert len(result) == 1
        assert result[0][0] == "rider-updates"

    def test_invalid_rider_profile_wrong_event_type_returns_empty(self):
        """Rider profile with invalid event_type should return empty list."""
        from src.handlers.rider_profile_handler import RiderProfileHandler

        handler = RiderProfileHandler()
        event = make_valid_rider_profile_event()
        event["event_type"] = "rider.invalid"  # Invalid literal
        message = json.dumps(event).encode()

        result = handler.handle(message)
        assert result == []
        assert handler.messages_processed == 0

    def test_invalid_rider_profile_wrong_payment_method_returns_empty(self):
        """Rider profile with invalid payment_method_type should return empty list."""
        from src.handlers.rider_profile_handler import RiderProfileHandler

        handler = RiderProfileHandler()
        event = make_valid_rider_profile_event()
        event["payment_method_type"] = (
            "cash"  # Invalid literal (only credit_card or digital_wallet)
        )
        message = json.dumps(event).encode()

        result = handler.handle(message)
        assert result == []
        assert handler.messages_processed == 0

    def test_rider_profile_validation_error_metrics(self):
        """Rider profile validation errors should increment metrics."""
        from src.handlers.rider_profile_handler import RiderProfileHandler

        handler = RiderProfileHandler()
        event = {"incomplete": "profile"}
        message = json.dumps(event).encode()

        with patch("src.handlers.rider_profile_handler.get_metrics_collector") as mock_metrics:
            mock_collector = MagicMock()
            mock_metrics.return_value = mock_collector

            handler.handle(message)

            mock_collector.record_validation_error.assert_called_once_with("rider_profile")
