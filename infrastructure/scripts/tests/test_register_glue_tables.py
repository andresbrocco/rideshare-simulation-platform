"""Tests for register-glue-tables.py.

Each test case patches both boto3 clients (glue and s3) to avoid real AWS
calls. The module is imported via importlib so the top-level boto3.client()
calls that create module-level clients happen inside the patched scope.
"""

import importlib.util
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Helpers to load the script under test as a module
# ---------------------------------------------------------------------------

SCRIPT_PATH = Path(__file__).parent.parent / "register-glue-tables.py"


def _load_module(env_overrides: dict[str, str] | None = None) -> types.ModuleType:
    """Import register-glue-tables.py as a fresh module for each test.

    Optional *env_overrides* dict patches ``os.getenv`` so module-level
    constants (like ``GLUE_DATABASE_PREFIX``) pick up the override.
    """
    env_patch = patch.dict("os.environ", env_overrides) if env_overrides else None
    if env_patch:
        env_patch.start()
    try:
        spec = importlib.util.spec_from_file_location("register_glue_tables", SCRIPT_PATH)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    finally:
        if env_patch:
            env_patch.stop()
    return module


def _client_error(code: str) -> ClientError:
    """Build a botocore ClientError with the given error code."""
    return ClientError(
        {"Error": {"Code": code, "Message": code}},
        "operation",
    )


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestRegisterGlueTables(unittest.TestCase):
    """Unit tests for register-glue-tables.py."""

    def _make_clients(self) -> tuple[MagicMock, MagicMock]:
        """Return (mock_glue, mock_s3) with sensible default behaviour."""
        mock_glue = MagicMock()
        mock_s3 = MagicMock()
        # head_object succeeds by default (table data exists)
        mock_s3.head_object.return_value = {}
        # create_table succeeds by default
        mock_glue.create_table.return_value = {}
        # create_database succeeds by default
        mock_glue.create_database.return_value = {}
        return mock_glue, mock_s3

    def _patch_clients(
        self, mock_glue: MagicMock, mock_s3: MagicMock
    ) -> patch:  # type: ignore[type-arg]
        """Return a context-manager patch that routes boto3.client() correctly."""

        def _client_factory(service: str, **kwargs: object) -> MagicMock:
            if service == "glue":
                return mock_glue
            if service == "s3":
                return mock_s3
            raise ValueError(f"Unexpected boto3 service: {service}")

        return patch("boto3.client", side_effect=_client_factory)

    # ------------------------------------------------------------------
    # 1. register_new_table
    # ------------------------------------------------------------------

    def test_register_new_table(self) -> None:
        """A table with S3 data that is not yet in Glue should be registered."""
        mock_glue, mock_s3 = self._make_clients()

        with self._patch_clients(mock_glue, mock_s3):
            mod = _load_module()
            result = mod.register_table("bronze_trips", "rideshare-bronze", "rideshare_bronze")

        self.assertTrue(result)
        mock_glue.create_table.assert_called_once()
        call_kwargs = mock_glue.create_table.call_args.kwargs
        self.assertEqual(call_kwargs["DatabaseName"], "rideshare_bronze")
        self.assertEqual(call_kwargs["TableInput"]["Name"], "bronze_trips")

    # ------------------------------------------------------------------
    # 2. skip_already_exists
    # ------------------------------------------------------------------

    def test_skip_already_exists(self) -> None:
        """AlreadyExistsException should make the call idempotent (returns False)."""
        mock_glue, mock_s3 = self._make_clients()
        mock_glue.create_table.side_effect = _client_error("AlreadyExistsException")

        with self._patch_clients(mock_glue, mock_s3):
            mod = _load_module()
            result = mod.register_table("bronze_trips", "rideshare-bronze", "rideshare_bronze")

        self.assertFalse(result)
        mock_glue.create_table.assert_called_once()

    # ------------------------------------------------------------------
    # 3. skip_no_s3_data
    # ------------------------------------------------------------------

    def test_skip_no_s3_data(self) -> None:
        """Tables with no Delta log in S3 should be skipped (returns False)."""
        mock_glue, mock_s3 = self._make_clients()
        mock_s3.head_object.side_effect = _client_error("404")

        with self._patch_clients(mock_glue, mock_s3):
            mod = _load_module()
            result = mod.register_table("bronze_trips", "rideshare-bronze", "rideshare_bronze")

        self.assertFalse(result)
        mock_glue.create_table.assert_not_called()

    # ------------------------------------------------------------------
    # 4. unexpected_error_sets_exit_code
    # ------------------------------------------------------------------

    def test_unexpected_error_sets_exit_code(self) -> None:
        """An unexpected Glue error should be re-raised by register_table."""
        mock_glue, mock_s3 = self._make_clients()
        mock_glue.create_table.side_effect = _client_error("AccessDeniedException")

        with self._patch_clients(mock_glue, mock_s3):
            mod = _load_module()
            with self.assertRaises(ClientError) as ctx:
                mod.register_table("bronze_trips", "rideshare-bronze", "rideshare_bronze")

        self.assertEqual(ctx.exception.response["Error"]["Code"], "AccessDeniedException")

    # ------------------------------------------------------------------
    # 5. dlq_columns
    # ------------------------------------------------------------------

    def test_dlq_columns(self) -> None:
        """DLQ tables should include the extra _error_message/_error_timestamp columns."""
        mock_glue, mock_s3 = self._make_clients()

        with self._patch_clients(mock_glue, mock_s3):
            mod = _load_module()
            result = mod.register_table("dlq_bronze_trips", "rideshare-bronze", "rideshare_bronze")

        self.assertTrue(result)
        call_kwargs = mock_glue.create_table.call_args.kwargs
        columns = call_kwargs["TableInput"]["StorageDescriptor"]["Columns"]
        column_names = [c["Name"] for c in columns]
        self.assertIn("_error_message", column_names)
        self.assertIn("_error_timestamp", column_names)

        # Standard tables must NOT have DLQ columns
        mock_glue.reset_mock()
        mock_s3.head_object.return_value = {}
        mock_glue.create_table.return_value = {}

        with self._patch_clients(mock_glue, mock_s3):
            mod2 = _load_module()
            mod2.register_table("bronze_trips", "rideshare-bronze", "rideshare_bronze")

        call_kwargs2 = mock_glue.create_table.call_args.kwargs
        columns2 = call_kwargs2["TableInput"]["StorageDescriptor"]["Columns"]
        standard_names = [c["Name"] for c in columns2]
        self.assertNotIn("_error_message", standard_names)
        self.assertNotIn("_error_timestamp", standard_names)

    # ------------------------------------------------------------------
    # 6. layer_routing (uses main → ensure_database_exists + register)
    # ------------------------------------------------------------------

    def test_layer_routing(self) -> None:
        """main() with --layer bronze should use rideshare_bronze database."""
        mock_glue, mock_s3 = self._make_clients()

        with self._patch_clients(mock_glue, mock_s3):
            mod = _load_module()

            import sys as _sys

            original_argv = _sys.argv
            try:
                _sys.argv = ["register-glue-tables.py", "--layer", "bronze"]
                code = mod.main()
            finally:
                _sys.argv = original_argv

        self.assertEqual(code, 0)
        # 16 tables = 8 bronze + 8 DLQ
        self.assertEqual(mock_glue.create_table.call_count, 16)
        # ensure_database_exists called with prefixed name
        mock_glue.create_database.assert_called_once_with(
            DatabaseInput={"Name": "rideshare_bronze"}
        )

    # ------------------------------------------------------------------
    # 7. ensure_database_creates_new
    # ------------------------------------------------------------------

    def test_ensure_database_creates_new(self) -> None:
        """ensure_database_exists should call create_database for a new database."""
        mock_glue, mock_s3 = self._make_clients()

        with self._patch_clients(mock_glue, mock_s3):
            mod = _load_module()
            mod.ensure_database_exists("rideshare_bronze")

        mock_glue.create_database.assert_called_once_with(
            DatabaseInput={"Name": "rideshare_bronze"}
        )

    # ------------------------------------------------------------------
    # 8. ensure_database_already_exists
    # ------------------------------------------------------------------

    def test_ensure_database_already_exists(self) -> None:
        """AlreadyExistsException from create_database should be handled gracefully."""
        mock_glue, mock_s3 = self._make_clients()
        mock_glue.create_database.side_effect = _client_error("AlreadyExistsException")

        with self._patch_clients(mock_glue, mock_s3):
            mod = _load_module()
            # Should not raise
            mod.ensure_database_exists("rideshare_bronze")

        mock_glue.create_database.assert_called_once()

    # ------------------------------------------------------------------
    # 9. ensure_database_unexpected_error
    # ------------------------------------------------------------------

    def test_ensure_database_unexpected_error(self) -> None:
        """Unexpected errors from create_database should propagate."""
        mock_glue, mock_s3 = self._make_clients()
        mock_glue.create_database.side_effect = _client_error("AccessDeniedException")

        with self._patch_clients(mock_glue, mock_s3):
            mod = _load_module()
            with self.assertRaises(ClientError) as ctx:
                mod.ensure_database_exists("rideshare_bronze")

        self.assertEqual(ctx.exception.response["Error"]["Code"], "AccessDeniedException")

    # ------------------------------------------------------------------
    # 10. custom_prefix_via_env_var
    # ------------------------------------------------------------------

    def test_custom_prefix_via_env_var(self) -> None:
        """GLUE_DATABASE_PREFIX env var should override the default 'rideshare' prefix."""
        mock_glue, mock_s3 = self._make_clients()

        with self._patch_clients(mock_glue, mock_s3):
            mod = _load_module(env_overrides={"GLUE_DATABASE_PREFIX": "myproject"})

            import sys as _sys

            original_argv = _sys.argv
            try:
                _sys.argv = ["register-glue-tables.py", "--layer", "bronze"]
                code = mod.main()
            finally:
                _sys.argv = original_argv

        self.assertEqual(code, 0)
        mock_glue.create_database.assert_called_once_with(
            DatabaseInput={"Name": "myproject_bronze"}
        )
        # All 16 create_table calls should use the custom database name
        for call in mock_glue.create_table.call_args_list:
            self.assertEqual(call.kwargs["DatabaseName"], "myproject_bronze")


if __name__ == "__main__":
    unittest.main()
