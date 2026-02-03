"""Tests for DeltaWriteConfig."""

from spark_streaming.config.delta_write_config import DeltaWriteConfig


class TestDeltaWriteConfigDefaults:
    """Tests for DeltaWriteConfig default values."""

    def test_default_optimize_write_enabled(self):
        """Verify optimize_write is enabled by default."""
        config = DeltaWriteConfig()
        assert config.optimize_write is True

    def test_default_auto_compact_enabled(self):
        """Verify auto_compact is enabled by default."""
        config = DeltaWriteConfig()
        assert config.auto_compact is True

    def test_default_target_file_size(self):
        """Verify default target file size is 128 MB."""
        config = DeltaWriteConfig()
        assert config.target_file_size_mb == 128

    def test_default_coalesce_partitions(self):
        """Verify default coalesce partitions is 1."""
        config = DeltaWriteConfig()
        assert config.default_coalesce_partitions == 1

    def test_default_topic_overrides_empty(self):
        """Verify topic overrides are empty by default."""
        config = DeltaWriteConfig()
        assert config.topic_coalesce_overrides == {}


class TestDeltaWriteConfigCustomValues:
    """Tests for DeltaWriteConfig with custom values."""

    def test_can_disable_optimize_write(self):
        """Verify optimize_write can be disabled."""
        config = DeltaWriteConfig(optimize_write=False)
        assert config.optimize_write is False

    def test_can_disable_auto_compact(self):
        """Verify auto_compact can be disabled."""
        config = DeltaWriteConfig(auto_compact=False)
        assert config.auto_compact is False

    def test_custom_target_file_size(self):
        """Verify custom target file size is respected."""
        config = DeltaWriteConfig(target_file_size_mb=256)
        assert config.target_file_size_mb == 256

    def test_custom_default_coalesce(self):
        """Verify custom default coalesce partitions is respected."""
        config = DeltaWriteConfig(default_coalesce_partitions=4)
        assert config.default_coalesce_partitions == 4

    def test_topic_overrides(self):
        """Verify topic-specific overrides are stored."""
        overrides = {"gps_pings": 2, "trips": 4}
        config = DeltaWriteConfig(topic_coalesce_overrides=overrides)
        assert config.topic_coalesce_overrides == overrides


class TestGetCoalescePartitions:
    """Tests for get_coalesce_partitions method."""

    def test_returns_default_for_unknown_topic(self):
        """Verify default is returned for topics without override."""
        config = DeltaWriteConfig(default_coalesce_partitions=1)
        assert config.get_coalesce_partitions("trips") == 1

    def test_returns_override_for_configured_topic(self):
        """Verify override is returned for configured topics."""
        config = DeltaWriteConfig(
            default_coalesce_partitions=1,
            topic_coalesce_overrides={"gps_pings": 2},
        )
        assert config.get_coalesce_partitions("gps_pings") == 2

    def test_returns_default_for_other_topics(self):
        """Verify default is used for topics not in overrides."""
        config = DeltaWriteConfig(
            default_coalesce_partitions=1,
            topic_coalesce_overrides={"gps_pings": 2},
        )
        assert config.get_coalesce_partitions("trips") == 1
        assert config.get_coalesce_partitions("payments") == 1

    def test_multiple_overrides(self):
        """Verify multiple topic overrides work correctly."""
        config = DeltaWriteConfig(
            default_coalesce_partitions=1,
            topic_coalesce_overrides={
                "gps_pings": 4,
                "trips": 2,
                "driver_status": 3,
            },
        )
        assert config.get_coalesce_partitions("gps_pings") == 4
        assert config.get_coalesce_partitions("trips") == 2
        assert config.get_coalesce_partitions("driver_status") == 3
        assert config.get_coalesce_partitions("ratings") == 1


class TestToWriteOptions:
    """Tests for to_write_options method."""

    def test_default_options_enable_optimize(self):
        """Verify default options enable auto-optimize."""
        config = DeltaWriteConfig()
        options = config.to_write_options()

        assert options["delta.autoOptimize.optimizeWrite"] == "true"
        assert options["delta.autoOptimize.autoCompact"] == "true"

    def test_options_can_be_disabled(self):
        """Verify options can be disabled."""
        config = DeltaWriteConfig(optimize_write=False, auto_compact=False)
        options = config.to_write_options()

        assert options["delta.autoOptimize.optimizeWrite"] == "false"
        assert options["delta.autoOptimize.autoCompact"] == "false"

    def test_file_size_converted_to_bytes(self):
        """Verify target file size is converted to bytes."""
        config = DeltaWriteConfig(target_file_size_mb=128)
        options = config.to_write_options()

        expected_bytes = 128 * 1024 * 1024  # 134217728
        assert options["delta.targetFileSize"] == str(expected_bytes)

    def test_custom_file_size_conversion(self):
        """Verify custom file size is converted correctly."""
        config = DeltaWriteConfig(target_file_size_mb=256)
        options = config.to_write_options()

        expected_bytes = 256 * 1024 * 1024  # 268435456
        assert options["delta.targetFileSize"] == str(expected_bytes)

    def test_returns_dict_with_string_values(self):
        """Verify all option values are strings."""
        config = DeltaWriteConfig()
        options = config.to_write_options()

        for key, value in options.items():
            assert isinstance(key, str)
            assert isinstance(value, str)


class TestDeltaWriteConfigImport:
    """Tests for DeltaWriteConfig import paths."""

    def test_import_from_config_module(self):
        """Verify DeltaWriteConfig can be imported from config module."""
        from spark_streaming.config import DeltaWriteConfig

        assert DeltaWriteConfig is not None

    def test_import_directly(self):
        """Verify DeltaWriteConfig can be imported directly."""
        from spark_streaming.config.delta_write_config import DeltaWriteConfig

        assert DeltaWriteConfig is not None
