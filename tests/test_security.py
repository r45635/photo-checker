"""Unit tests for security-critical functions in api/main.py."""
import re
import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException


# ── Helpers — import only what can be tested without starting the server ───────

def _get_validate_media_path():
    from api.main import _validate_media_path
    return _validate_media_path


def _get_uuid_re():
    from api.main import _UUID_RE
    return _UUID_RE


def _get_sensitive_prefixes():
    from api.main import _SENSITIVE_PREFIXES
    return _SENSITIVE_PREFIXES


# ── _validate_media_path ───────────────────────────────────────────────────────

class TestValidateMediaPath:
    def test_blocks_etc(self):
        fn = _get_validate_media_path()
        with pytest.raises(HTTPException) as exc:
            fn("/etc/passwd")
        assert exc.value.status_code == 403

    def test_blocks_private_etc(self):
        fn = _get_validate_media_path()
        with pytest.raises(HTTPException) as exc:
            fn("/private/etc/hosts")
        assert exc.value.status_code == 403

    def test_blocks_system(self):
        fn = _get_validate_media_path()
        with pytest.raises(HTTPException) as exc:
            fn("/System/Library/something.png")
        assert exc.value.status_code == 403

    def test_blocks_ssh_dir(self):
        fn = _get_validate_media_path()
        with pytest.raises(HTTPException) as exc:
            fn(str(Path.home() / ".ssh" / "id_rsa"))
        assert exc.value.status_code == 403

    def test_blocks_photo_checker_tokens(self):
        fn = _get_validate_media_path()
        with pytest.raises(HTTPException) as exc:
            fn(str(Path.home() / ".photo_checker" / "tokens" / "google_token.json"))
        assert exc.value.status_code == 403

    def test_blocks_non_media_extension(self):
        fn = _get_validate_media_path()
        with pytest.raises(HTTPException) as exc:
            fn("/Users/user/photos/script.py")
        assert exc.value.status_code == 400

    def test_blocks_dotenv(self):
        fn = _get_validate_media_path()
        with pytest.raises(HTTPException) as exc:
            fn("/Users/user/project/.env")
        assert exc.value.status_code == 400

    def test_allows_jpg(self, tmp_path):
        fn = _get_validate_media_path()
        fake = tmp_path / "photo.jpg"
        fake.touch()
        result = fn(str(fake))
        assert result == fake.resolve()

    def test_allows_heic(self, tmp_path):
        fn = _get_validate_media_path()
        fake = tmp_path / "photo.heic"
        fake.touch()
        result = fn(str(fake))
        assert result.suffix.lower() == ".heic"

    def test_allows_mp4(self, tmp_path):
        fn = _get_validate_media_path()
        fake = tmp_path / "video.mp4"
        fake.touch()
        result = fn(str(fake))
        assert result.suffix.lower() == ".mp4"

    def test_traversal_via_dotdot(self, tmp_path):
        fn = _get_validate_media_path()
        # Attempt traversal: /tmp/photos/../../etc/passwd
        traversal = str(tmp_path / ".." / ".." / "etc" / "passwd")
        with pytest.raises(HTTPException) as exc:
            fn(traversal)
        assert exc.value.status_code in (400, 403)


# ── UUID validation regex ──────────────────────────────────────────────────────

class TestUUIDRegex:
    def test_valid_uuid(self):
        uuid_re = _get_uuid_re()
        assert uuid_re.match("A1B2C3D4-E5F6-7890-ABCD-EF1234567890")

    def test_valid_uuid_lowercase(self):
        uuid_re = _get_uuid_re()
        assert uuid_re.match("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

    def test_rejects_injection_semicolon(self):
        uuid_re = _get_uuid_re()
        assert not uuid_re.match("valid-uuid; rm -rf /")

    def test_rejects_injection_newline(self):
        uuid_re = _get_uuid_re()
        assert not uuid_re.match("A1B2C3D4-E5F6-7890-ABCD-EF1234567890\ntell app")

    def test_rejects_short(self):
        uuid_re = _get_uuid_re()
        assert not uuid_re.match("ABCD-1234")

    def test_rejects_empty(self):
        uuid_re = _get_uuid_re()
        assert not uuid_re.match("")

    def test_rejects_non_hex(self):
        uuid_re = _get_uuid_re()
        assert not uuid_re.match("G1B2C3D4-E5F6-7890-ABCD-EF1234567890")
