# Roadmap — photo-checker

## Phase 0 — Proof of concept (DONE)
- [x] Scan folder, match by filename
- [x] Apple Photos via osxphotos
- [x] Google Photos skeleton (REST + cache)
- [x] OneDrive skeleton (Graph API + MSAL)
- [x] CSV + JSON output
- [x] `--dry-run` and `--delete` flags
- [x] GitHub repo created

---

## Phase 1 — Web UI MVP (DONE)

Full Next.js 14 + FastAPI web application replacing the CLI proof of concept.

### Completed
- [x] FastAPI backend serving scan, thumbnail, import, delete, patch endpoints
- [x] Next.js 14 static frontend (TypeScript + Tailwind)
- [x] Photo grid with lazy-loading thumbnails (JPEG, HEIC, video)
- [x] Filter bar (YES / NO / MAYBE / ALL) with live counts
- [x] Subfolder navigation sidebar
- [x] Sort by name / date / subfolder
- [x] Infinite scroll (32 photos per page)
- [x] Detail panel — Apple Photos metadata (albums, date, cloud status, UUID)
- [x] Import to Apple Photos from detail panel (async, skip duplicate dialog)
- [x] Multi-select with checkbox and shift-click range selection
- [x] Batch bar — Trash / Import / Force-delete with confirmation dialogs
- [x] Scan dialog with native macOS folder picker + fallback prompt
- [x] Results list in sidebar with per-result info modal / rescan / Finder / delete icons
- [x] Unicode NFC normalization fix (accented filenames: é, ü, ñ)
- [x] Batch key switched from filename → path (fixes selection bugs for same-name files in different subfolders)
- [x] README and screenshots
- [x] Cross-format stem matching: JPEG backup ↔ HEIC stored in Photos (Live Photos)
- [x] Copy-suffix stripping: "Copie" (FR) and "Copy" (EN) normalized before matching
- [x] Silent Photos import (empty stdout) correctly treated as `already_in_photos`
- [x] Scan metadata companion files (`{slug}-meta.json`) — prevents duplicate sidebar entries for same folder
- [x] SSE real-time scan progress (`GET /api/scan/stream`)
- [x] Keyboard shortcuts: j/k navigation, Space to select, ⌘A select all, Escape close
- [x] Toast notifications after batch Trash / import / delete
- [x] Reveal in Finder from detail panel and sidebar
- [x] MAYBE status tooltip explaining the condition
- [x] Auto-advance to next photo after import in detail panel
- [x] Server log panel: rolling 500-line buffer, `GET /api/logs`, accessible via sidebar button
- [x] Security: UUID format validation before AppleScript injection; path traversal guard on thumbnail/video endpoints

---

## Phase 1.1 — Stabilization (DONE)

Making the project a clean, testable, reproducible MVP before new features.

- [x] `_COPY_SUFFIX_RE` extended to handle macOS/Windows copy numbering `(1)`, `(2)`
- [x] `match_confidence` + `match_reason` fields added to scan records (high/medium/none/unknown)
- [x] `match_confidence: "medium"` warning in detail panel and batch-delete modal
- [x] AppleScript injection fixed: path passed as `argv` argument, not interpolated in script string
- [x] `requirements.txt` split: core / optional (Google, OneDrive, viewer) / dev
- [x] `requirements-dev.txt` with pytest and ruff
- [x] 54 unit tests: copy-suffix, NFC, confidence model, path security, UUID injection
- [x] `DEV_AUDIT.md` — audit findings, validation procedure, architecture reference
- [x] `CLAUDE.md` personal path removed
- [x] GitHub Actions CI (Python tests + frontend build on push)
- [x] `.gitignore` hardened (macOS, Node, Python artifacts, secret files)
- [x] Issue templates (bug, false positive, feature request)

---

## Phase 2 — API integrations

### 2.1 — Google Photos
- [ ] Create Google Cloud project, enable Photos Library API
- [ ] Create OAuth 2.0 Desktop credentials, fill `~/.photo_checker/config.json`
- [ ] Run first auth flow, verify token saved
- [ ] Full scan with Google Photos enabled, verify cache written
- [ ] UI toggle to enable/disable Google Photos check

