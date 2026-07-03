"""Unit tests for the rclone-based OneDrive integration.

No real OneDrive account or rclone remote is needed — rclone calls are mocked.
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── photo_checker: check_onedrive lookup ──────────────────────────────────────

def test_check_onedrive_hit():
    import photo_checker as pc
    idx = {"img_1234.jpg", "photo.heic"}
    assert pc.check_onedrive("IMG_1234.JPG", idx) is True   # case-insensitive


def test_check_onedrive_miss():
    import photo_checker as pc
    assert pc.check_onedrive("nope.jpg", {"a.jpg"}) is False


def test_check_onedrive_skipped_when_index_none():
    import photo_checker as pc
    assert pc.check_onedrive("x.jpg", None) is None


def test_check_onedrive_nfc_normalization():
    import photo_checker as pc
    # index built from NFC; query decomposed (NFD) accent should still match
    import unicodedata
    idx = {unicodedata.normalize("NFC", "chloé.jpg").lower()}
    nfd_query = unicodedata.normalize("NFD", "Chloé.jpg")
    assert pc.check_onedrive(nfd_query, idx) is True


# ── photo_checker: onedrive_remotes parsing ───────────────────────────────────

def test_onedrive_remotes_filters_by_type(monkeypatch):
    import photo_checker as pc
    monkeypatch.setattr(pc, "rclone_available", lambda: True)
    fake = MagicMock()
    fake.stdout = "onedrive:      onedrive\ngdrive:        drive\nod2:           onedrive\n"
    with patch("subprocess.run", return_value=fake):
        remotes = pc.onedrive_remotes()
    assert remotes == ["onedrive", "od2"]


def test_onedrive_remotes_empty_when_no_rclone(monkeypatch):
    import photo_checker as pc
    monkeypatch.setattr(pc, "rclone_available", lambda: False)
    assert pc.onedrive_remotes() == []


# ── photo_checker: load_onedrive_filenames cache logic ────────────────────────

def test_load_onedrive_none_when_no_rclone(monkeypatch):
    import photo_checker as pc
    monkeypatch.setattr(pc, "rclone_available", lambda: False)
    assert pc.load_onedrive_filenames() is None


def test_load_onedrive_none_when_remote_missing(monkeypatch):
    import photo_checker as pc
    monkeypatch.setattr(pc, "rclone_available", lambda: True)
    monkeypatch.setattr(pc, "onedrive_remotes", lambda: ["other"])
    assert pc.load_onedrive_filenames(remote="onedrive") is None


def test_load_onedrive_uses_fresh_cache(monkeypatch, tmp_path):
    import photo_checker as pc
    from datetime import datetime
    cache = tmp_path / "od.json"
    cache.write_text(json.dumps({
        "fetched_at": datetime.now().isoformat(),
        "remote": "onedrive",
        "filenames": ["a.jpg", "b.heic"],
    }))
    monkeypatch.setattr(pc, "rclone_available", lambda: True)
    monkeypatch.setattr(pc, "onedrive_remotes", lambda: ["onedrive"])
    monkeypatch.setattr(pc, "ONEDRIVE_CACHE_FILE", cache)
    # _fetch must NOT be called when cache is fresh
    called = {"fetch": False}
    def _boom(*a, **k):
        called["fetch"] = True
        return set()
    monkeypatch.setattr(pc, "_fetch_onedrive_filenames", _boom)
    names = pc.load_onedrive_filenames(remote="onedrive")
    assert names == {"a.jpg", "b.heic"}
    assert called["fetch"] is False


def test_load_onedrive_rebuilds_when_stale(monkeypatch, tmp_path):
    import photo_checker as pc
    from datetime import datetime, timedelta
    cache = tmp_path / "od.json"
    old = (datetime.now() - timedelta(hours=48)).isoformat()
    cache.write_text(json.dumps({"fetched_at": old, "remote": "onedrive", "filenames": ["stale.jpg"]}))
    monkeypatch.setattr(pc, "rclone_available", lambda: True)
    monkeypatch.setattr(pc, "onedrive_remotes", lambda: ["onedrive"])
    monkeypatch.setattr(pc, "ONEDRIVE_CACHE_FILE", cache)
    monkeypatch.setattr(pc, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(pc, "_fetch_onedrive_filenames", lambda *a, **k: {"new.jpg"})
    names = pc.load_onedrive_filenames(remote="onedrive")
    assert names == {"new.jpg"}


def test_fetch_onedrive_filenames_takes_basename(monkeypatch):
    import photo_checker as pc

    class _FakeProc:
        returncode = 0
        stdout = iter(["Images/sub/IMG_1.JPG\n", "Docs/report.pdf\n", "top.heic\n"])
        def wait(self):
            self.returncode = 0

    captured = {}
    def _popen(cmd, **kw):
        captured["cmd"] = cmd
        return _FakeProc()

    with patch("subprocess.Popen", side_effect=_popen):
        names = pc._fetch_onedrive_filenames("onedrive")
    assert names == {"img_1.jpg", "report.pdf", "top.heic"}
    assert captured["cmd"][-1] == "onedrive:"          # whole drive


def test_fetch_onedrive_with_subfolder_target(monkeypatch):
    import photo_checker as pc

    class _FakeProc:
        returncode = 0
        stdout = iter(["a.jpg\n"])
        def wait(self):
            self.returncode = 0

    captured = {}
    with patch("subprocess.Popen", side_effect=lambda cmd, **kw: captured.update(cmd=cmd) or _FakeProc()):
        pc._fetch_onedrive_filenames("onedrive", path="Images")
    assert captured["cmd"][-1] == "onedrive:Images"    # scoped to subfolder


def test_load_onedrive_rebuilds_when_path_differs(monkeypatch, tmp_path):
    """A cache built for the whole drive must not be reused when a subfolder is set."""
    import photo_checker as pc
    from datetime import datetime
    cache = tmp_path / "od.json"
    cache.write_text(json.dumps({
        "fetched_at": datetime.now().isoformat(),
        "remote": "onedrive", "path": "", "filenames": ["wholedrive.jpg"],
    }))
    monkeypatch.setattr(pc, "rclone_available", lambda: True)
    monkeypatch.setattr(pc, "onedrive_remotes", lambda: ["onedrive"])
    monkeypatch.setattr(pc, "ONEDRIVE_CACHE_FILE", cache)
    monkeypatch.setattr(pc, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(pc, "_fetch_onedrive_filenames", lambda *a, **k: {"subfolder.jpg"})
    names = pc.load_onedrive_filenames(remote="onedrive", path="Images")
    assert names == {"subfolder.jpg"}    # rebuilt, not the stale whole-drive cache


# ── api endpoints (via direct function calls, no httpx) ───────────────────────

def _fake_pc(remotes=("onedrive",), installed=True):
    m = MagicMock()
    m.rclone_available.return_value = installed
    m.onedrive_remotes.return_value = list(remotes)
    return m


def test_status_rclone_installed_one_remote(tmp_path, monkeypatch):
    import api.main as main
    monkeypatch.setattr(main, "_CONFIG_FILE", tmp_path / "config.json")
    with patch.object(main, "_pc", return_value=_fake_pc(("onedrive",))):
        r = main.onedrive_status()
    assert r["rclone_installed"] is True
    assert r["remotes"] == ["onedrive"]
    assert r["remote"] == "onedrive"      # auto-selected (single remote)
    assert r["configured"] is True


def test_status_rclone_not_installed(tmp_path, monkeypatch):
    import api.main as main
    monkeypatch.setattr(main, "_CONFIG_FILE", tmp_path / "config.json")
    with patch.object(main, "_pc", return_value=_fake_pc(installed=False)):
        r = main.onedrive_status()
    assert r["rclone_installed"] is False
    assert r["remotes"] == []
    assert r["configured"] is False


def test_status_multiple_remotes_none_selected(tmp_path, monkeypatch):
    import api.main as main
    monkeypatch.setattr(main, "_CONFIG_FILE", tmp_path / "config.json")
    with patch.object(main, "_pc", return_value=_fake_pc(("a", "b"))):
        r = main.onedrive_status()
    assert r["remote"] is None            # not auto-selected when ambiguous
    assert r["configured"] is False


def test_save_config_valid_remote(tmp_path, monkeypatch):
    import api.main as main
    monkeypatch.setattr(main, "_CONFIG_FILE", tmp_path / "config.json")
    with patch.object(main, "_pc", return_value=_fake_pc(("onedrive",))):
        main.onedrive_save_config(main._OneDriveConfigBody(remote="onedrive"))
    assert main._load_config()["onedrive"]["remote"] == "onedrive"


def test_save_config_rejects_unknown_remote(tmp_path, monkeypatch):
    import api.main as main
    from fastapi import HTTPException
    monkeypatch.setattr(main, "_CONFIG_FILE", tmp_path / "config.json")
    with patch.object(main, "_pc", return_value=_fake_pc(("onedrive",))):
        with pytest.raises(HTTPException) as exc:
            main.onedrive_save_config(main._OneDriveConfigBody(remote="ghost"))
    assert exc.value.status_code == 400


def test_save_config_rejects_empty(tmp_path, monkeypatch):
    import api.main as main
    from fastapi import HTTPException
    monkeypatch.setattr(main, "_CONFIG_FILE", tmp_path / "config.json")
    with pytest.raises(HTTPException) as exc:
        main.onedrive_save_config(main._OneDriveConfigBody(remote="  "))
    assert exc.value.status_code == 400


# ── _do_scan integration ──────────────────────────────────────────────────────

def _make_fake_jpg(path: Path) -> Path:
    path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    return path


def _mock_pc_module(img, apple_result=(False, "none", "not found"), od_index=None):
    pc = MagicMock()
    pc.scan_folder.return_value = [img]
    pc.load_apple_photos_filenames.return_value = None
    pc._check_apple_detail.return_value = apple_result
    pc.load_onedrive_filenames.return_value = od_index
    pc.check_onedrive.side_effect = lambda name, idx: (
        None if idx is None else (name.lower() in idx)
    )
    pc.status_label.side_effect = lambda result, skipped: (
        "skipped" if skipped else ("error" if result is None else ("yes" if result else "no"))
    )
    return pc


def test_do_scan_onedrive_disabled_skipped(tmp_path):
    import api.main as main
    img = _make_fake_jpg(tmp_path / "a.jpg")
    with (
        patch.dict("sys.modules", {"photo_checker": _mock_pc_module(img)}),
        patch.object(main, "_find_apple_photo", return_value=None),
    ):
        _, results = main._do_scan(tmp_path, recursive=False, onedrive=False)
    assert results[0]["onedrive"] == "skipped"
    assert results[0]["safe_to_delete"] == "NO"


def test_do_scan_onedrive_found(tmp_path, monkeypatch):
    import api.main as main
    img = _make_fake_jpg(tmp_path / "vacation.jpg")
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"onedrive": {"remote": "onedrive"}}))
    monkeypatch.setattr(main, "_CONFIG_FILE", cfg)
    pc = _mock_pc_module(img, od_index={"vacation.jpg"})
    with (
        patch.dict("sys.modules", {"photo_checker": pc}),
        patch.object(main, "_find_apple_photo", return_value=None),
    ):
        _, results = main._do_scan(tmp_path, recursive=False, onedrive=True)
    assert results[0]["onedrive"] == "yes"
    assert results[0]["safe_to_delete"] == "YES"
    assert "onedrive" in results[0]["found_in"]


def test_do_scan_onedrive_not_found(tmp_path, monkeypatch):
    import api.main as main
    img = _make_fake_jpg(tmp_path / "local_only.jpg")
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"onedrive": {"remote": "onedrive"}}))
    monkeypatch.setattr(main, "_CONFIG_FILE", cfg)
    pc = _mock_pc_module(img, od_index={"other.jpg"})
    with (
        patch.dict("sys.modules", {"photo_checker": pc}),
        patch.object(main, "_find_apple_photo", return_value=None),
    ):
        _, results = main._do_scan(tmp_path, recursive=False, onedrive=True)
    assert results[0]["onedrive"] == "no"
    assert results[0]["safe_to_delete"] == "NO"


def test_do_scan_onedrive_index_fails_degrades_to_skipped(tmp_path, monkeypatch):
    """If onedrive requested but index can't be built, degrade to skipped (not MAYBE)."""
    import api.main as main
    img = _make_fake_jpg(tmp_path / "photo.jpg")
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"onedrive": {"remote": "onedrive"}}))
    monkeypatch.setattr(main, "_CONFIG_FILE", cfg)
    # Apple finds it, OneDrive index is None (rclone failed)
    pc = _mock_pc_module(img, apple_result=(True, "high", "match"), od_index=None)
    with (
        patch.dict("sys.modules", {"photo_checker": pc}),
        patch.object(main, "_find_apple_photo", return_value=None),
    ):
        _, results = main._do_scan(tmp_path, recursive=False, onedrive=True)
    assert results[0]["apple_photos"] == "yes"
    assert results[0]["onedrive"] == "skipped"      # degraded, not "error"
    assert results[0]["safe_to_delete"] == "YES"    # not MAYBE


