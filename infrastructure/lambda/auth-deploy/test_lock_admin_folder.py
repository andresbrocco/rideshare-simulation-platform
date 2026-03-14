"""Unit tests for the Grafana Admin folder lock module.

Tests validate the three behavioural scenarios for lock_admin_folder():
- Successful lock (HTTP 200 → status "locked")
- Folder not yet provisioned (HTTP 404 → status "skipped")
- Other HTTP errors are propagated to the caller

These are pure unit tests — no running services required.
"""

from __future__ import annotations

import importlib.util
import io
import json
import types
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------

_MODULE_PATH = __import__("pathlib").Path(__file__).parent / "lock_grafana_admin_folder.py"
_MODULE_NAME = "lock_grafana_admin_folder"

_GRAFANA_URL = "http://localhost:3001"
_ADMIN_AUTH = "Basic YWRtaW46YWRtaW4="


def _load_lock_module() -> types.ModuleType:
    """Load lock_grafana_admin_folder.py as a fresh module object."""
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module: types.ModuleType = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLockAdminFolder:
    @pytest.mark.unit
    def test_success_returns_locked(self) -> None:
        """HTTP 200 from Grafana results in status 'locked'."""
        mod = _load_lock_module()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"message":"Permissions updated"}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp) as mock_open:
            result = mod.lock_admin_folder(
                grafana_url=_GRAFANA_URL,
                admin_auth_header=_ADMIN_AUTH,
            )

        assert result == {"status": "locked", "folder_uid": "admin"}
        req = mock_open.call_args[0][0]
        assert req.full_url == f"{_GRAFANA_URL}/api/folders/admin/permissions"

    @pytest.mark.unit
    def test_sends_empty_items_payload(self) -> None:
        """The POST body must be {"items": []} to strip all explicit permissions."""
        mod = _load_lock_module()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"{}"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp) as mock_open:
            mod.lock_admin_folder(
                grafana_url=_GRAFANA_URL,
                admin_auth_header=_ADMIN_AUTH,
            )

        req = mock_open.call_args[0][0]
        assert json.loads(req.data) == {"items": []}

    @pytest.mark.unit
    def test_404_returns_skipped(self) -> None:
        """HTTP 404 (folder not yet created) returns status 'skipped'."""
        mod = _load_lock_module()
        error = urllib.error.HTTPError(
            url=f"{_GRAFANA_URL}/api/folders/admin/permissions",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=io.BytesIO(b"not found"),  # type: ignore[arg-type]
        )

        with patch.object(urllib.request, "urlopen", side_effect=error):
            result = mod.lock_admin_folder(
                grafana_url=_GRAFANA_URL,
                admin_auth_header=_ADMIN_AUTH,
            )

        assert result == {"status": "skipped", "reason": "folder_not_found"}

    @pytest.mark.unit
    def test_500_raises(self) -> None:
        """Non-404 HTTP errors are propagated."""
        mod = _load_lock_module()
        error = urllib.error.HTTPError(
            url=f"{_GRAFANA_URL}/api/folders/admin/permissions",
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=io.BytesIO(b"error"),  # type: ignore[arg-type]
        )

        with patch.object(urllib.request, "urlopen", side_effect=error):
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                mod.lock_admin_folder(
                    grafana_url=_GRAFANA_URL,
                    admin_auth_header=_ADMIN_AUTH,
                )

        assert exc_info.value.code == 500

    @pytest.mark.unit
    def test_custom_folder_uid(self) -> None:
        """A custom folder_uid is used in the URL and returned in the result."""
        mod = _load_lock_module()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"{}"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp) as mock_open:
            result = mod.lock_admin_folder(
                grafana_url=_GRAFANA_URL,
                admin_auth_header=_ADMIN_AUTH,
                folder_uid="custom-folder",
            )

        assert result == {"status": "locked", "folder_uid": "custom-folder"}
        req = mock_open.call_args[0][0]
        assert "/api/folders/custom-folder/permissions" in req.full_url

    @pytest.mark.unit
    def test_correct_url_construction(self) -> None:
        """The full URL combines grafana_url + /api/folders/{uid}/permissions."""
        mod = _load_lock_module()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"{}"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp) as mock_open:
            mod.lock_admin_folder(
                grafana_url="http://grafana:3000",
                admin_auth_header=_ADMIN_AUTH,
            )

        req = mock_open.call_args[0][0]
        assert req.full_url == "http://grafana:3000/api/folders/admin/permissions"
        assert req.get_header("Authorization") == _ADMIN_AUTH
        assert req.get_header("Content-type") == "application/json"
        assert req.get_method() == "POST"