### 2.2 — OneDrive (DONE — via rclone, no Azure)
Microsoft deprecated personal-account app registrations outside a directory, so the
Graph API path was dropped in favour of the `rclone` CLI (built-in OAuth, no Azure app).
- [x] `rclone config` (browser login) — no `client_id` / Azure registration needed
- [x] Filename index via `rclone lsf -R`, cached 24 h (O(1) lookup per photo)
- [x] Optional subfolder to avoid indexing a whole multi-hundred-GB drive
- [x] UI toggle + remote picker + subfolder field in the scan dialog
- [x] Validated end-to-end against a real 1 TB OneDrive

### 2.3 — Combined run
- [ ] Run all three sources on the same folder
- [ ] Spot-check accuracy: 5 YES files confirmed, 5 NO files confirmed absent

---

## Phase 3 — Performance & accuracy

- [ ] Large folder test: 5 000+ files, measure total runtime
- [x] OneDrive: filename cache (rclone lists all names once, cached 24 h — done in 2.2)
- [ ] Google token auto-refresh validation
- [ ] EXIF date+size as secondary signal for renamed files (reduce false negatives)
- [ ] Hash-based fallback for Apple Photos (already have fingerprint index — wire into scan)

---

## Phase 4 — Polish

- [x] Progress streaming during scan (SSE)
- [x] Keyboard shortcuts (j/k, Space, ⌘A, Escape)
- [x] Toast notifications after batch actions
- [x] Reveal in Finder (sidebar + detail panel)
- [x] MAYBE tooltip
- [x] Server log panel
- [x] Security hardening (UUID validation, path traversal guard)
- [x] Source filter in the main UX (All / Both / Apple only / OneDrive only / Neither) + per-thumbnail source badges
- [x] Thumbnails honor EXIF orientation (`exif_transpose`) + versioned URLs to bust stale cache
- [x] Upload to OneDrive (single + batch) — `rclone copyto` into a dedicated folder, collision-safe rename
- [x] Batch actions adapt to per-source presence (import to Apple / upload to OneDrive shown per photo)
- [x] Imports persisted path-safely (`/api/patch-imported`) so batch imports survive a reload
- [x] Scroll perf on large libraries — `content-visibility` + `React.memo` (no dependency added)
- [ ] Settings screen (API credentials, cache management)
- [ ] Export filtered results as CSV
- [ ] Dark/light mode
- [x] Packaged macOS app (PyInstaller + Next.js static bundle) — `build.sh` + `photo_checker.spec`
- [ ] Signed and notarized macOS app (requires Apple Developer Program)

### Scaling the photo grid further (optional, if needed)
The grid currently stays smooth via `content-visibility` + `React.memo` with **no added
dependency** — good up to ~10–20k photos per result. For much larger libraries, the next
step would be **true virtualization** (e.g. `react-virtuoso`'s `VirtuosoGrid` or
`react-window`), which unmounts off-screen cards entirely. This adds a dependency and a
grid/headers/shift-select rework, so it's deferred until a real need appears.
- [ ] (If needed) Virtualized photo grid via `react-virtuoso` / `react-window`

---

## Known limitations

| Limitation | Impact | Resolution |
|---|---|---|
| Filename-only matching | Renamed files not detected | Phase 3: EXIF date+size fallback |
| Google cache is 24 h | Stale if you upload during the day | `--refresh-cache` flag exists; add UI button |
| OneDrive uploads land in `PhotoChecker/`, not the indexed folder | A later scan indexing e.g. `Images` won't see them until re-indexed | Session record is patched immediately; future: union `path` + `upload_path` in the index |
| Uploaded photos not auto-added to Apple Photos (and vice-versa) | Backup to one source doesn't fill the other | Use the per-source batch actions to complete both |
| Apple Photos visual duplicate detection is opaque | Photos silently skips AI-detected duplicates — we can't tell which existing photo it matched | No bypass available via public API; treated as `already_in_photos` |
