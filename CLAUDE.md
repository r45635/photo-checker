# photo-checker — Claude Code context

## What this project is

A macOS CLI tool that scans a local folder of photos and checks, by filename, whether each file already exists in one or more cloud/local repositories:
- **Apple Photos** — via `osxphotos` (reads the local library directly, no API)
- **Google Photos** — via Google Photos Library REST API (OAuth 2.0, cached locally 24 h)
- **OneDrive** — via Microsoft Graph API (MSAL device-flow auth, token persisted)

The goal: help the user decide which local backup files are safe to delete because they are already stored elsewhere.

## Current state (proof-of-concept, no GUI)

- Matching is **filename-based** (not hash — EXIF/tag edits change hashes, filenames are stable)
- Output: CSV + JSON report
- Flags: `--dry-run` (preview deletions), `--delete` (move to trash via `send2trash`)
- Apple Photos works and was tested on a 1,697-file folder (237 found, ~849 MB recoverable)
- Google Photos and OneDrive require API credentials not yet configured

## Repository

- GitHub: https://github.com/r45635/photo-checker (private)
- Local: `/Users/vcruvellier/tools/photo_checker/`

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
2. **Google Photos uses a local cache** — the API has no filename search; we list all items once and cache for 24 h to avoid thousands of paginated calls on every run.
3. **OneDrive uses per-file Graph search** — `GET /me/drive/root/search(q='filename')` — reasonable for typical folder sizes.
4. **Deletion moves to trash** (`send2trash`), never permanent `unlink`. Fallback: timestamped sibling folder `_photo_checker_trash_YYYYMMDD_HHMMSS/`.
5. **`safe_to_delete = YES`** requires: found in ≥ 1 repo AND zero check errors. `MAYBE` = found somewhere but a check errored.
6. **macOS `._` resource fork files are excluded** from scanning.

## What must be validated before GUI MVP (see ROADMAP.md)

1. Google Photos OAuth flow end-to-end
2. OneDrive OAuth flow end-to-end
3. Accuracy of filename matching across all three sources on the same test folder
4. Cache invalidation and refresh logic
5. `--delete` / `send2trash` on a small real set
6. Performance on a large folder (2 000+ files)

## Coding conventions

- Python 3.10+ type hints (`list[Path]`, `bool | None`, etc.)
- No comments unless the WHY is non-obvious
- No feature flags or backwards-compat shims
- Keep all secrets out of the repo; validate only at system boundaries