# ── OneDrive upload: helpers ──────────────────────────────────────────────────

def test_unique_dest_name_no_collision():
    import photo_checker as pc
    assert pc._unique_dest_name("new.jpg", {"other.jpg"}) == "new.jpg"


def test_unique_dest_name_collision_suffixes():
    import photo_checker as pc
    taken = {"img_1234.jpg"}
    assert pc._unique_dest_name("IMG_1234.JPG", taken) == "IMG_1234 (2).JPG"
    taken.add("img_1234 (2).jpg")
    assert pc._unique_dest_name("IMG_1234.JPG", taken) == "IMG_1234 (3).JPG"


def test_onedrive_upload_builds_correct_rclone_command():
    import photo_checker as pc
    captured = {}

    class _Proc:
        returncode = 0
        stderr = ""

    def _run(cmd, **kw):
        captured["cmd"] = cmd
        return _Proc()

    with patch("subprocess.run", side_effect=_run):
        pc.onedrive_upload("onedrive", "PhotoChecker", Path("/local/IMG_1.jpg"), "IMG_1.jpg")
    assert captured["cmd"][:2] == ["rclone", "copyto"]
    assert captured["cmd"][2] == "/local/IMG_1.jpg"
    assert captured["cmd"][3] == "onedrive:PhotoChecker/IMG_1.jpg"
    assert "--no-traverse" in captured["cmd"]


