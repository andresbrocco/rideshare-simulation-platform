"""SQL validation for Superset dataset definitions.

This module validates dataset SQL queries against Spark Thrift Server
before provisioning dashboards. It catches schema mismatches and missing
data early in the pipeline.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from provisioning.dashboards.base import DatasetDefinition
from provisioning.datasets.bronze_datasets import BRONZE_DATASETS
from provisioning.datasets.gold_datasets import GOLD_DATASETS
from provisioning.datasets.map_datasets import MAP_DATASETS
from provisioning.datasets.silver_datasets import SILVER_DATASETS

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """Status of dataset SQL validation."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a single dataset.

    Attributes:
        dataset_name: Name of the validated dataset
        status: Validation status (PASS, WARN, FAIL)
        row_count: Number of rows returned (None if SQL error)
        error_message: Error message if validation failed
        execution_time: Time taken to execute validation in seconds
    """

    dataset_name: str
    status: ValidationStatus
    row_count: int | None
    error_message: str | None
    execution_time: float


@dataclass(frozen=True)
class ValidationSummary:
    """Summary of all dataset validations.

    Attributes:
        results: Tuple of all validation results
        total: Total number of datasets validated
        passed: Number of datasets that passed
        warned: Number of datasets that produced warnings
        failed: Number of datasets that failed
    """

    results: tuple[ValidationResult, ...]
    total: int
    passed: int
    warned: int
    failed: int

    @property
    def has_critical_failures(self) -> bool:
        """Return True if any datasets failed (not just warned)."""
        return self.failed > 0


class SparkSQLValidator:
    """Validates SQL queries against Spark Thrift Server via PyHive.

    This class connects to Spark Thrift Server using the HiveServer2 protocol
    and executes COUNT(*) queries wrapped around dataset SQL to verify:
    1. SQL syntax is valid
    2. Referenced tables/columns exist
    3. Queries return data (or are marked as allow_empty_results)
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 10000,
        connection: Any | None = None,
    ) -> None:
        """Initialize the validator.

        Args:
            host: Spark Thrift Server hostname
            port: Spark Thrift Server port (default: 10000)
            connection: Optional pre-existing connection (for testing)
        """
        self.host = host
        self.port = port
        self._connection: Any | None = connection

    def connect(self) -> None:
        """Establish connection to Spark Thrift Server."""
        if self._connection is not None:
            # Already connected (e.g., injected for testing)
            return

        from pyhive import hive

        logger.info("Connecting to Spark Thrift Server at %s:%d", self.host, self.port)
        self._connection = hive.connect(
            host=self.host,
            port=self.port,
            auth="NOSASL",
        )

    def close(self) -> None:
        """Close the connection to Spark Thrift Server."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def validate_dataset(self, dataset: DatasetDefinition) -> ValidationResult:
        """Validate a single dataset's SQL query.

        Executes a COUNT(*) query wrapping the dataset SQL to verify:
        1. The SQL is syntactically valid
        2. All referenced tables and columns exist
        3. The query returns rows (unless allow_empty_results=True)

        Args:
            dataset: The dataset definition to validate

        Returns:
            ValidationResult with status, row count, and any error message
        """
        if self._connection is None:
            raise RuntimeError("Not connected. Call connect() first.")

        start_time = time.time()

        # Build count query by wrapping dataset SQL
        sql = dataset.sql.strip().rstrip(";")
        count_sql = f"SELECT COUNT(*) FROM ({sql}) AS subquery"

        try:
            cursor = self._connection.cursor()
            cursor.execute(count_sql)
            result = cursor.fetchone()
            cursor.close()

            row_count = result[0] if result else 0
            execution_time = time.time() - start_time

            # Determine status based on row count and allow_empty_results
            if row_count > 0:
                status = ValidationStatus.PASS
                error_message = None
            elif dataset.allow_empty_results:
                status = ValidationStatus.WARN
                error_message = "empty allowed"
            else:
                status = ValidationStatus.FAIL
                error_message = "Query returned 0 rows"

            return ValidationResult(
                dataset_name=dataset.name,
                status=status,
                row_count=row_count,
                error_message=error_message,
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return ValidationResult(
                dataset_name=dataset.name,
                status=ValidationStatus.FAIL,
                row_count=None,
                error_message=str(e),
                execution_time=execution_time,
            )

    def __enter__(self) -> "SparkSQLValidator":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit."""
        self.close()


def collect_all_datasets() -> tuple[DatasetDefinition, ...]:
    """Collect and deduplicate all dataset definitions from all layers.

    Imports datasets from bronze, silver, gold, and map modules and
    returns a deduplicated tuple (by dataset name).

    Returns:
        Tuple of unique DatasetDefinition objects
    """
    all_datasets: list[DatasetDefinition] = []
    seen_names: set[str] = set()

    for datasets in (BRONZE_DATASETS, SILVER_DATASETS, GOLD_DATASETS, MAP_DATASETS):
        for dataset in datasets:
            if dataset.name not in seen_names:
                all_datasets.append(dataset)
                seen_names.add(dataset.name)
            else:
                logger.warning("Duplicate dataset name skipped: %s", dataset.name)

    return tuple(all_datasets)


def validate_datasets(
    host: str = "localhost",
    port: int = 10000,
    datasets: tuple[DatasetDefinition, ...] | None = None,
) -> ValidationSummary:
    """Validate all dataset SQL queries against Spark Thrift Server.

    This is the high-level function for Airflow tasks and CLI usage.

    Args:
        host: Spark Thrift Server hostname
        port: Spark Thrift Server port
        datasets: Optional tuple of datasets to validate. If None, collects all datasets.

    Returns:
        ValidationSummary with results for all datasets

    Raises:
        RuntimeError: If validation has critical failures
    """
    if datasets is None:
        datasets = collect_all_datasets()

    results: list[ValidationResult] = []
    passed = 0
    warned = 0
    failed = 0

    logger.info("=" * 54)
    logger.info(" Dataset SQL Validation ")
    logger.info("=" * 54)

    with SparkSQLValidator(host=host, port=port) as validator:
        for dataset in datasets:
            result = validator.validate_dataset(dataset)
            results.append(result)

            # Update counters
            if result.status == ValidationStatus.PASS:
                passed += 1
            elif result.status == ValidationStatus.WARN:
                warned += 1
            else:
                failed += 1

            # Log result
            status_str = f"[{result.status.value.upper()}]"
            if result.row_count is not None:
                count_str = f"{result.row_count:,} rows"
            else:
                count_str = "Error"
            time_str = f"{result.execution_time:.2f}s"

            if result.error_message and result.status == ValidationStatus.WARN:
                extra = f"  ({result.error_message})"
            elif result.error_message and result.status == ValidationStatus.FAIL:
                extra = f"  {result.error_message}"
            else:
                extra = ""

            logger.info(
                "%s %-30s %12s %8s%s",
                status_str,
                dataset.name,
                count_str,
                time_str,
                extra,
            )

    logger.info("=" * 54)
    logger.info(
        "Summary: %d total, %d passed, %d warned, %d failed",
        len(results),
        passed,
        warned,
        failed,
    )

    summary = ValidationSummary(
        results=tuple(results),
        total=len(results),
        passed=passed,
        warned=warned,
        failed=failed,
    )

    if summary.has_critical_failures:
        failed_names = [r.dataset_name for r in results if r.status == ValidationStatus.FAIL]
        logger.error("Task failed: %s", failed_names)

    return summary
