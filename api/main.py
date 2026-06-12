#!/usr/bin/env python3
"""
FastAPI backend for the photo deduplication tool.
Wraps photo_checker.py logic and serves a Next.js frontend.
"""

from __future__ import annotations

import collections
import datetime
import io
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


_COPY_SUFFIX_RE = re.compile(
    r'(\s*-\s*copi[ey]|\s+copi[ey]|_copi[ey]|\s*-\s*copy|\s+copy|_copy)+$',
    re.IGNORECASE,
)

def _strip_copy_suffix(stem: str) -> str:
    return _COPY_SUFFIX_RE.sub('', stem)

_UUID_RE = re.compile(
    r'^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$'
)

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Paths (portable: works both in dev and when packaged with PyInstaller) ───────

_FROZEN = getattr(sys, "frozen", False)
# When frozen: sys._MEIPASS is the temp bundle dir; use home for writable data.
_BUNDLE_DIR = Path(sys._MEIPASS) if _FROZEN else Path(__file__).parent.parent  # type: ignore[attr-defined]
_DATA_DIR   = Path.home() / ".photo_checker" if _FROZEN else _BUNDLE_DIR

# photo_checker.py is imported directly (see _do_scan); these are dev-only fallbacks.
RESULTS_DIR = _DATA_DIR / "results"
STATIC_DIR  = _BUNDLE_DIR / "web" / "out"

# ── In-memory log buffer ────────────────────────────────────────────────────────

import threading as _threading

_LOG_LOCK = _threading.Lock()
_LOG_BUFFER: collections.deque = collections.deque(maxlen=500)


def _log(level: str, msg: str) -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {level:5s} {msg}"
    with _LOG_LOCK:
        _LOG_BUFFER.append(line)
    print(line, file=sys.stderr)


class _LogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _log(record.levelname[:5], self.format(record))


logging.getLogger().addHandler(_LogHandler())


# ── App ─────────────────────────────────────────────────────────────────────────

