# Photo Checker

A macOS tool that scans a local folder of photos and checks — by filename — whether each file already exists in your cloud or local repositories, so you can safely delete confirmed duplicates.

## Screenshots

### Main grid — safe-to-delete files (YES filter)
![Main grid YES](docs/screenshots/01_main_grid_yes.png)

### NO filter — files not found in any repository
![Main grid NO](docs/screenshots/02_main_grid_no.png)

### Full stats — all files
![All results](docs/screenshots/03_main_grid_all.png)

### Multi-select and batch actions
![Selection and batch bar](docs/screenshots/04_selection_batch_bar.png)

### Scan a new folder
![Scan dialog](docs/screenshots/05_scan_dialog.png)

### File detail panel
![Detail panel](docs/screenshots/06_detail_panel.png)

---

## What it does

- Scans a local folder (optionally recursive) and checks each photo by filename against:
  - **Apple Photos** ✅ — reads the local Photos library directly via `osxphotos` (no API, no network)
  - **Google Photos** 🚧 *(coming soon)* — API backend exists, UI integration in progress
  - **OneDrive** 🚧 *(coming soon)* — API backend exists, UI integration in progress
- Labels each file: `YES` (safe to delete — confirmed backup), `NO` (not found), `MAYBE` (found but a check errored)
- Lets you select files and **move to Trash** (`send2trash`), **import to Apple Photos**, or **force-move** to a folder
- Results are stored as JSON locally and browsable across sessions

---

## Architecture

```
photo_checker/
├── photo_checker.py      # Core scan logic (filename matching, Apple Photos via osxphotos)
├── api/
│   └── main.py           # FastAPI backend — scan, import, delete, thumbnails, Apple info, logs
├── web/                  # Next.js 14 frontend (TypeScript, Tailwind)
│   ├── app/page.tsx      # Main page — grid, filters, batch selection, keyboard shortcuts
│   ├── components/
│   │   ├── Sidebar.tsx   # Results list, filters, sort, subfolder nav, server logs button
│   │   ├── PhotoCard.tsx # Thumbnail card with selection
│   │   ├── DetailPanel.tsx  # Side panel — Apple Photos metadata, import, Reveal in Finder
│   │   ├── BatchBar.tsx  # Bottom bar — multi-select actions with progress
│   │   ├── ScanDialog.tsx   # Folder scan dialog with SSE progress
│   │   ├── LogPanel.tsx  # Server log viewer (rolling 500-line buffer)
│   │   └── Toast.tsx     # Toast notifications after batch actions
│   └── lib/
│       ├── api.ts        # Typed fetch wrappers
│       └── types.ts      # Shared TypeScript interfaces
├── results/              # Scan results (JSON + companion meta files, local only)
└── docs/screenshots/     # UI screenshots
```

**Runtime**: FastAPI serves both the API (`/api/*`) and the Next.js static build (`/`).  
**Dev**: Next.js dev server on `:3000` proxies API calls to FastAPI on `:8000`.

---

## Setup

### Requirements

- macOS (Apple Photos integration requires macOS)
- Python 3.10+
- Node.js 18+ (for frontend development only)

### Full Disk Access (required for Apple Photos)

`osxphotos` reads the Photos SQLite database directly. The app running the tool needs **Full Disk Access**:

| How you run it | App to grant access to |
|---|---|
| Terminal.app / iTerm2 | Terminal.app / iTerm2 |
| Via Claude Code in VS Code | Visual Studio Code |
| Via Claude desktop app | Claude.app |

**System Settings → Privacy & Security → Full Disk Access → add your terminal app**

### Install

```bash
git clone https://github.com/r45635/photo-checker
cd photo-checker

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt          # core: FastAPI, osxphotos, Pillow, send2trash, …
# pip install -r requirements-optional.txt  # optional: Google Photos, OneDrive, Streamlit viewer

cd web && npm install && npm run build   # Build frontend
cd ..
```

### Validate the install (optional)

```bash
pip install -r requirements-dev.txt  # pytest, ruff
pytest -v
```

### Config (for Google Photos / OneDrive)

```bash
mkdir -p ~/.photo_checker/tokens ~/.photo_checker/cache
```

Create `~/.photo_checker/config.json`:

```json
{
  "google_client_id": "YOUR_GOOGLE_CLIENT_ID",
  "google_client_secret": "YOUR_GOOGLE_CLIENT_SECRET",
  "onedrive_client_id": "YOUR_AZURE_APP_CLIENT_ID"
}
```

Apple Photos works with no config — it reads the local library directly.

---

## Run

```bash
# Production (serves web UI + API on port 8000)
source venv/bin/activate
python api/main.py
# → open http://localhost:8000

# Development (hot-reload frontend + API)
source venv/bin/activate
python -m uvicorn api.main:app --reload &   # API on :8000
cd web && npm run dev                        # UI on :3000 → open http://localhost:3000
```

---

## Usage

1. Click **Scan folder** → pick a folder path → optionally enable **Include subfolders** → **Scan**  
   A live progress bar shows files scanned in real time.