def test_onedrive_upload_raises_on_failure():
    import photo_checker as pc

    class _Proc:
        returncode = 1
        stderr = "quota exceeded"

    with patch("subprocess.run", return_value=_Proc()):
        with pytest.raises(RuntimeError, match="quota exceeded"):
            pc.onedrive_upload("onedrive", "PhotoChecker", Path("/x.jpg"), "x.jpg")


# ── OneDrive upload: endpoint patches records ─────────────────────────────────

def test_upload_endpoint_patches_record(tmp_path, monkeypatch):
    """After a successful upload the record flips onedrive->yes, safe_to_delete->YES."""
    import api.main as main
    import asyncio

    # A real local source file (endpoint checks src.is_file())
    src = _make_fake_jpg(tmp_path / "a.jpg")

    # A result file with one photo not in OneDrive
    slug = "T"
    monkeypatch.setattr(main, "RESULTS_DIR", tmp_path)
    (tmp_path / f"{slug}.json").write_text(json.dumps([{
        "filename": "a.jpg", "path": str(src),
        "apple_photos": "no", "google_photos": "skipped", "onedrive": "no",
        "found_in": "—", "safe_to_delete": "NO",
    }]))
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"onedrive": {"remote": "onedrive", "upload_path": "PhotoChecker"}}))
    monkeypatch.setattr(main, "_CONFIG_FILE", cfg)

    fake_pc = MagicMock()
    fake_pc.rclone_available.return_value = True
    fake_pc.onedrive_remotes.return_value = ["onedrive"]
    fake_pc.onedrive_dir_names.return_value = set()
    fake_pc._unique_dest_name.side_effect = lambda name, taken: name
    fake_pc.onedrive_upload.return_value = None

    async def _drain():
        with (
            patch.object(main, "_pc", return_value=fake_pc),
            patch.object(main, "_validate_media_path", return_value=src),
        ):
            resp = await main.onedrive_upload(main._OneDriveUploadBody(paths=[str(src)], slug=slug))
            events = []
            async for chunk in resp.body_iterator:
                for line in chunk.split("\n"):
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))
            return events

    events = asyncio.run(_drain())
    done = [e for e in events if e.get("type") == "done"]
    assert done and done[0]["uploaded"] == [str(src)] and not done[0]["errors"]

    # Record patched on disk
    rec = json.loads((tmp_path / f"{slug}.json").read_text())[0]
    assert rec["onedrive"] == "yes"
    assert rec["safe_to_delete"] == "YES"
    assert "onedrive" in rec["found_in"]