app = FastAPI(title="photo-checker API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)

# ── Helpers ─────────────────────────────────────────────────────────────────────

def _slug_from_stem(stem: str) -> str:
    """Return a URL-safe slug from a file stem (already without extension)."""
    return stem


def _stem_from_slug(slug: str) -> str:
    return slug


def _meta_file(slug: str) -> Path:
    return RESULTS_DIR / f"{_stem_from_slug(slug)}-meta.json"


def _load_scan_meta(slug: str) -> dict[str, Any]:
    p = _meta_file(slug)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_scan_meta(slug: str, scan_folder: str) -> None:
    meta = {
        "scan_folder": scan_folder,
        "scan_date": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    _meta_file(slug).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def _slug_for_folder(folder: str) -> str | None:
    """Return the slug of any existing result that was scanned from `folder`, or None."""
    for p in RESULTS_DIR.glob("*-meta.json"):
        try:
            meta = json.loads(p.read_text(encoding="utf-8"))
            if meta.get("scan_folder") == folder:
                stem = p.name[: -len("-meta.json")]
                return _slug_from_stem(stem)
        except Exception:
            pass
    return None


def _load_result_file(slug: str) -> list[dict[str, Any]]:
    path = RESULTS_DIR / f"{_stem_from_slug(slug)}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Result not found: {slug}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Malformed JSON: {exc}") from exc


def _save_result_file(slug: str, records: list[dict[str, Any]]) -> None:
    path = RESULTS_DIR / f"{_stem_from_slug(slug)}.json"
    path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


_SENSITIVE_PREFIXES = (
    "/etc", "/private/etc", "/System", "/usr/", "/bin/", "/sbin/",
    str(Path.home() / ".ssh"),
    str(Path.home() / ".photo_checker" / "tokens"),
)

_ALLOWED_MEDIA_EXTS = {
    ".jpg", ".jpeg", ".png", ".heic", ".heif", ".gif", ".tiff", ".tif",
    ".bmp", ".webp", ".raw", ".arw", ".cr2", ".nef", ".dng", ".orf", ".rw2",
    ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm",
}


def _validate_media_path(path: str) -> Path:
    """Guard thumbnail/video endpoints against path traversal."""
    p = Path(path).resolve()
    ps = str(p)
    for prefix in _SENSITIVE_PREFIXES:
        if ps.startswith(prefix):
            raise HTTPException(status_code=403, detail="Access denied")
    if p.suffix.lower() not in _ALLOWED_MEDIA_EXTS:
        raise HTTPException(status_code=400, detail="File type not allowed")
    return p


def _compute_subfolders(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Add _subfolder to every record: the portion of the file's parent path
    that is relative to the common root of all paths in the result set.
    """
    paths = [Path(r["path"]) for r in records if r.get("path")]
    if not paths:
        for r in records:
            r["_subfolder"] = ""
        return records

    # Common path of all file parents
    try:
        common = Path(os.path.commonpath([str(p.parent) for p in paths]))
    except ValueError:
        common = paths[0].parent

    out = []
    for r in records:
        p = Path(r["path"])
        try:
            rel = p.parent.relative_to(common)
            subfolder = str(rel) if str(rel) != "." else ""
        except ValueError:
            subfolder = str(p.parent)
        out.append({**r, "_subfolder": subfolder})
    return out


# ── Pydantic models ──────────────────────────────────────────────────────────────

class ScanBody(BaseModel):
    folder: str
    recursive: bool = False


class ImportBody(BaseModel):
    path: str


class PatchBody(BaseModel):
    slug: str
    filename: str


class DeleteBody(BaseModel):
    paths: list[str]
    slug: str


class MoveBody(BaseModel):
    paths: list[str]
    dest: str
    slug: str


class OpenFinderBody(BaseModel):
    path: str


class OpenPhotosBody(BaseModel):
    uuid: str


# ── GET /api/logs ────────────────────────────────────────────────────────────────

@app.get("/api/logs")
def get_logs(n: int = Query(default=200, ge=1, le=500)) -> list[str]:
    """Return the last n server log lines (newest last)."""
    with _LOG_LOCK:
        lines = list(_LOG_BUFFER)
    return lines[-n:]


# ── GET /api/results ─────────────────────────────────────────────────────────────

@app.get("/api/results")
def list_results() -> list[dict[str, Any]]:
    """Return result metadata for every JSON file in the results directory."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for p in sorted(RESULTS_DIR.glob("*.json"), reverse=True):
        stem = p.stem
        if stem.endswith("-meta"):
            continue
        mtime = p.stat().st_mtime
        folder = ""
        scan_date = ""
        total = yes = no = maybe = 0
        size_yes_mb = 0.0
        try:
            meta = _load_scan_meta(stem)
            if meta.get("scan_folder"):
                folder = meta["scan_folder"]
                scan_date = meta.get("scan_date", "")
            records = json.loads(p.read_text(encoding="utf-8"))
            if not folder:
                paths = [r["path"] for r in records if r.get("path")]
                if paths:
                    try:
                        common = os.path.commonpath(paths)
                        folder = common if os.path.isdir(common) else str(Path(common).parent)
                    except (ValueError, OSError):
                        folder = str(Path(paths[0]).parent)
            total = len(records)
            for r in records:
                s = r.get("safe_to_delete", "NO")
                if s == "YES":
                    yes += 1
                    size_yes_mb += r.get("size_kb", 0) / 1024
                elif s == "MAYBE":
                    maybe += 1
                else:
                    no += 1
        except Exception:
            pass
        items.append({
            "slug": _slug_from_stem(stem),
            "name": stem,
            "mtime": mtime,
            "scan_date": scan_date,
            "folder": folder,
            "total": total,
            "yes": yes,
            "no": no,
            "maybe": maybe,
            "size_yes_mb": round(size_yes_mb, 1),
        })
    return items


# ── DELETE /api/results/{slug} ───────────────────────────────────────────────────

@app.delete("/api/results/{slug}")
def delete_result(slug: str) -> dict[str, str]:
    """Delete a result JSON file and its companion metadata file."""
    path = RESULTS_DIR / f"{_stem_from_slug(slug)}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Result not found: {slug}")
    path.unlink()
    meta = _meta_file(slug)
    if meta.exists():
        meta.unlink()
    return {"status": "deleted", "slug": slug}


# ── GET /api/results/{slug} ──────────────────────────────────────────────────────

@app.get("/api/results/{slug}")
def get_result(slug: str) -> list[dict[str, Any]]:
    """Return the records from a result JSON file with _subfolder computed."""
    records = _load_result_file(slug)
    return _compute_subfolders(records)


# ── GET /api/thumbnail ───────────────────────────────────────────────────────────

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v"}


@app.get("/api/thumbnail")
def get_thumbnail(path: str = Query(...), size: int = Query(400)) -> Response:
    """
    Generate and return a JPEG thumbnail for the given file path.
    Uses Pillow (+pillow-heif) for images, qlmanage for videos.
    """
    file_path = _validate_media_path(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    ext = file_path.suffix.lower()
    jpeg_bytes: bytes | None = None

    if ext in VIDEO_EXTENSIONS:
        jpeg_bytes = _video_thumbnail(file_path, size)
    else:
        jpeg_bytes = _image_thumbnail(file_path, size)

    if jpeg_bytes is None:
        raise HTTPException(status_code=500, detail="Failed to generate thumbnail")

    return Response(
        content=jpeg_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


def _image_thumbnail(file_path: Path, size: int) -> bytes | None:
    try:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass

        from PIL import Image

        with Image.open(file_path) as img:
            img = img.convert("RGB")
            img.thumbnail((size, size))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85, optimize=True)
            return buf.getvalue()
    except Exception as exc:
        print(f"[thumbnail] image error for {file_path}: {exc}", file=sys.stderr)
        return None


def _video_thumbnail(file_path: Path, size: int) -> bytes | None:
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ["qlmanage", "-t", "-s", str(size), "-o", tmpdir, str(file_path)],
                capture_output=True,
                timeout=10,
            )
            # qlmanage writes <filename>.png into the output dir
            candidates = list(Path(tmpdir).glob("*.png")) + list(Path(tmpdir).glob("*.jpg"))
            if not candidates:
                print(
                    f"[thumbnail] qlmanage produced no output for {file_path}: "
                    f"{result.stderr.decode(errors='replace')}",
                    file=sys.stderr,
                )
                return None

            from PIL import Image

            with Image.open(candidates[0]) as img:
                img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85, optimize=True)
                return buf.getvalue()
    except Exception as exc:
        print(f"[thumbnail] video error for {file_path}: {exc}", file=sys.stderr)
        return None