2. Results appear in the grid. Use the filter bar (**YES / NO / MAYBE / ALL**) and subfolder list to navigate.
3. Click any photo to open the **detail panel** — shows Apple Photos metadata (albums, date, cloud status) and an import button if not yet backed up. Use **Reveal in Finder** to locate the file on disk.
4. Check individual photos or use **shift-click** to range-select; the **batch bar** appears at the bottom.
5. From the batch bar:
   - **Trash** — move confirmed YES files to macOS Trash (recoverable)
   - **Import** — send NO files to Apple Photos (with live progress and auto-advance to next photo)
   - **Force delete** — move or trash files without confirmed backup (requires typing `DELETE`)
6. Use **Server logs** (bottom of sidebar) to inspect backend activity and diagnose import errors.

### Keyboard shortcuts

| Key | Action |
|---|---|
| `j` / `↓` | Next photo |
| `k` / `↑` | Previous photo |
| `Space` | Toggle selection |
| `⌘A` | Select all visible |
| `Escape` | Close detail panel / deselect |

---

## How matching works

Matching is **filename-based**, not hash-based — hashes change when metadata is edited; filenames are stable.

**Unicode normalization**: macOS filesystem paths come in NFD form; Apple Photos stores `original_filename` in NFC. The tool normalizes both sides to NFC before comparing, so filenames with accented characters (é, ü, ñ) match correctly.

**Cross-format stem matching**: iPhone Live Photos are stored in Apple Photos as HEIC but backup copies are often JPEG. `IMG_1495.JPG` matches `IMG_1495.HEIC` by comparing stems (filename without extension). This prevents false negatives for converted photos.

**Copy-suffix stripping**: Files like `IMG_1234 - Copy.jpg`, `IMG_1234 - Copie.jpg`, `IMG_1234_copy.JPG`, and `Chloé (1).jpg` (macOS/Windows automatic copy numbering) are normalized to their base name before matching. Supports English ("copy"), French ("copie"), and numeric suffixes ` (1)`, ` (2)`, etc. This handles the case where Apple Photos merges duplicates and retains the original name without the number.

**Fingerprint fallback**: for Apple Photos, the SHA-1 fingerprint stored in the Photos DB is checked as a secondary signal when the filename doesn't match (catches files that were renamed after import).

**Visual duplicate detection**: Apple Photos uses perceptual AI to detect duplicate photos during import, even when filenames and file sizes differ (e.g., a JPEG re-export of a HEIC). When Photos silently skips an import (empty stdout, exit 0), the tool correctly treats this as `already_in_photos` — a successful match.

**`safe_to_delete = YES`** requires: found in ≥ 1 repository AND zero check errors.  
**`safe_to_delete = MAYBE`** = found somewhere but at least one check errored. Hovering the MAYBE badge shows an explanation.

**`match_confidence`** indicates how the match was found:
- `high` — exact filename match or SHA-1 content match
- `medium` — copy-suffix normalization or cross-format stem match (JPG↔HEIC)
- `none` — no match found
- `unknown` — Apple Photos index unavailable

`medium` matches are shown with an amber warning in the detail panel and in the batch-delete confirmation. Review them before bulk deletion.

---

## Key design decisions

| Decision | Reason |
|---|---|
| Filename matching (not hash) | EXIF/tag edits change hashes; filenames are stable |
| Cross-format stem matching | iPhone Live Photos saved as HEIC but backups are JPEG — same stem, different extension |
| Copy-suffix stripping | Users make copies like "IMG_1234 - Copie.jpg" or "Chloé (1).jpg"; these are the same photo — handles Apple Photos duplicate merge |
| Google Photos uses a local 24 h cache | The API has no filename search; listing everything once avoids thousands of paginated API calls |
| OneDrive uses per-file Graph search | `GET /me/drive/root/search(q='filename')` — acceptable for typical folder sizes |
| Deletion via `send2trash` | Never permanent; files land in macOS Trash and can be restored |
| `skip check duplicates true` in AppleScript import | Prevents Photos from showing a blocking dialog that would time out the API |
| Silent import (empty stdout) = success | Photos silently skips visual duplicates (exit 0, no output) — correctly treated as already imported |
| Results stored as local JSON + companion meta | No database dependency; companion `{slug}-meta.json` stores actual scanned folder path to prevent duplicate entries |
| In-memory 500-line log buffer | Visible via `GET /api/logs` and the Server logs panel — helps diagnose silent failures |
| UUID validation before AppleScript | `open-photos` validates UUID format to prevent AppleScript injection |
| Path validation on thumbnail/video endpoints | `_validate_media_path()` blocks traversal into system paths and non-media extensions |

## Tested

- Apple Photos: 37 000+ item library, 1 600-file scan folder, 402 confirmed duplicates detected
- Unicode normalization fix: 392 additional matches found after NFC normalization (files with accented names, e.g. Chloé)
- Cross-format stem matching: correctly detects HEIC-stored Live Photos from JPEG backup files
- Visual duplicate detection: Photos' perceptual AI is now handled correctly (silent skip = already imported)
