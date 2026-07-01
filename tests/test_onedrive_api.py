"""Unit tests for OneDrive config helpers and scan integration.

These tests do NOT require a real OneDrive account, msal, or httpx:
- Config helpers are tested directly
- _do_scan is tested with patched dependencies
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── _load_config / _save_config ───────────────────────────────────────────────

def test_load_config_missing_file(tmp_path, monkeypatch):
    import api.main as m
    monkeypatch.setattr(m, "_CONFIG_FILE", tmp_path / "config.json")
    assert m._load_config() == {}


def test_save_and_load_config(tmp_path, monkeypatch):
    import api.main as m
    monkeypatch.setattr(m, "_CONFIG_FILE", tmp_path / "config.json")
    m._save_config({"onedrive": {"client_id": "test-id"}})
    assert m._load_config()["onedrive"]["client_id"] == "test-id"


def test_save_config_creates_parent_dirs(tmp_path, monkeypatch):
    import api.main as m
    deep = tmp_path / "a" / "b" / "config.json"
    monkeypatch.setattr(m, "_CONFIG_FILE", deep)
    m._save_config({"x": 1})
    assert deep.exists()


# ── onedrive_status helper logic ──────────────────────────────────────────────

def test_status_not_configured(tmp_path, monkeypatch):
    """No config file → configured=False, authenticated=False."""
    import api.main as m
    monkeypatch.setattr(m, "_CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(m, "_OD_CACHE_FILE", tmp_path / "od.bin")

    # Call the function directly (it reads module-level vars)
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(
        _async_call(m.onedrive_status)
    ) if False else m.onedrive_status()
    assert result["configured"] is False
    assert result["authenticated"] is False


def test_status_configured_no_cache(tmp_path, monkeypatch):
    import api.main as m
    monkeypatch.setattr(m, "_CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(m, "_OD_CACHE_FILE", tmp_path / "od.bin")
    m._save_config({"onedrive": {"client_id": "abc"}})

    result = m.onedrive_status()
    assert result["configured"] is True
    assert result["authenticated"] is False


def test_save_config_endpoint(tmp_path, monkeypatch):
    """onedrive_save_config stores client_id and preserves other keys."""
    import api.main as m
    monkeypatch.setattr(m, "_CONFIG_FILE", tmp_path / "config.json")
    # Pre-existing config
    m._save_config({"google": {"client_id": "g-id"}})

    from pydantic import BaseModel
    class Body(BaseModel):
        client_id: str

    m.onedrive_save_config(m._OneDriveConfigBody(client_id="new-od-id"))
    cfg = m._load_config()
    assert cfg["onedrive"]["client_id"] == "new-od-id"
    assert cfg["google"]["client_id"] == "g-id"  # other keys preserved


def test_save_config_rejects_empty(tmp_path, monkeypatch):
    import api.main as m
    from fastapi import HTTPException
    monkeypatch.setattr(m, "_CONFIG_FILE", tmp_path / "config.json")
    with pytest.raises(HTTPException) as exc_info:
        m.onedrive_save_config(m._OneDriveConfigBody(client_id="  "))
    assert exc_info.value.status_code == 400


def test_disconnect_idempotent(tmp_path, monkeypatch):
    """Disconnect with no cache file should not raise."""
    import api.main as m
    monkeypatch.setattr(m, "_OD_CACHE_FILE", tmp_path / "od.bin")
    result = m.onedrive_disconnect()
    assert result["ok"] is True


def test_disconnect_removes_cache(tmp_path, monkeypatch):
    import api.main as m
    cache_path = tmp_path / "od.bin"
    cache_path.write_bytes(b"fake-token")
    monkeypatch.setattr(m, "_OD_CACHE_FILE", cache_path)
    m.onedrive_disconnect()
    assert not cache_path.exists()


def test_poll_returns_current_state(monkeypatch):
    import api.main as m
    monkeypatch.setattr(m, "_od_auth_result", {"status": "idle"})
    assert m.onedrive_auth_poll()["status"] == "idle"


def test_auth_start_no_client_id(tmp_path, monkeypatch):
    import api.main as m
    from fastapi import HTTPException
    monkeypatch.setattr(m, "_CONFIG_FILE", tmp_path / "config.json")
    with pytest.raises(HTTPException) as exc_info:
        m.onedrive_auth_start()
    assert exc_info.value.status_code == 400


def test_auth_start_msal_not_installed(tmp_path, monkeypatch):
    import api.main as m
    from fastapi import HTTPException
    monkeypatch.setattr(m, "_CONFIG_FILE", tmp_path / "config.json")
    m._save_config({"onedrive": {"client_id": "test-id"}})
    monkeypatch.setattr(m, "_OD_CACHE_FILE", tmp_path / "od.bin")
    with patch.dict("sys.modules", {"msal": None}):
        with pytest.raises(HTTPException) as exc_info:
            m.onedrive_auth_start()
    assert exc_info.value.status_code == 501


# ── _do_scan integration ──────────────────────────────────────────────────────
# _do_scan imports from photo_checker locally (inside the function), so we mock
# the entire photo_checker module via sys.modules rather than api.main attributes.

def _make_fake_jpg(path: Path) -> Path:
    path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    return path


def _status_label(result, skipped):
    """Real status_label logic used in test mocks."""
    if skipped:
        return "skipped"
    if result is None:
        return "error"
    return "yes" if result else "no"


def _mock_pc(img, apple_result=(False, "none", "not found"), od_result=False):
    """Build a MagicMock for the photo_checker module."""
    from unittest.mock import MagicMock
    pc = MagicMock()
    pc.scan_folder.return_value = [img]
    pc.load_apple_photos_filenames.return_value = None
    pc._check_apple_detail.return_value = apple_result
    pc.check_onedrive.return_value = od_result
    pc.status_label.side_effect = _status_label
    return pc


def test_do_scan_onedrive_disabled_records_skipped(tmp_path, monkeypatch):
    """onedrive=False (default) → all records have onedrive='skipped'."""
    import api.main as m
    img = _make_fake_jpg(tmp_path / "test.jpg")
    pc = _mock_pc(img, apple_result=(False, "none", "not found"))

    with (
        patch.dict("sys.modules", {"photo_checker": pc}),
        patch.object(m, "_find_apple_photo", return_value=None),
    ):
        _, results = m._do_scan(tmp_path, recursive=False, onedrive=False)

    assert len(results) == 1
    assert results[0]["onedrive"] == "skipped"
    assert results[0]["apple_photos"] == "no"
    assert results[0]["safe_to_delete"] == "NO"


def test_do_scan_apple_yes_onedrive_disabled(tmp_path):
    """Apple=yes, OneDrive disabled → safe_to_delete=YES (no regression)."""
    import api.main as m
    img = _make_fake_jpg(tmp_path / "in_apple.jpg")
    pc = _mock_pc(img, apple_result=(True, "high", "filename match"))

    with (
        patch.dict("sys.modules", {"photo_checker": pc}),
        patch.object(m, "_find_apple_photo", return_value=None),
    ):
        _, results = m._do_scan(tmp_path, recursive=False, onedrive=False)

    assert results[0]["apple_photos"] == "yes"
    assert results[0]["onedrive"] == "skipped"
    assert results[0]["safe_to_delete"] == "YES"


def test_do_scan_onedrive_enabled_found(tmp_path, monkeypatch):
    """onedrive=True, check_onedrive=True → onedrive=yes, safe_to_delete=YES."""
    import api.main as m
    img = _make_fake_jpg(tmp_path / "backup.jpg")
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"onedrive": {"client_id": "test-id"}}))
    monkeypatch.setattr(m, "_CONFIG_FILE", cfg_file)
    pc = _mock_pc(img, apple_result=(False, "none", "not found"), od_result=True)

    with (
        patch.dict("sys.modules", {"photo_checker": pc}),
        patch.object(m, "_find_apple_photo", return_value=None),
    ):
        _, results = m._do_scan(tmp_path, recursive=False, onedrive=True)

    assert results[0]["onedrive"] == "yes"
    assert results[0]["safe_to_delete"] == "YES"
    assert "onedrive" in results[0]["found_in"]


def test_do_scan_onedrive_enabled_not_found(tmp_path, monkeypatch):
    """onedrive=True, check_onedrive=False → onedrive=no, safe=NO."""
    import api.main as m
    img = _make_fake_jpg(tmp_path / "missing.jpg")
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"onedrive": {"client_id": "test-id"}}))
    monkeypatch.setattr(m, "_CONFIG_FILE", cfg_file)
    pc = _mock_pc(img, apple_result=(False, "none", "not found"), od_result=False)

    with (
        patch.dict("sys.modules", {"photo_checker": pc}),
        patch.object(m, "_find_apple_photo", return_value=None),
    ):
        _, results = m._do_scan(tmp_path, recursive=False, onedrive=True)

    assert results[0]["onedrive"] == "no"
    assert results[0]["safe_to_delete"] == "NO"


def test_do_scan_onedrive_error_with_apple_yes_is_maybe(tmp_path, monkeypatch):
    """Apple=yes, OneDrive enabled but errors → safe=MAYBE (conservative)."""
    import api.main as m
    img = _make_fake_jpg(tmp_path / "err.jpg")
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"onedrive": {"client_id": "test-id"}}))
    monkeypatch.setattr(m, "_CONFIG_FILE", cfg_file)
    pc = _mock_pc(img, apple_result=(True, "high", "filename match"), od_result=None)

    with (
        patch.dict("sys.modules", {"photo_checker": pc}),
        patch.object(m, "_find_apple_photo", return_value=None),
    ):
        _, results = m._do_scan(tmp_path, recursive=False, onedrive=True)

    assert results[0]["apple_photos"] == "yes"
    assert results[0]["onedrive"] == "error"
    assert results[0]["safe_to_delete"] == "MAYBE"


def test_do_scan_apple_yes_onedrive_yes_both_found(tmp_path, monkeypatch):
    """Found in both Apple and OneDrive → found_in lists both, safe=YES."""
    import api.main as m
    img = _make_fake_jpg(tmp_path / "both.jpg")
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"onedrive": {"client_id": "test-id"}}))
    monkeypatch.setattr(m, "_CONFIG_FILE", cfg_file)
    pc = _mock_pc(img, apple_result=(True, "high", "filename match"), od_result=True)

    with (
        patch.dict("sys.modules", {"photo_checker": pc}),
        patch.object(m, "_find_apple_photo", return_value=None),
    ):
        _, results = m._do_scan(tmp_path, recursive=False, onedrive=True)

    assert results[0]["apple_photos"] == "yes"
    assert results[0]["onedrive"] == "yes"
    assert results[0]["safe_to_delete"] == "YES"
    assert "apple_photos" in results[0]["found_in"]
    assert "onedrive" in results[0]["found_in"]
