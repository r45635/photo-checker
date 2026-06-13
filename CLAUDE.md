# photo-checker — Claude Code context

## What this project is

A macOS web app (FastAPI + Next.js 14) that scans a local folder of photos and checks, by filename, whether each file already exists in one or more cloud/local repositories:
- **Apple Photos** — reads the Photos SQLite library directly via `osxphotos` (no API, no network). Fully working.
- **Google Photos** — REST API backend exists; UI integration in progress.
- **OneDrive** — Graph API backend exists; UI integration in progress.

The goal: help the user decide which local backup files are safe to delete because they are already stored elsewhere.

## Current state (web UI, Apple Photos fully functional)

- FastAPI backend (`api/main.py`) + Next.js 14 static frontend (`web/`)
- Matching is **filename-based** with cross-format stem fallback and copy-suffix stripping
- Apple Photos tested on 37 000+ item library, 1 600-file scan folder
- Google Photos and OneDrive backends exist but are not wired to the UI

## Repository

- GitHub: https://github.com/r45635/photo-checker (private)
- Local: `<wherever you cloned it>/photo_checker/`

## macOS setup prerequisites

### Full Disk Access (required for Apple Photos)

`osxphotos` reads the Photos SQLite database directly. macOS blocks this unless the terminal running the script has **Full Disk Access**:

The app that needs Full Disk Access is whichever process spawns the shell running the script:

| How you run the script | App to grant access to |
|---|---|
| From Terminal.app / iTerm2 | Terminal.app / iTerm2 |
| Via Claude Code in VS Code | **Visual Studio Code** (Code.app) |
| Via Claude desktop app | Claude.app |

Steps:
1. **System Settings → Privacy & Security → Full Disk Access**
2. Add the correct app (see table above)
3. Restart the app

Without this, every file will show `apple_photos: error` and the run is useless.
Photos.app does **not** need to be closed — Full Disk Access is the only requirement.

### Python venv

Always use the project venv:
```bash
source venv/bin/activate
python photo_checker.py ...
# or without activating:
venv/bin/python photo_checker.py ...
```

Python 3.14 (system), venv at `./venv/`.

## Config & credentials

All sensitive files live **outside the repo** in `~/.photo_checker/`:
```
~/.photo_checker/
  config.json          # Google client_id/secret + OneDrive client_id
  tokens/
    google_token.json  # Google OAuth token (auto-refreshed)
    onedrive_cache.bin # MSAL token cache
  cache/
    google_filenames.json  # 24 h filename cache for Google Photos
```

`config.json` is only required when Google or OneDrive checks are enabled.

## Key design decisions (do not reverse without discussion)

1. **Filename matching, not hash** — hashes are fragile after metadata edits.
2. **Cross-format stem matching** — `IMG_1495.JPG` matches `IMG_1495.HEIC`. iPhone Live Photos are stored as HEIC in Apple Photos but backup copies are often JPEG. `load_apple_photos_filenames()` returns a 3-tuple `(name_set, size_index, stem_set)`.
3. **Copy-suffix stripping** — `_COPY_SUFFIX_RE` strips "- Copy", "- Copie", "_copy", "_copie" (case-insensitive, English + French) **and macOS/Windows numeric copy suffixes ` (1)`, ` (2)`, etc.** before matching. Both `photo_checker.py` and `api/main.py` share the same regex. Handles the Apple Photos duplicate merge scenario where the numbered variant (`Chloé (1).jpg`) is removed and the un-numbered original is kept.
4. **Photos silent skip = already imported** — Apple Photos exits 0 with empty stdout when its perceptual AI detects a visual duplicate. The import endpoint returns HTTP 200 / `already_in_photos` in that case.
5. **Google Photos uses a local cache** — the API has no filename search; we list all items once and cache for 24 h to avoid thousands of paginated calls on every run.
6. **OneDrive uses per-file Graph search** — `GET /me/drive/root/search(q='filename')` — reasonable for typical folder sizes.
7. **Deletion moves to trash** (`send2trash`), never permanent `unlink`. Fallback: timestamped sibling folder `_photo_checker_trash_YYYYMMDD_HHMMSS/`.
8. **`safe_to_delete = YES`** requires: found in ≥ 1 repo AND zero check errors. `MAYBE` = found somewhere but a check errored.
9. **macOS `._` resource fork files are excluded** from scanning.
10. **Scan metadata companion files** — `results/{slug}-meta.json` stores `scan_folder` (absolute path) and `scan_date` (ISO). `_slug_for_folder()` reuses the same slug on rescan, preventing duplicate sidebar entries.
11. **In-memory log buffer** — `_LOG_BUFFER` (500-line deque, thread-safe). All backend logging goes through `_log(level, msg)` — never `print(stderr)` directly. Exposed via `GET /api/logs`.
12. **UUID validation** — `open-photos` endpoint validates UUID format (`^[0-9A-F-]{36}$`) before embedding in AppleScript.
13. **Path validation** — `_validate_media_path()` guards thumbnail/video endpoints against traversal into system paths or non-media extensions.

## Apple Photos SQLite internals

- `ZASSET.ZFILENAME` is always a UUID-based internal name — **never use this for matching**.
- `ZADDITIONALASSETATTRIBUTES.ZORIGINALFILENAME` is the original import filename — this is what we compare against.
- `_sqlite_apple_names` (global set) and `_sqlite_apple_stems` (global set) are built once per server lifetime and invalidated on successful import.

## Coding conventions

- Python 3.10+ type hints (`list[Path]`, `bool | None`, etc.)
- No comments unless the WHY is non-obvious
- No feature flags or backwards-compat shims
- Keep all secrets out of the repo; validate only at system boundaries
