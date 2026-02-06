"""Unit tests for SQL validation module."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from provisioning.dashboards.base import DatasetDefinition
from provisioning.validators import (
    SparkSQLValidator,
    ValidationStatus,
    collect_all_datasets,
    validate_datasets,
)


@pytest.fixture
def mock_connection() -> MagicMock:
    """Create a mock database connection."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


@pytest.fixture
def sample_dataset() -> DatasetDefinition:
    """Create a sample dataset for testing."""
    return DatasetDefinition(
        name="test_dataset",
        sql="SELECT * FROM test_table",
        description="Test dataset",
    )


@pytest.fixture
def sample_dataset_allow_empty() -> DatasetDefinition:
    """Create a sample dataset that allows empty results."""
    return DatasetDefinition(
        name="test_dataset_empty_allowed",
        sql="SELECT * FROM empty_table",
        description="Test dataset that allows empty results",
        allow_empty_results=True,
    )


class TestValidateDataset:
    """Tests for SparkSQLValidator.validate_dataset."""

    def test_validate_dataset_pass(
        self,
        mock_connection: MagicMock,
        sample_dataset: DatasetDefinition,
    ) -> None:
        """Test validation passes when rows are returned."""
        mock_cursor = mock_connection.cursor.return_value
        mock_cursor.fetchone.return_value = (100,)

        # Inject mock connection
        validator = SparkSQLValidator(connection=mock_connection)
        result = validator.validate_dataset(sample_dataset)

        assert result.status == ValidationStatus.PASS
        assert result.row_count == 100
        assert result.error_message is None
        assert result.dataset_name == "test_dataset"

    def test_validate_dataset_fail_empty(
        self,
        mock_connection: MagicMock,
        sample_dataset: DatasetDefinition,
    ) -> None:
        """Test validation fails when 0 rows and allow_empty=False."""
        mock_cursor = mock_connection.cursor.return_value
        mock_cursor.fetchone.return_value = (0,)

        validator = SparkSQLValidator(connection=mock_connection)
        result = validator.validate_dataset(sample_dataset)

        assert result.status == ValidationStatus.FAIL
        assert result.row_count == 0
        assert result.error_message == "Query returned 0 rows"

    def test_validate_dataset_warn_empty_allowed(
        self,
        mock_connection: MagicMock,
        sample_dataset_allow_empty: DatasetDefinition,
    ) -> None:
        """Test validation warns when 0 rows but allow_empty=True."""
        mock_cursor = mock_connection.cursor.return_value
        mock_cursor.fetchone.return_value = (0,)

        validator = SparkSQLValidator(connection=mock_connection)
        result = validator.validate_dataset(sample_dataset_allow_empty)

        assert result.status == ValidationStatus.WARN
        assert result.row_count == 0
        assert result.error_message == "empty allowed"

    def test_validate_dataset_fail_sql_error(
        self,
        mock_connection: MagicMock,
        sample_dataset: DatasetDefinition,
    ) -> None:
        """Test validation fails when SQL throws an exception."""
        mock_cursor = mock_connection.cursor.return_value
        mock_cursor.execute.side_effect = Exception("Column 'foo' not found")

        validator = SparkSQLValidator(connection=mock_connection)
        result = validator.validate_dataset(sample_dataset)

        assert result.status == ValidationStatus.FAIL
        assert result.row_count is None
        assert "Column 'foo' not found" in str(result.error_message)


class TestCollectAllDatasets:
    """Tests for collect_all_datasets function."""

    def test_collects_from_all_layers(self) -> None:
        """Test that datasets are collected from all layer modules."""
        datasets = collect_all_datasets()

        # Should have datasets from each layer
        dataset_names = {d.name for d in datasets}

        # Check representative datasets from each layer
        assert "bronze_ingestion_events" in dataset_names  # Bronze
        assert "silver_staging_health" in dataset_names  # Silver
        assert "gold_driver_performance" in dataset_names  # Gold
        assert "ops_driver_locations" in dataset_names  # Map

    def test_deduplicates_by_name(self) -> None:
        """Test that duplicate dataset names are deduplicated."""
        datasets = collect_all_datasets()

        # All names should be unique
        names = [d.name for d in datasets]
        assert len(names) == len(set(names)), "Duplicate dataset names found"


