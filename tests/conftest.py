"""Shared fixtures for photo-checker tests.

No real Apple Photos library required — all fixtures use in-memory sets.
"""
import sys
from pathlib import Path

# Add project root to path so photo_checker and api are importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import unicodedata
import pytest


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


@pytest.fixture
def apple_name_idx():
    """A small set of NFC-lowercased Apple Photos filenames."""
    names = [
        "img_1234.jpg",
        "img_1495.heic",
        "chloé.jpg",          # NFC é
        "photo.jpg",
        "photo - copy.jpg",
        "dsc_0001.nef",
        "2005 family.jpg",
    ]
    return {_nfc(n).lower() for n in names}


@pytest.fixture
def apple_stem_idx(apple_name_idx):
    """Stem set derived from apple_name_idx (no extension)."""
    from pathlib import Path
    return {Path(n).stem for n in apple_name_idx}