# ── patch-imported (path-based batch persist) ─────────────────────────────────

def test_patch_imported_by_path(tmp_path, monkeypatch):
    import api.main as main
    monkeypatch.setattr(main, "RESULTS_DIR", tmp_path)
    slug = "R"
    (tmp_path / f"{slug}.json").write_text(json.dumps([
        {"filename": "dup.jpg", "path": "/a/dup.jpg", "apple_photos": "no",
         "google_photos": "skipped", "onedrive": "yes", "found_in": "onedrive", "safe_to_delete": "YES"},
        {"filename": "dup.jpg", "path": "/b/dup.jpg", "apple_photos": "no",
         "google_photos": "skipped", "onedrive": "no", "found_in": "—", "safe_to_delete": "NO"},
    ]))
    # Patch only /a/dup.jpg → path-safe (same filename, different folders)
    res = main.patch_imported(main._PatchImportedBody(slug=slug, paths=["/a/dup.jpg"]))
    assert res["patched"] == 1
    recs = json.loads((tmp_path / f"{slug}.json").read_text())
    a = next(r for r in recs if r["path"] == "/a/dup.jpg")
    b = next(r for r in recs if r["path"] == "/b/dup.jpg")
    assert a["apple_photos"] == "yes" and a["safe_to_delete"] == "YES"
    assert "apple_photos" in a["found_in"] and "onedrive" in a["found_in"]
    assert b["apple_photos"] == "no"   # the same-named file in /b was NOT touched


