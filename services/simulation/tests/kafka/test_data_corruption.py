"""Tests for malformed data injection."""

import json
from unittest.mock import patch

import pytest

from kafka.data_corruption import CorruptionType, DataCorruptor, get_corruptor


@pytest.mark.unit
class TestDataCorruptorInit:
    def test_default_rate_is_zero(self):
        corruptor = DataCorruptor()
        assert corruptor.corruption_rate == 0.0

    def test_custom_rate(self):
        corruptor = DataCorruptor(corruption_rate=0.15)
        assert corruptor.corruption_rate == 0.15

    def test_rate_clamped_to_min(self):
        corruptor = DataCorruptor(corruption_rate=-0.5)
        assert corruptor.corruption_rate == 0.0

    def test_rate_clamped_to_max(self):
        corruptor = DataCorruptor(corruption_rate=1.5)
        assert corruptor.corruption_rate == 1.0

    def test_from_environment_reads_rate(self, monkeypatch):
        monkeypatch.setenv("MALFORMED_EVENT_RATE", "0.05")
        corruptor = DataCorruptor.from_environment()
        assert corruptor.corruption_rate == 0.05

    def test_from_environment_defaults_to_zero(self, monkeypatch):
        monkeypatch.delenv("MALFORMED_EVENT_RATE", raising=False)
        corruptor = DataCorruptor.from_environment()
        assert corruptor.corruption_rate == 0.0


@pytest.mark.unit
class TestShouldCorrupt:
    def test_never_corrupts_at_zero(self):
        corruptor = DataCorruptor(corruption_rate=0.0)
        results = [corruptor.should_corrupt() for _ in range(100)]
        assert not any(results)

    def test_always_corrupts_at_one(self):
        corruptor = DataCorruptor(corruption_rate=1.0)
        results = [corruptor.should_corrupt() for _ in range(100)]
        assert all(results)

    def test_zero_rate_skips_rng(self):
        """When corruption_rate is 0.0, random.random() should never be called."""
        corruptor = DataCorruptor(corruption_rate=0.0)
        with patch("kafka.data_corruption.random.random") as mock_random:
            for _ in range(50):
                result = corruptor.should_corrupt()
                assert result is False
            mock_random.assert_not_called()

    def test_nonzero_rate_calls_rng(self):
        """When corruption_rate > 0, random.random() should be invoked."""
        corruptor = DataCorruptor(corruption_rate=0.05)
        with patch("kafka.data_corruption.random.random", return_value=0.99) as mock_random:
            corruptor.should_corrupt()
            mock_random.assert_called_once()