# ── GET /api/video ───────────────────────────────────────────────────────────────

VIDEO_MIME: dict[str, str] = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".m4v": "video/x-m4v",
}


@app.get("/api/video")
def stream_video(path: str = Query(...)) -> FileResponse:
    """Stream a video file directly so the browser can play it."""
    file_path = _validate_media_path(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    ext = file_path.suffix.lower()
    media_type = VIDEO_MIME.get(ext, "video/mp4")
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        headers={"Accept-Ranges": "bytes"},
    )


# ── GET /api/apple-thumbnail ─────────────────────────────────────────────────────

@app.get("/api/apple-thumbnail")
def get_apple_thumbnail(filename: str = Query(...), size: int = Query(400), path: str | None = Query(None)) -> Response:
    """Return a JPEG thumbnail sourced from the Apple Photos library."""
    photo = _find_apple_photo(filename, backup_path=path)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found in Apple Photos library")

    # Prefer derivative files (pre-cached JPEG previews, much smaller/faster than originals).
    # Fall back to the original only when no derivative is locally available.
    source_path: str | None = None
    is_video = False
    try:
        for deriv in photo.path_derivatives or []:
            if deriv and Path(deriv).exists():
                source_path = deriv
                break
    except Exception:
        pass

    if not source_path:
        try:
            orig = photo.path
            if orig and Path(orig).exists():
                source_path = orig
                is_video = Path(orig).suffix.lower() in VIDEO_EXTENSIONS
        except Exception:
            pass

    if not source_path:
        raise HTTPException(status_code=404, detail="No local copy available for this photo")

    if is_video:
        jpeg_bytes = _video_thumbnail(Path(source_path), size)
    else:
        jpeg_bytes = _image_thumbnail(Path(source_path), size)

    if jpeg_bytes is None:
        raise HTTPException(status_code=500, detail="Failed to generate thumbnail")

    return Response(
        content=jpeg_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=3600"},
    )


def _photos_library_path() -> Path | None:
    db = Path.home() / "Pictures" / "Photos Library.photoslibrary" / "database" / "Photos.sqlite"
    return db if db.exists() else None


def _check_photos_permission() -> str:
    """Returns 'ok', 'no_library', or 'permission_denied'."""
    db = _photos_library_path()
    if db is None:
        return "no_library"
    try:
        import sqlite3
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        con.execute("SELECT 1")
        con.close()
        return "ok"
    except Exception:
        return "permission_denied"


