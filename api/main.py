#!/usr/bin/env python3
"""
FastAPI backend for the photo deduplication tool.
Wraps photo_checker.py logic and serves a Next.js frontend.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

# ── Paths ───────────────────────────────────────────────────────────────────────

PYTHON      = Path("/Users/vcruvellier/tools/photo_checker/venv/bin/python")
CHECKER     = Path("/Users/vcruvellier/tools/photo_checker/photo_checker.py")
RESULTS_DIR = Path("/Users/vcruvellier/tools/photo_checker/results")

# ── App ─────────────────────────────────────────────────────────────────────────

app = FastAPI(title="photo-checker API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Helpers ─────────────────────────────────────────────────────────────────────

def _slug_from_stem(stem: str) -> str:
    """Return a URL-safe slug from a file stem (already without extension)."""
    return stem


def _stem_from_slug(slug: str) -> str:
    return slug


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


# ── GET /api/results ─────────────────────────────────────────────────────────────

@app.get("/api/results")
def list_results() -> list[dict[str, str]]:
    """Return [{slug, name}] for every JSON file in the results directory."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for p in sorted(RESULTS_DIR.glob("*.json")):
        stem = p.stem
        items.append({"slug": _slug_from_stem(stem), "name": stem})
    return items


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
    file_path = Path(path)
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


_apple_cache: dict | None = None


def _get_apple_cache() -> dict | None:
    """Lazy-load and cache the PhotosDB name+fingerprint indexes."""
    global _apple_cache
    if _apple_cache is not None:
        return _apple_cache
    try:
        import osxphotos
        db = osxphotos.PhotosDB()
        photos = db.photos()
        names: dict = {}
        fingerprints: dict = {}
        for p in photos:
            key = p.original_filename.lower()
            if key not in names:
                names[key] = p
            if p.fingerprint:
                fingerprints[p.fingerprint] = p
        _apple_cache = {"names": names, "fingerprints": fingerprints}
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
    """Return an osxphotos PhotoInfo matching by filename, then SHA1 fingerprint."""
    cache = _get_apple_cache()
    if cache is None:
        return None
    photo = cache["names"].get(filename.lower())
    if photo is not None:
        return photo
    if backup_path:
        try:
            p = Path(backup_path)
            if p.is_file():
                sha1 = _file_sha1(p)
                return cache["fingerprints"].get(sha1)
        except Exception as exc:
            print(f"[apple] fingerprint lookup error for {filename}: {exc}", file=sys.stderr)
    return None


# ── GET /api/apple-info ──────────────────────────────────────────────────────────

@app.get("/api/apple-info")
def get_apple_info(filename: str = Query(...), path: str | None = Query(None)) -> dict[str, Any] | None:
    """Return Apple Photos metadata for a filename, or null if not found."""
    photo = _find_apple_photo(filename, backup_path=path)
    if photo is None:
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

@app.post("/api/scan")
def scan(body: ScanBody) -> dict[str, str]:
    """
    Run photo_checker.py on the given folder and return {slug, output}.
    Always skips Google and OneDrive (Apple-only) to avoid interactive OAuth flows.
    """
    folder = Path(body.folder).expanduser().resolve()
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {folder}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = folder.name
    output_base = str(RESULTS_DIR / slug)

    cmd = [
        str(PYTHON),
        str(CHECKER),
        str(folder),
        "--output", output_base,
        "--skip-google",
        "--skip-onedrive",
    ]
    if body.recursive:
        cmd.append("--recursive")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        combined = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
        if proc.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Scan failed (exit {proc.returncode}):\n{combined}",
            )
        return {"slug": _slug_from_stem(slug), "output": combined}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Scan timed out after 5 minutes")
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[scan] error: {exc}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── POST /api/import ─────────────────────────────────────────────────────────────

@app.post("/api/import")
def import_to_photos(body: ImportBody) -> dict[str, str]:
    """Import a file into Apple Photos via osascript."""
    file_path = Path(body.path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    script = f'tell application "Photos" to import POSIX file "{file_path}"'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"osascript error: {result.stderr.strip()}",
            )
        return {"status": "imported", "path": str(file_path)}
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[import] error: {exc}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
            print(f"[delete] error trashing {p}: {exc}", file=sys.stderr)
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


# ── Entry point ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