# ── rclone binary resolution + connect endpoint ───────────────────────────────

def test_rclone_bin_dev_uses_path():
    import photo_checker as pc
    assert pc._rclone_bin() == "rclone"   # not frozen → PATH


def test_rclone_bin_frozen_prefers_bundled(monkeypatch, tmp_path):
    import photo_checker as pc
    bundled = tmp_path / "rclone"
    bundled.write_text("")   # pretend the bundled binary exists
    monkeypatch.setattr(pc.sys, "frozen", True, raising=False)
    monkeypatch.setattr(pc.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert pc._rclone_bin() == str(bundled)


def test_connect_no_rclone(monkeypatch):
    import api.main as main
    from fastapi import HTTPException
    fake = MagicMock()
    fake.rclone_available.return_value = False
    with patch.object(main, "_pc", return_value=fake):
        with pytest.raises(HTTPException) as exc:
            main.onedrive_connect()
    assert exc.value.status_code == 400


def test_connect_already_connected(monkeypatch):
    import api.main as main
    fake = MagicMock()
    fake.rclone_available.return_value = True
    fake._rclone_bin.return_value = "rclone"
    fake.onedrive_remotes.return_value = ["onedrive"]   # already there
    with patch.object(main, "_pc", return_value=fake):
        r = main.onedrive_connect()
    assert r["status"] == "already_connected"
