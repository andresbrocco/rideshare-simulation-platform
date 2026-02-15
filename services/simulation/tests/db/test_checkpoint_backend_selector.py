"""Unit tests for checkpoint backend selector."""

from unittest.mock import MagicMock, patch

import pytest

from src.db import get_checkpoint_manager
from src.settings import Settings


@pytest.mark.unit
class TestCheckpointBackendSelector:
    """Tests for get_checkpoint_manager backend selection logic."""

    def test_sqlite_backend_selected_by_default(self) -> None:
        """SQLite is the default backend when no storage_type override."""
        settings = Settings()
        session = MagicMock()

        manager = get_checkpoint_manager(settings, session=session)

        assert type(manager).__name__ == "CheckpointManager"

    def test_sqlite_backend_requires_session(self) -> None:
        """SQLite backend raises ValueError when session is not provided."""
        settings = Settings()

        with pytest.raises(ValueError, match="SQLite checkpoint backend requires session"):
            get_checkpoint_manager(settings, session=None)

    def test_s3_backend_selected_when_configured(self) -> None:
        """S3 backend is selected when checkpoint_storage_type=s3."""
        settings = Settings(
            simulation={
                "checkpoint_storage_type": "s3",
                "checkpoint_s3_bucket": "test-bucket",
                "checkpoint_s3_prefix": "test-prefix",
            },
        )

        with patch("boto3.client") as mock_boto3:
            mock_s3_client = MagicMock()
            mock_boto3.return_value = mock_s3_client

            manager = get_checkpoint_manager(settings)

            assert type(manager).__name__ == "S3CheckpointManager"
            assert manager.bucket_name == "test-bucket"
            assert manager.key == "test-prefix/latest.json.gz"

    def test_s3_backend_uses_configured_bucket_and_prefix(self) -> None:
        """S3 backend uses custom bucket and prefix from settings."""
        settings = Settings(
            simulation={
                "checkpoint_storage_type": "s3",
                "checkpoint_s3_bucket": "my-custom-bucket",
                "checkpoint_s3_prefix": "my-custom-prefix",
            },
        )

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value = MagicMock()

            manager = get_checkpoint_manager(settings)

            assert manager.bucket_name == "my-custom-bucket"
            assert manager.key == "my-custom-prefix/latest.json.gz"

    def test_s3_backend_raises_error_if_boto3_not_installed(self) -> None:
        """S3 backend raises ValueError when boto3 is not available."""
        settings = Settings(
            simulation={"checkpoint_storage_type": "s3"},
        )

        with (
            patch.dict("sys.modules", {"boto3": None}),
            pytest.raises(ValueError, match="S3 checkpoint backend requires boto3"),
        ):
            get_checkpoint_manager(settings)

    def test_unknown_storage_type_raises_error(self) -> None:
        """Unknown storage type raises ValueError."""
        settings = MagicMock()
        settings.simulation.checkpoint_storage_type = "redis"

        with pytest.raises(ValueError, match="Unknown checkpoint storage type"):
            get_checkpoint_manager(settings)

    def test_default_settings_use_sqlite(self) -> None:
        """Verify default SimulationSettings has storage_type=sqlite."""
        settings = Settings()

        assert settings.simulation.checkpoint_storage_type == "sqlite"
        assert settings.simulation.checkpoint_s3_bucket == "rideshare-checkpoints"
        assert settings.simulation.checkpoint_s3_prefix == "simulation"