_apple_cache: dict | None = None
_sqlite_apple_names: set | None = None
_sqlite_apple_stems: set | None = None


def _load_sqlite_apple_names() -> tuple[set, set]:
    """Direct SQLite name+stem sets — same source as the scan. Cached per server lifetime."""
    global _sqlite_apple_names, _sqlite_apple_stems
    if _sqlite_apple_names is not None and _sqlite_apple_stems is not None:
        return _sqlite_apple_names, _sqlite_apple_stems
    _pc_dir = str(_BUNDLE_DIR)
    if _pc_dir not in sys.path:
        sys.path.insert(0, _pc_dir)
    try:
        from photo_checker import load_apple_photos_filenames as _load_afn
        result = _load_afn()
        _sqlite_apple_names = result[0] if result else set()
        _sqlite_apple_stems = result[2] if result else set()
    except Exception as exc:
        print(f"[apple] sqlite names load error: {exc}", file=sys.stderr)
        _sqlite_apple_names = set()
        _sqlite_apple_stems = set()
    return _sqlite_apple_names, _sqlite_apple_stems


def _sqlite_name_found(filename: str) -> bool:
    """Check filename against the direct SQLite index (steps 1-4 of check_apple)."""
    names, stems = _load_sqlite_apple_names()
    if not names:
        return False
    p = Path(filename)
    if _nfc(filename).lower() in names:
        return True
    stem_stripped = _strip_copy_suffix(p.stem)
    if stem_stripped != p.stem and _nfc(stem_stripped + p.suffix).lower() in names:
        return True
    if _nfc(p.stem + " - Copy" + p.suffix).lower() in names:
        return True
    if _nfc(p.stem).lower() in stems:
        return True
    return False


def _get_apple_cache() -> dict | None:
    """Lazy-load and cache the PhotosDB name+fingerprint+uuid indexes."""
    global _apple_cache
    if _apple_cache is not None:
        return _apple_cache
    try:
        import osxphotos
        db = osxphotos.PhotosDB()
        photos = db.photos()
        names: dict = {}
        fingerprints: dict = {}
        uuids: dict = {}
        for p in photos:
            key = _nfc(p.original_filename).lower()
            if key not in names:
                names[key] = p
            if p.fingerprint:
                fingerprints[p.fingerprint] = p
            uuids[p.uuid] = p
        _apple_cache = {"names": names, "fingerprints": fingerprints, "uuids": uuids}
        return _apple_cache
    except Exception as exc:
        print(f"[apple] cache build error: {exc}", file=sys.stderr)
        return None


def _file_sha1(path: Path) -> str:
    import hashlib
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_apple_photo(filename: str, backup_path: str | None = None):
    """Return an osxphotos PhotoInfo matching by filename, osxphotos fingerprint,
    or direct SHA1 comparison against the Apple Photos originals folder."""
    cache = _get_apple_cache()
    if cache is None:
        return None
    # 1. Exact name match
    photo = cache["names"].get(_nfc(filename).lower())
    if photo is not None:
        return photo
    # 2. Strip " - Copy" suffix
    p = Path(filename)
    stem_stripped = _strip_copy_suffix(p.stem)
    if stem_stripped != p.stem:
        photo = cache["names"].get(_nfc(stem_stripped + p.suffix).lower())
        if photo is not None:
            return photo
    # 3. Add " - Copy" suffix
    copy_alt = _nfc(p.stem + " - Copy" + p.suffix).lower()
    photo = cache["names"].get(copy_alt)
    if photo is not None:
        return photo
    if not backup_path:
        return None
    bp = Path(backup_path)
    if not bp.is_file():
        return None
    # 4. osxphotos fingerprint hash
    try:
        backup_sha1 = _file_sha1(bp)
        photo = cache["fingerprints"].get(backup_sha1)
        if photo is not None:
            return photo
    except Exception as exc:
        print(f"[apple] fingerprint lookup error for {filename}: {exc}", file=sys.stderr)
        return None
    # 5. Direct SHA1 against originals folder (same as check_apple step 4 in scan)
    try:
        import sqlite3
        db_path = _photos_library_path()
        if db_path is None:
            return None
        size = bp.stat().st_size
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = con.cursor()
        cur.execute("""
            SELECT a.ZUUID, a.ZFILENAME
            FROM   ZASSET a
            JOIN   ZADDITIONALASSETATTRIBUTES aa ON aa.ZASSET = a.Z_PK
            WHERE  a.ZTRASHEDSTATE = 0
              AND  aa.ZORIGINALFILESIZE = ?
        """, (size,))
        rows = cur.fetchall()
        con.close()
        originals = db_path.parent.parent / "originals"
        for uuid, zfilename in rows:
            if not uuid or not zfilename:
                continue
            lib_file = originals / uuid[0] / f"{uuid}{Path(zfilename).suffix}"
            if lib_file.exists() and _file_sha1(lib_file) == backup_sha1:
                return cache["uuids"].get(uuid)
    except Exception as exc:
        print(f"[apple] SHA1 originals lookup error for {filename}: {exc}", file=sys.stderr)
    return None


