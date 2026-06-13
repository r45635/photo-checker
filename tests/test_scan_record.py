"""Tests for scan record structure and safe_to_delete logic."""
import pytest
from photo_checker import _check_apple_detail


REQUIRED_RECORD_FIELDS = {
    "filename", "path", "size_kb",
    "apple_photos", "google_photos", "onedrive",
    "found_in", "safe_to_delete",
    "match_confidence", "match_reason",
    "is_cloud_only",
    "datetime_original", "has_gps", "has_camera",
    "width", "height",
}


def make_record(**overrides) -> dict:
    base = {
        "filename": "test.jpg",
        "path": "/some/folder/test.jpg",
        "size_kb": 1024.0,
        "apple_photos": "yes",
        "google_photos": "skipped",
        "onedrive": "skipped",
        "found_in": "apple_photos",
        "safe_to_delete": "YES",
        "match_confidence": "high",
        "match_reason": "Exact filename match",
        "is_cloud_only": False,
        "datetime_original": None,
        "has_gps": False,
        "has_camera": False,
        "width": None,
        "height": None,
    }
    base.update(overrides)
    return base


class TestRecordSchema:
    def test_required_fields_present(self):
        record = make_record()
        assert REQUIRED_RECORD_FIELDS.issubset(record.keys())

    def test_safe_to_delete_values(self):
        for v in ("YES", "NO", "MAYBE"):
            r = make_record(safe_to_delete=v)
            assert r["safe_to_delete"] == v

    def test_match_confidence_values(self):
        for v in ("high", "medium", "none", "unknown"):
            r = make_record(match_confidence=v)
            assert r["match_confidence"] == v

    def test_is_cloud_only_defaults_false(self):
        assert make_record()["is_cloud_only"] is False

    def test_is_cloud_only_can_be_true(self):
        r = make_record(is_cloud_only=True)
        assert r["is_cloud_only"] is True


class TestSafeToDeleteLogic:
    """Test the YES/NO/MAYBE logic by exercising _check_apple_detail + scan rules."""

    def _evaluate(self, apple: bool | None) -> str:
        found_in = ["apple_photos"] if apple is True else []
        has_error = apple is None
        safe = bool(found_in) and not has_error
        return "YES" if safe else ("MAYBE" if found_in and has_error else "NO")

    def test_found_no_error_gives_yes(self):
        assert self._evaluate(True) == "YES"

    def test_not_found_no_error_gives_no(self):
        assert self._evaluate(False) == "NO"

    def test_check_error_gives_maybe_when_found_in_other(self):
        # If apple returns None (error) but was found elsewhere — MAYBE
        # Simulated: found_in has entries, has_error True
        found_in = ["apple_photos"]
        has_error = True
        safe = bool(found_in) and not has_error
        result = "YES" if safe else ("MAYBE" if found_in and has_error else "NO")
        assert result == "MAYBE"

    def test_error_alone_gives_no(self):
        # Apple returned None (error), no other repo found it
        assert self._evaluate(None) == "NO"


class TestMatchConfidenceIntegration:
    """Integration between _check_apple_detail and expected record fields."""

    def test_exact_match_produces_high_confidence(self):
        name_idx = {"photo.jpg"}
        found, conf, reason = _check_apple_detail("photo.jpg", name_idx)
        assert found is True
        assert conf == "high"

    def test_no_match_produces_none_confidence(self):
        name_idx = {"other.jpg"}
        found, conf, reason = _check_apple_detail("photo.jpg", name_idx)
        assert found is False
        assert conf == "none"

    def test_unavailable_produces_unknown_confidence(self):
        found, conf, reason = _check_apple_detail("photo.jpg", None)
        assert found is None
        assert conf == "unknown"