@pytest.mark.unit
class TestCorruptionTypes:
    @pytest.fixture
    def sample_event(self):
        return {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "event_type": "trip.requested",
            "trip_id": "660e8400-e29b-41d4-a716-446655440001",
            "rider_id": "770e8400-e29b-41d4-a716-446655440002",
            "timestamp": "2025-07-30T10:00:00Z",
            "pickup_location": [-23.5505, -46.6333],
            "dropoff_location": [-23.5605, -46.6433],
            "fare": 25.50,
            "surge_multiplier": 1.5,
        }

    def test_corrupt_returns_corruption_type(self, sample_event):
        corruptor = DataCorruptor(corruption_rate=1.0)
        _, corruption_type = corruptor.corrupt(sample_event, "trips")
        assert isinstance(corruption_type, CorruptionType)

    def test_empty_payload_returns_empty_string(self, sample_event):
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._corruption_types = [CorruptionType.EMPTY_PAYLOAD]
        corruptor._corruption_weights = [100]
        corrupted, ctype = corruptor.corrupt(sample_event, "trips")
        assert corrupted == ""
        assert ctype == CorruptionType.EMPTY_PAYLOAD

    def test_malformed_json_is_unparseable(self, sample_event):
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._corruption_types = [CorruptionType.MALFORMED_JSON]
        corruptor._corruption_weights = [100]
        corrupted, _ = corruptor.corrupt(sample_event, "trips")
        with pytest.raises(json.JSONDecodeError):
            json.loads(corrupted)

    def test_truncated_message_is_unparseable(self, sample_event):
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._corruption_types = [CorruptionType.TRUNCATED_MESSAGE]
        corruptor._corruption_weights = [100]
        corrupted, _ = corruptor.corrupt(sample_event, "trips")
        with pytest.raises(json.JSONDecodeError):
            json.loads(corrupted)

    def test_missing_field_removes_required(self, sample_event):
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._corruption_types = [CorruptionType.MISSING_REQUIRED_FIELD]
        corruptor._corruption_weights = [100]
        corrupted, _ = corruptor.corrupt(sample_event, "trips")
        parsed = json.loads(corrupted)
        required = {"event_id", "event_type", "trip_id", "rider_id", "timestamp"}
        present = set(parsed.keys()) & required
        assert len(present) < len(required)

    def test_wrong_type_changes_field_type(self, sample_event):
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._corruption_types = [CorruptionType.WRONG_DATA_TYPE]
        corruptor._corruption_weights = [100]
        corrupted, _ = corruptor.corrupt(sample_event, "trips")
        parsed = json.loads(corrupted)
        # One of these should have wrong type
        type_checks = [
            isinstance(parsed.get("timestamp"), int),
            isinstance(parsed.get("fare"), str),
            isinstance(parsed.get("surge_multiplier"), list),
        ]
        assert any(type_checks)

    def test_invalid_enum_sets_bad_value(self, sample_event):
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._corruption_types = [CorruptionType.INVALID_ENUM_VALUE]
        corruptor._corruption_weights = [100]
        corrupted, _ = corruptor.corrupt(sample_event, "trips")
        parsed = json.loads(corrupted)
        assert parsed["event_type"] == "trip.invalid_state"

    def test_invalid_uuid_sets_bad_format(self, sample_event):
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._corruption_types = [CorruptionType.INVALID_UUID]
        corruptor._corruption_weights = [100]
        corrupted, _ = corruptor.corrupt(sample_event, "trips")
        parsed = json.loads(corrupted)
        uuid_fields = ["event_id", "trip_id", "rider_id"]
        bad_uuids = [parsed[f] == "not-a-valid-uuid" for f in uuid_fields if f in parsed]
        assert any(bad_uuids)

    def test_invalid_timestamp_sets_bad_format(self, sample_event):
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._corruption_types = [CorruptionType.INVALID_TIMESTAMP]
        corruptor._corruption_weights = [100]
        corrupted, _ = corruptor.corrupt(sample_event, "trips")
        parsed = json.loads(corrupted)
        valid_timestamp = "2025-07-30T10:00:00Z"
        assert parsed["timestamp"] != valid_timestamp

    def test_out_of_range_sets_negative_fare(self, sample_event):
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._corruption_types = [CorruptionType.OUT_OF_RANGE_VALUE]
        corruptor._corruption_weights = [100]
        corrupted, _ = corruptor.corrupt(sample_event, "trips")
        parsed = json.loads(corrupted)
        assert parsed["fare"] < 0


@pytest.mark.unit
class TestTopicAwareCorruption:
    def test_gps_ping_corruption(self):
        event = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "entity_type": "driver",
            "entity_id": "660e8400-e29b-41d4-a716-446655440001",
            "timestamp": "2025-07-30T10:00:00Z",
            "location": [-23.5505, -46.6333],
            "heading": 180,
            "accuracy": 10.0,
        }
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._corruption_types = [CorruptionType.INVALID_ENUM_VALUE]
        corruptor._corruption_weights = [100]
        corrupted, _ = corruptor.corrupt(event, "gps_pings")
        parsed = json.loads(corrupted)
        assert parsed["entity_type"] == "vehicle"

    def test_rating_out_of_range(self):
        event = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "trip_id": "660e8400-e29b-41d4-a716-446655440001",
            "timestamp": "2025-07-30T10:00:00Z",
            "rating": 5,
            "rater_type": "rider",
        }
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._corruption_types = [CorruptionType.OUT_OF_RANGE_VALUE]
        corruptor._corruption_weights = [100]
        corrupted, _ = corruptor.corrupt(event, "ratings")
        parsed = json.loads(corrupted)
        assert parsed["rating"] == 10


@pytest.mark.unit
class TestFactoryFunction:
    def test_get_corruptor_returns_instance(self, monkeypatch):
        monkeypatch.setenv("MALFORMED_EVENT_RATE", "0.03")
        corruptor = get_corruptor()
        assert isinstance(corruptor, DataCorruptor)
        assert corruptor.corruption_rate == 0.03