# ── GET /api/apple-info ──────────────────────────────────────────────────────────

@app.get("/api/apple-info")
def get_apple_info(filename: str = Query(...), path: str | None = Query(None)) -> dict[str, Any] | None:
    """Return Apple Photos metadata for a filename, or null if not found."""
    photo = _find_apple_photo(filename, backup_path=path)
    if photo is None:
        # osxphotos missed it — fall back to the same direct SQLite check the scan uses
        if _sqlite_name_found(filename):
            return {
                "uuid": None, "date": None, "albums": [], "keywords": [],
                "favorite": False, "ismissing": False, "iscloudasset": False,
                "has_local_copy": False,
            }
        return None
    try:
        return {
            "uuid":            photo.uuid,
            "date":            photo.date.isoformat() if photo.date else None,
            "albums":          [a.title for a in (photo.album_info or [])],
            "keywords":        list(photo.keywords or []),
            "favorite":        bool(photo.favorite),
            "ismissing":       bool(photo.ismissing),
            "iscloudasset":    bool(photo.iscloudasset),
            "has_local_copy":  bool(photo.path and Path(photo.path).exists()),
        }
    except Exception as exc:
        print(f"[apple-info] metadata error for {filename}: {exc}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── POST /api/scan ───────────────────────────────────────────────────────────────

def _do_scan(folder: Path, recursive: bool, on_progress=None) -> tuple[str, list[dict]]:
    """Run the Apple-Photos check in-process and return (log_output, results)."""
    # Import photo_checker from sibling directory (works in dev and when bundled)
    _pc_dir = str(_BUNDLE_DIR)
    if _pc_dir not in sys.path:
        sys.path.insert(0, _pc_dir)

    import io as _io
    import contextlib
    from photo_checker import (
        scan_folder as _scan_folder,
        load_apple_photos_filenames,
        check_apple,
        status_label,
    )

    log = _io.StringIO()
    with contextlib.redirect_stdout(log):
        photos = _scan_folder(folder, recursive=recursive)
        if not photos:
            return f"No photos found in {folder}", []

        print(f"\nFound {len(photos):,} photos in {folder}\n")
        apple_result  = load_apple_photos_filenames()
        apple_names   = apple_result[0] if apple_result else None
        apple_sizes   = apple_result[1] if apple_result else None
        apple_stems   = apple_result[2] if apple_result else None
        print()

        if on_progress:
            on_progress(0, len(photos), "Loading Apple Photos database…")

        results = []
        for i, photo in enumerate(photos, 1):
            apple = check_apple(photo.name, apple_names, apple_sizes, photo, apple_stems)
            found_in = ["apple_photos"] if apple is True else []
            has_error = apple is None
            safe = bool(found_in) and not has_error
            results.append({
                "filename":       photo.name,
                "path":           str(photo),
                "size_kb":        round(photo.stat().st_size / 1024, 1),
                "apple_photos":   status_label(apple, False),
                "google_photos":  "skipped",
                "onedrive":       "skipped",
                "found_in":       ", ".join(found_in) if found_in else "—",
                "safe_to_delete": "YES" if safe else ("MAYBE" if found_in and has_error else "NO"),
            })
            icon = "OK" if safe else ("?" if found_in and has_error else "NO")
            print(f"[{i:>4}/{len(photos)}] [{icon}] {photo.name}")
            if on_progress:
                on_progress(i, len(photos), photo.name)

    return log.getvalue(), results


@app.post("/api/scan")
async def scan(body: ScanBody) -> StreamingResponse:
    """Scan a folder, streaming SSE progress events then a done/error event."""
    import asyncio
    import queue as _queue
    import threading

    folder = Path(body.folder).expanduser().resolve()
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {folder}")

    perm = _check_photos_permission()
    if perm == "permission_denied":
        raise HTTPException(
            status_code=403,
            detail=(
                "Full Disk Access required. Open System Settings → Privacy & Security → "
                "Full Disk Access, add this app, then restart it."
            ),
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    folder_str = str(folder)
    existing_slug = _slug_for_folder(folder_str)
    slug = existing_slug if existing_slug else folder.name
    q: _queue.Queue = _queue.Queue()

    def _run() -> None:
        try:
            def _progress(current: int, total: int, filename: str) -> None:
                q.put({"type": "progress", "current": current, "total": total, "file": filename})

            log, results = _do_scan(folder, body.recursive, on_progress=_progress)
            if not results:
                q.put({"type": "error", "detail": f"No photos found in {folder}"})
                return
            json_path = RESULTS_DIR / f"{slug}.json"
            json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
            _save_scan_meta(slug, folder_str)
            q.put({"type": "done", "slug": _slug_from_stem(slug), "output": log})
        except Exception as exc:
            _log("ERROR", f"scan failed: {exc}")
            q.put({"type": "error", "detail": str(exc)})

    threading.Thread(target=_run, daemon=True).start()

    async def _generate():
        loop = asyncio.get_event_loop()
        while True:
            try:
                item = await loop.run_in_executor(None, q.get, True, 1.0)
                yield f"data: {json.dumps(item)}\n\n"
                if item["type"] in ("done", "error"):
                    break
            except _queue.Empty:
                yield 'data: {"type":"ping"}\n\n'

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ── POST /api/import ─────────────────────────────────────────────────────────────

@app.post("/api/import")
async def import_to_photos(body: ImportBody) -> dict[str, str]:
    """Import a file into Apple Photos via osascript.

    Uses 'skip check duplicates true' so Photos never shows a blocking
    dialog when the image is already in the library.
    """
    import asyncio

    file_path = Path(body.path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Escape double-quotes in path (edge case for filenames with quotes)
    escaped = str(file_path).replace('"', '\\"')
    script = (
        f'tell application "Photos" to import '
        f'{{POSIX file "{escaped}"}} skip check duplicates true'
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        except asyncio.TimeoutError:
            proc.kill()
            raise HTTPException(
                status_code=504,
                detail="Photos did not respond within 60 s — make sure Photos.app is running.",
            )
        if proc.returncode != 0:
            err = stderr.decode().strip()
            raise HTTPException(status_code=500, detail=f"Photos import failed: {err}")
        result = stdout.decode().strip()
        global _apple_cache, _sqlite_apple_names, _sqlite_apple_stems
        _apple_cache = None
        _sqlite_apple_names = None
        _sqlite_apple_stems = None
        if not result:
            # Empty stdout = Photos recognised this as a duplicate and silently
            # skipped it (skip check duplicates true).  The file IS already in
            # the library — treat this as a successful import.
            _log("INFO", f"import already_in_photos (duplicate detected by Photos): {file_path.name}")
            return {"status": "already_in_photos", "path": str(file_path), "result": ""}
        _log("INFO", f"import ok: {file_path.name}")
        return {"status": "imported", "path": str(file_path), "result": result}
    except HTTPException:
        raise
    except Exception as exc:
        _log("ERROR", f"import failed for {file_path.name}: {exc}")
        raise HTTPException(status_code=500, detail="Import failed — check server logs.") from exc


# ── POST /api/patch ──────────────────────────────────────────────────────────────

@app.post("/api/patch")
def patch_record(body: PatchBody) -> dict[str, str]:
    """
    Update a record in a result JSON so apple_photos='yes' and
    safe_to_delete='YES', then persist the file.
    """
    records = _load_result_file(body.slug)
    matched = False
    for rec in records:
        if rec.get("filename") == body.filename:
            rec["apple_photos"] = "yes"
            # Recompute found_in
            repos = []
            for field in ("apple_photos", "google_photos", "onedrive"):
                if rec.get(field) == "yes":
                    repos.append(field)
            rec["found_in"] = ", ".join(repos) if repos else "—"
            # Only set YES if there are no errors
            has_error = any(
                rec.get(f) == "error"
                for f in ("apple_photos", "google_photos", "onedrive")
            )
            if repos and not has_error:
                rec["safe_to_delete"] = "YES"
            elif repos:
                rec["safe_to_delete"] = "MAYBE"
            matched = True
            break

    if not matched:
        raise HTTPException(status_code=404, detail=f"Filename not found: {body.filename}")

    _save_result_file(body.slug, records)
    return {"status": "patched", "filename": body.filename}


# ── POST /api/delete ─────────────────────────────────────────────────────────────

@app.post("/api/delete")
def delete_files(body: DeleteBody) -> dict[str, Any]:
    """Move each path to the system trash and remove records from the JSON."""
    try:
        from send2trash import send2trash
        use_trash = True
    except ImportError:
        use_trash = False

    records = _load_result_file(body.slug)
    paths_set = set(body.paths)
    deleted: list[str] = []
    errors: list[dict[str, str]] = []

    for p_str in body.paths:
        p = Path(p_str)
        if not p.exists():
            errors.append({"path": p_str, "error": "File not found"})
            continue
        try:
            if use_trash:
                send2trash(str(p))
            else:
                # Fallback: move to a sibling trash folder
                from datetime import datetime
                backup_dir = p.parent.parent / f"_photo_checker_trash_{datetime.now():%Y%m%d_%H%M%S}"
                backup_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), backup_dir / p.name)
            deleted.append(p_str)
        except Exception as exc:
            _log("ERROR", f"trash failed for {p.name}: {exc}")
            errors.append({"path": p_str, "error": str(exc)})

    # Remove successfully deleted records from JSON
    remaining = [r for r in records if r.get("path") not in set(deleted)]
    _save_result_file(body.slug, remaining)

    return {"deleted": deleted, "errors": errors}


# ── POST /api/move ───────────────────────────────────────────────────────────────

@app.post("/api/move")
def move_files(body: MoveBody) -> dict[str, Any]:
    """Move each path to dest folder and remove records from the JSON."""
    dest = Path(body.dest).expanduser()
    dest.mkdir(parents=True, exist_ok=True)

    records = _load_result_file(body.slug)
    moved: list[str] = []
    errors: list[dict[str, str]] = []

    for p_str in body.paths:
        p = Path(p_str)
        if not p.exists():
            errors.append({"path": p_str, "error": "File not found"})
            continue
        try:
            shutil.move(str(p), dest / p.name)
            moved.append(p_str)
        except Exception as exc:
            print(f"[move] error moving {p}: {exc}", file=sys.stderr)
            errors.append({"path": p_str, "error": str(exc)})

    remaining = [r for r in records if r.get("path") not in set(moved)]
    _save_result_file(body.slug, remaining)

    return {"moved": moved, "errors": errors, "dest": str(dest)}


# ── POST /api/open-finder ─────────────────────────────────────────────────────────

@app.post("/api/open-finder")
def open_finder(body: OpenFinderBody) -> dict[str, str]:
    """Open the file's containing folder in Finder and select the file."""
    p = Path(body.path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        # -R reveals and selects the file in Finder
        subprocess.run(["open", "-R", str(p)], check=True, timeout=10)
        return {"status": "opened", "path": str(p)}
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── POST /api/open-photos ─────────────────────────────────────────────────────────

@app.post("/api/open-photos")
def open_photos(body: OpenPhotosBody) -> dict[str, str]:
    """Spotlight a photo in Apple Photos by UUID via osascript."""
    if not _UUID_RE.match(body.uuid):
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    script = (
        f'tell application "Photos"\n'
        f'    activate\n'
        f'    spotlight media item id "{body.uuid}"\n'
        f'end tell'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"osascript error: {result.stderr.strip()}",
            )
        return {"status": "opened", "uuid": body.uuid}
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[open-photos] error: {exc}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── GET /api/pick-folder ─────────────────────────────────────────────────────────

@app.get("/api/pick-folder")
def pick_folder() -> dict[str, str]:
    """Open native macOS folder chooser via osascript. Returns {path}."""
    try:
        result = subprocess.run(
            ["osascript", "-e",
             'POSIX path of (choose folder with prompt "Select folder to scan")'],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            return {"path": ""}
        return {"path": result.stdout.strip().rstrip("/")}
    except Exception:
        return {"path": ""}


# ── Static frontend (served when web/out/ exists — production bundle) ────────────

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

# ── Entry point ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import threading, webbrowser, time as _time

    def _open_browser():
        _time.sleep(1.5)
        webbrowser.open("http://localhost:8000")

    if STATIC_DIR.exists():
        # Production mode: serve everything from port 8000, open browser
        threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000)
