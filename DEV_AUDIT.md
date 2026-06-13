# DEV_AUDIT.md — photo-checker stabilization audit

> Internal development reference. Not end-user documentation.

## Project state (2026-06-13) — v1.1.0 Stabilization complete

photo-checker is a local macOS web app (FastAPI + Next.js 14) for checking whether backup photos/videos already exist in Apple Photos. The Apple Photos flow is stable and production-ready. Google Photos and OneDrive backends exist in `photo_checker.py` but are not wired to the web API.

## Findings

| Domain | Status | Priority |
|---|---|---|
| Apple Photos matching | Stable, 37k+ item library tested | ✓ |
| Google Photos web integration | Not wired to API, always `"skipped"` | Medium |
| OneDrive web integration | Not wired to API, always `"skipped"` | Medium |
| `requirements.txt` | Mixed CLI + legacy viewer deps | Fixed → see Commit 2 |
| `requirements-dev.txt` | Missing | Fixed → see Commit 2 |
| Unit tests | None existed | Fixed → see Commit 6 |
| AppleScript escaping (`/api/import`) | Incomplete for special chars | Fixed → see Commit 3 |
| Match confidence fields | No per-record confidence/reason | Fixed → see Commit 5 |
| `CLAUDE.md` personal path | Local path exposed | Fixed → see Commit 4 |
| `results/*.json` in git | Not tracked (`.gitignore` scoped to `results/`) | ✓ OK |
| CORS policy | Restricted to localhost:3000 only | ✓ OK |
| UUID validation | Validated before AppleScript (`_UUID_RE`) | ✓ OK |
| `_validate_media_path()` | Blocks system dirs + extension whitelist | ✓ OK (see note) |
| `.gitignore` | Missing .DS_Store, node_modules/, .next/, .pytest_cache/ | Fixed |
| GitHub Actions CI | Missing | Fixed → `.github/workflows/test.yml` |
| Issue templates | Missing | Fixed → `.github/ISSUE_TEMPLATE/` |

## Security note: `_validate_media_path()`

The function blocks access to sensitive system paths (`/etc`, `/System`, `/usr`, `~/.ssh`, `~/.photo_checker/tokens`) and enforces a media extension whitelist. It does **not** restrict access to the originally scanned folder — in principle, any file on disk with an allowed extension can be served.

This is acceptable by design: the app is local-only (localhost CORS), single-user, and users legitimately need to view photos from arbitrary locations on their own disk. Do not change this behavior without understanding the trade-off.

## `viewer.py` (Streamlit legacy UI)

`viewer.py` is the original Streamlit-based UI, superseded by the current Next.js web app. It is still present in the repo but is not part of the active application. Its dependencies (`streamlit`, `pandas`) have been moved to `requirements-optional.txt` to keep the core install lean.

**Do not delete `viewer.py` without an explicit decision** — it may still be useful for debugging or quick CSV inspection.

## Dependency layout

| File | Purpose |
|---|---|
| `requirements.txt` | Core runtime: FastAPI backend + CLI + matching |
| `requirements-optional.txt` | Google Photos, OneDrive, Streamlit viewer |
| `requirements-dev.txt` | Test and lint tools |

## Local validation procedure

```bash
# Create and activate venv
python -m venv venv
source venv/bin/activate

# Install runtime dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest -v

# Start the backend (dev mode, auto-reload)
uvicorn api.main:app --reload --port 8000

# Start the frontend (in another terminal)
cd web && npm run dev
```

## Architecture quick-reference

```
photo_checker/
├── photo_checker.py       CLI + matching core (check_apple, check_google, etc.)
├── api/
│   └── main.py            FastAPI backend (scan, thumbnail, import, delete)
├── web/                   Next.js 14 frontend (static export)
│   ├── app/page.tsx       Main UI
│   ├── components/        PhotoCard, DetailPanel, Sidebar, Lightbox, ...
│   └── lib/               types.ts, api.ts
├── results/               Scan result JSON files (not tracked in git)
├── viewer.py              Legacy Streamlit UI (inactive)
├── requirements.txt       Core deps
├── requirements-optional.txt  Google Photos / OneDrive / viewer
├── requirements-dev.txt   pytest, ruff
├── .github/
│   ├── workflows/test.yml     CI: python tests + frontend build
│   └── ISSUE_TEMPLATE/        bug_report, false_positive, feature_request
└── DEV_AUDIT.md           This file
```

## v1.1.0 release checklist

- [x] `pytest -v` → 54/54 passed
- [x] `pip install -r requirements.txt -r requirements-dev.txt` succeeds from clean venv
- [x] Frontend builds: `cd web && npm ci && npm run build`
- [x] README does not oversell Google Photos or OneDrive
- [x] CLAUDE.md contains no personal paths or private data
- [x] Results include `match_confidence` and `match_reason`
- [x] All deletions go via `send2trash` (no direct `unlink`)
- [x] Sensitive endpoints validate paths (`_validate_media_path`)
- [x] AppleScript path passed as argv (no injection)
- [x] GitHub Actions CI runs on push
- [x] `.gitignore` covers macOS, Node, Python, and secret file patterns
- [x] Issue templates present

## Known limitations

- Filename-based matching only (not perceptual hash). Files significantly edited after import may not be recognized.
- Apple Photos duplicate merge can change internal filenames — rescan after major library reorganization.
- `match_confidence: "medium"` records (cross-format or copy-suffix matches) should be reviewed before bulk deletion.
- Google Photos and OneDrive are not accessible from the web UI.