class TestValidateDatasets:
    """Tests for validate_datasets function."""

    def test_validate_datasets_all_pass(self) -> None:
        """Test validation summary when all datasets pass."""
        mock_hive_module = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (50,)
        mock_hive_module.connect.return_value = mock_conn

        test_datasets = (
            DatasetDefinition(name="ds1", sql="SELECT 1"),
            DatasetDefinition(name="ds2", sql="SELECT 2"),
        )

        with patch.dict(
            sys.modules,
            {"pyhive": MagicMock(hive=mock_hive_module), "pyhive.hive": mock_hive_module},
        ):
            summary = validate_datasets(
                host="localhost",
                port=10000,
                datasets=test_datasets,
            )

        assert summary.total == 2
        assert summary.passed == 2
        assert summary.warned == 0
        assert summary.failed == 0
        assert not summary.has_critical_failures

    def test_validate_datasets_with_failures(self) -> None:
        """Test validation summary when some datasets fail."""
        mock_hive_module = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        # First call returns rows, second call returns 0, third raises error
        mock_cursor.fetchone.side_effect = [(50,), (0,), Exception("SQL error")]
        mock_hive_module.connect.return_value = mock_conn

        test_datasets = (
            DatasetDefinition(name="ds_pass", sql="SELECT 1"),
            DatasetDefinition(name="ds_fail_empty", sql="SELECT 2"),
            DatasetDefinition(name="ds_fail_error", sql="SELECT 3"),
        )

        with patch.dict(
            sys.modules,
            {"pyhive": MagicMock(hive=mock_hive_module), "pyhive.hive": mock_hive_module},
        ):
            summary = validate_datasets(
                host="localhost",
                port=10000,
                datasets=test_datasets,
            )

        assert summary.total == 3
        assert summary.passed == 1
        assert summary.warned == 0
        assert summary.failed == 2
        assert summary.has_critical_failures

    def test_validate_datasets_with_warnings(self) -> None:
        """Test validation summary with warnings (allow_empty_results)."""
        mock_hive_module = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.side_effect = [(50,), (0,)]
        mock_hive_module.connect.return_value = mock_conn

        test_datasets = (
            DatasetDefinition(name="ds_pass", sql="SELECT 1"),
            DatasetDefinition(name="ds_warn", sql="SELECT 2", allow_empty_results=True),
        )

        with patch.dict(
            sys.modules,
            {"pyhive": MagicMock(hive=mock_hive_module), "pyhive.hive": mock_hive_module},
        ):
            summary = validate_datasets(
                host="localhost",
                port=10000,
                datasets=test_datasets,
            )

        assert summary.total == 2
        assert summary.passed == 1
        assert summary.warned == 1
        assert summary.failed == 0
        assert not summary.has_critical_failures


class TestSparkSQLValidatorContextManager:
    """Tests for SparkSQLValidator context manager protocol."""

    def test_context_manager_connects_and_closes(self) -> None:
        """Test that context manager properly connects and closes."""
        mock_hive_module = MagicMock()
        mock_conn = MagicMock()
        mock_hive_module.connect.return_value = mock_conn

        with patch.dict(
            sys.modules,
            {"pyhive": MagicMock(hive=mock_hive_module), "pyhive.hive": mock_hive_module},
        ):
            with SparkSQLValidator(host="localhost", port=10000) as validator:
                assert validator._connection is not None

            mock_conn.close.assert_called_once()

    def test_not_connected_raises_error(self) -> None:
        """Test that validate_dataset raises error when not connected."""
        validator = SparkSQLValidator()
        dataset = DatasetDefinition(name="test", sql="SELECT 1")

        with pytest.raises(RuntimeError, match="Not connected"):
            validator.validate_dataset(dataset)

    def test_injected_connection_used(self, mock_connection: MagicMock) -> None:
        """Test that injected connection is used without calling connect."""
        mock_cursor = mock_connection.cursor.return_value
        mock_cursor.fetchone.return_value = (10,)

        validator = SparkSQLValidator(connection=mock_connection)
        # connect() should not call pyhive since connection is already set
        validator.connect()

        dataset = DatasetDefinition(name="test", sql="SELECT 1")
        result = validator.validate_dataset(dataset)

        assert result.status == ValidationStatus.PASS
        assert result.row_count == 10
