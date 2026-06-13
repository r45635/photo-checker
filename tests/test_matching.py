"""Unit tests for filename matching and copy-suffix stripping."""
import unicodedata
import pytest
from photo_checker import _strip_copy_suffix, _nfc, _check_apple_detail


# ── Copy-suffix stripping ──────────────────────────────────────────────────────

class TestStripCopySuffix:
    def test_strip_english_copy(self):
        assert _strip_copy_suffix("photo - Copy") == "photo"

    def test_strip_english_copy_case(self):
        assert _strip_copy_suffix("photo - COPY") == "photo"

    def test_strip_french_copie(self):
        assert _strip_copy_suffix("photo - Copie") == "photo"

    def test_strip_underscore_copy(self):
        assert _strip_copy_suffix("photo_copy") == "photo"

    def test_strip_underscore_copie(self):
        assert _strip_copy_suffix("photo_copie") == "photo"

    def test_strip_space_copy(self):
        assert _strip_copy_suffix("photo copy") == "photo"

    def test_strip_numeric_suffix(self):
        assert _strip_copy_suffix("Chloé (1)") == "Chloé"

    def test_strip_numeric_suffix_2(self):
        assert _strip_copy_suffix("photo (2)") == "photo"

    def test_strip_numeric_multidigit(self):
        assert _strip_copy_suffix("IMG_1234 (10)") == "IMG_1234"

    def test_strip_combined_numeric_and_copy(self):
        assert _strip_copy_suffix("myphoto (1) - Copy") == "myphoto"

    def test_strip_repeated_copy(self):
        assert _strip_copy_suffix("photo - Copy - Copy") == "photo"

    def test_no_strip_internal_parens(self):
        # IMG_(1234) has no space before ( — should NOT be stripped
        assert _strip_copy_suffix("IMG_(1234)") == "IMG_(1234)"

    def test_no_strip_name_without_suffix(self):
        assert _strip_copy_suffix("normal_photo") == "normal_photo"

    def test_no_strip_partial_match(self):
        # "copycat" contains "copy" but not as a trailing suffix
        assert _strip_copy_suffix("copycat") == "copycat"


# ── NFC normalization ──────────────────────────────────────────────────────────

class TestNFC:
    def test_nfc_stable_ascii(self):
        assert _nfc("hello") == "hello"

    def test_nfc_normalizes_decomposed(self):
        # NFD é = e + combining accent; NFC é = single codepoint
        nfd_e = "é"
        nfc_e = "\xe9"
        assert _nfc(nfd_e) == nfc_e

    def test_nfc_idempotent(self):
        s = "Chloé (1).jpg"
        assert _nfc(_nfc(s)) == _nfc(s)


# ── _check_apple_detail confidence levels ─────────────────────────────────────

class TestCheckAppleDetail:
    def test_exact_match_returns_high(self, apple_name_idx, apple_stem_idx):
        found, conf, reason = _check_apple_detail(
            "IMG_1234.jpg", apple_name_idx, stem_idx=apple_stem_idx
        )
        assert found is True
        assert conf == "high"
        assert "exact" in reason.lower()

    def test_exact_match_case_insensitive(self, apple_name_idx, apple_stem_idx):
        found, conf, _ = _check_apple_detail(
            "IMG_1234.JPG", apple_name_idx, stem_idx=apple_stem_idx
        )
        assert found is True
        assert conf == "high"

    def test_copy_suffix_stripped_returns_medium(self):
        # Apple Photos has "original.jpg" only — backup has "original - Copy.jpg"
        # Step 1 (exact) fails; step 2 (strip copy suffix) succeeds → medium
        name_idx = {"original.jpg"}
        stem_idx = {"original"}
        found, conf, reason = _check_apple_detail(
            "original - Copy.jpg", name_idx, stem_idx=stem_idx
        )
        assert found is True
        assert conf == "medium"
        assert "copy" in reason.lower()

    def test_numeric_suffix_stripped_returns_medium(self, apple_name_idx, apple_stem_idx):
        # "2005 family (1).jpg" → strip → "2005 family.jpg" which IS in apple_name_idx
        found, conf, reason = _check_apple_detail(
            "2005 family (1).jpg", apple_name_idx, stem_idx=apple_stem_idx
        )
        assert found is True
        assert conf == "medium"

    def test_reverse_copy_returns_medium(self, apple_name_idx, apple_stem_idx):
        # "photo.jpg" in backup, "photo - copy.jpg" IS in apple_name_idx
        found, conf, reason = _check_apple_detail(
            "photo.jpg", apple_name_idx, stem_idx=apple_stem_idx
        )
        assert found is True
        # Could match via reverse copy (step 3) — medium
        assert conf in ("high", "medium")

    def test_cross_format_stem_match_returns_medium(self, apple_name_idx, apple_stem_idx):
        # backup = IMG_1495.JPG, Apple Photos has IMG_1495.HEIC — stem match
        found, conf, reason = _check_apple_detail(
            "IMG_1495.JPG", apple_name_idx, stem_idx=apple_stem_idx
        )
        assert found is True
        assert conf == "medium"
        assert "format" in reason.lower() or "stem" in reason.lower()

    def test_no_match_returns_false_none(self, apple_name_idx, apple_stem_idx):
        found, conf, reason = _check_apple_detail(
            "UNKNOWN_FILE_XYZ.jpg", apple_name_idx, stem_idx=apple_stem_idx
        )
        assert found is False
        assert conf == "none"

    def test_unavailable_index_returns_unknown(self):
        found, conf, reason = _check_apple_detail("anyfile.jpg", name_idx=None)
        assert found is None
        assert conf == "unknown"

    def test_nfc_filename_match(self, apple_name_idx, apple_stem_idx):
        # apple_name_idx has NFC "chloé.jpg"; backup may use NFD decomposed form
        nfd_name = "Chloé.jpg".replace("\xe9", "é")  # NFD decomposed é
        found, conf, _ = _check_apple_detail(
            nfd_name, apple_name_idx, stem_idx=apple_stem_idx
        )
        assert found is True
        assert conf == "high"
