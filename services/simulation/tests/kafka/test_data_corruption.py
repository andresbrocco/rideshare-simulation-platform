"""Tests for malformed data injection."""

import json

import pytest

from kafka.data_corruption import CorruptionType, DataCorruptor, get_corruptor


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


class TestShouldCorrupt:
    def test_never_corrupts_at_zero(self):
        corruptor = DataCorruptor(corruption_rate=0.0)
        results = [corruptor.should_corrupt() for _ in range(100)]
        assert not any(results)

    def test_always_corrupts_at_one(self):
        corruptor = DataCorruptor(corruption_rate=1.0)
        results = [corruptor.should_corrupt() for _ in range(100)]
        assert all(results)


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
        corruptor._weights = {CorruptionType.EMPTY_PAYLOAD: 100}
        corrupted, ctype = corruptor.corrupt(sample_event, "trips")
        assert corrupted == ""
        assert ctype == CorruptionType.EMPTY_PAYLOAD

    def test_malformed_json_is_unparseable(self, sample_event):
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._weights = {CorruptionType.MALFORMED_JSON: 100}
        corrupted, _ = corruptor.corrupt(sample_event, "trips")
        with pytest.raises(json.JSONDecodeError):
            json.loads(corrupted)

    def test_truncated_message_is_unparseable(self, sample_event):
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._weights = {CorruptionType.TRUNCATED_MESSAGE: 100}
        corrupted, _ = corruptor.corrupt(sample_event, "trips")
        with pytest.raises(json.JSONDecodeError):
            json.loads(corrupted)

    def test_missing_field_removes_required(self, sample_event):
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._weights = {CorruptionType.MISSING_REQUIRED_FIELD: 100}
        corrupted, _ = corruptor.corrupt(sample_event, "trips")
        parsed = json.loads(corrupted)
        required = {"event_id", "event_type", "trip_id", "rider_id", "timestamp"}
        present = set(parsed.keys()) & required
        assert len(present) < len(required)

    def test_wrong_type_changes_field_type(self, sample_event):
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._weights = {CorruptionType.WRONG_DATA_TYPE: 100}
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
        corruptor._weights = {CorruptionType.INVALID_ENUM_VALUE: 100}
        corrupted, _ = corruptor.corrupt(sample_event, "trips")
        parsed = json.loads(corrupted)
        assert parsed["event_type"] == "trip.invalid_state"

    def test_invalid_uuid_sets_bad_format(self, sample_event):
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._weights = {CorruptionType.INVALID_UUID: 100}
        corrupted, _ = corruptor.corrupt(sample_event, "trips")
        parsed = json.loads(corrupted)
        uuid_fields = ["event_id", "trip_id", "rider_id"]
        bad_uuids = [parsed[f] == "not-a-valid-uuid" for f in uuid_fields if f in parsed]
        assert any(bad_uuids)

    def test_invalid_timestamp_sets_bad_format(self, sample_event):
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._weights = {CorruptionType.INVALID_TIMESTAMP: 100}
        corrupted, _ = corruptor.corrupt(sample_event, "trips")
        parsed = json.loads(corrupted)
        valid_timestamp = "2025-07-30T10:00:00Z"
        assert parsed["timestamp"] != valid_timestamp

    def test_out_of_range_sets_negative_fare(self, sample_event):
        corruptor = DataCorruptor(corruption_rate=1.0)
        corruptor._weights = {CorruptionType.OUT_OF_RANGE_VALUE: 100}
        corrupted, _ = corruptor.corrupt(sample_event, "trips")
        parsed = json.loads(corrupted)
        assert parsed["fare"] < 0


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
        corruptor._weights = {CorruptionType.INVALID_ENUM_VALUE: 100}
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
        corruptor._weights = {CorruptionType.OUT_OF_RANGE_VALUE: 100}
        corrupted, _ = corruptor.corrupt(event, "ratings")
        parsed = json.loads(corrupted)
        assert parsed["rating"] == 10


class TestFactoryFunction:
    def test_get_corruptor_returns_instance(self, monkeypatch):
        monkeypatch.setenv("MALFORMED_EVENT_RATE", "0.03")
        corruptor = get_corruptor()
        assert isinstance(corruptor, DataCorruptor)
        assert corruptor.corruption_rate == 0.03
