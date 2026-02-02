"""Table existence checker for dashboard provisioning.

Validates that required tables exist before creating dashboards.
"""

import logging
from typing import Any

from provisioning.client import SupersetClient

logger = logging.getLogger(__name__)


class TableChecker:
    """Checks if tables exist in the Spark database.

    Uses Superset's SQL execution to query table existence.
    Results are cached to avoid repeated queries.
    """

    def __init__(self, client: SupersetClient, database_id: int) -> None:
        """Initialize the checker.

        Args:
            client: Superset REST API client
            database_id: ID of the database connection to check
        """
        self.client = client
        self.database_id = database_id
        self._cache: dict[str, bool] = {}

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists.

        Args:
            table_name: Fully qualified table name (e.g., "bronze.bronze_trips")

        Returns:
            True if table exists, False otherwise
        """
        if table_name in self._cache:
            return self._cache[table_name]

        # Parse schema and table
        parts = table_name.split(".")
        if len(parts) == 2:
            schema, table = parts
        else:
            schema = "default"
            table = parts[0]

        exists = self._check_table_exists(schema, table)
        self._cache[table_name] = exists
        return exists

    def _check_table_exists(self, schema: str, table: str) -> bool:
        """Query Spark to check table existence.

        Args:
            schema: Schema/database name
            table: Table name

        Returns:
            True if table exists
        """
        try:
            # Use SHOW TABLES to check existence
            sql = f"SHOW TABLES IN {schema} LIKE '{table}'"
            result = self._execute_sql(sql)

            # If we get any rows back, the table exists
            if result and "data" in result:
                return len(result["data"]) > 0
            return False

        except Exception as e:
            logger.warning("Failed to check table %s.%s: %s", schema, table, e)
            return False

    def _execute_sql(self, sql: str) -> dict[str, Any]:
        """Execute SQL query via Superset.

        Args:
            sql: SQL query to execute

        Returns:
            Query result
        """
        # Use Superset's SQL Lab execution endpoint
        response = self.client._request(
            "POST",
            "/api/v1/sqllab/execute/",
            json_data={
                "database_id": self.database_id,
                "sql": sql,
                "runAsync": False,
                "select_as_cta": False,
            },
            timeout=60,
        )
        return response

    def check_tables(self, table_names: tuple[str, ...]) -> tuple[list[str], list[str]]:
        """Check multiple tables and return found/missing lists.

        Args:
            table_names: Tuple of table names to check

        Returns:
            Tuple of (found_tables, missing_tables)
        """
        found: list[str] = []
        missing: list[str] = []

        for table in table_names:
            if self.table_exists(table):
                found.append(table)
            else:
                missing.append(table)

        return found, missing

    def clear_cache(self) -> None:
        """Clear the table existence cache."""
        self._cache.clear()
