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

## Phase 1 — Concept validation (current focus — NO GUI yet)

Goal: prove the full pipeline works end-to-end on real data before investing in a GUI.

### 1.1 — Google Photos API setup and test
- [ ] Create Google Cloud project, enable Photos Library API
- [ ] Create OAuth 2.0 Desktop credentials, fill `~/.photo_checker/config.json`
- [ ] Run first auth flow (`run_local_server`), verify token saved
- [ ] Run full scan on the Camera folder with Google Photos enabled
- [ ] Verify cache written to `~/.photo_checker/cache/google_filenames.json`
- [ ] Re-run and confirm cache is used (fast, no API calls)
- [ ] Run `--refresh-cache` and confirm re-fetch

### 1.2 — OneDrive API setup and test
- [ ] Register app in Azure portal (App registrations), add `Files.Read` delegated scope
- [ ] Enable public client / native flows
- [ ] Fill `client_id` in `~/.photo_checker/config.json`
- [ ] Run first auth (device flow — follow printed URL+code), verify token cached
- [ ] Run scan on Camera folder with OneDrive enabled
- [ ] Verify per-file search returns correct results

### 1.3 — Three-source combined run
- [ ] Run full scan (all three sources) on Camera folder
- [ ] Compare `safe_to_delete` results vs Apple-only run
- [ ] Spot-check: pick 5 YES files, manually confirm they exist in each reported repo
- [ ] Spot-check: pick 5 NO files, confirm they are genuinely absent

### 1.4 — Deletion flow test
- [ ] Create a scratch folder with 3–5 expendable copies of known-backed-up photos
- [ ] Run with `--dry-run` — verify list matches expectations
- [ ] Run with `--delete` — confirm files move to Trash, folder is empty
- [ ] Verify files appear in macOS Trash and can be restored

### 1.5 — Edge cases
- [ ] Files with special characters in names (spaces, accents, apostrophes)
- [ ] Files present in Apple Photos but renamed (should show as NO — expected behavior)
- [ ] Very large folder (2 000+ files): measure total runtime
- [ ] Google token expiry: let token expire, verify auto-refresh works
- [ ] OneDrive token expiry: same

### 1.6 — Accuracy assessment
- [ ] Document false-negative rate (files that exist in repos but aren't matched)
  - Root cause: renamed files → consider adding EXIF date+size as a secondary signal
- [ ] Decide whether to add hash or metadata fallback before GUI phase

---

## Phase 2 — MVP with GUI (after Phase 1 is complete)

Only start this phase once Phase 1 validation is signed off.

### Technology choice (decide before starting)
Options:
- **Tkinter** — built-in, no install, basic look
- **PyQt6 / PySide6** — native macOS feel, more complex
- **Textual** — rich terminal UI (TUI), no windowing system needed, easiest to build

Recommendation: start with **Textual** (TUI). It runs in the terminal, looks modern,
and avoids packaging complexity. Upgrade to a real GUI only if needed.

### Planned GUI features
- [ ] Folder picker
- [ ] Checkboxes to enable/disable each source
- [ ] Progress bar during scan
- [ ] Sortable results table (filename, size, found_in, safe_to_delete)
- [ ] Select rows and delete with confirmation dialog
- [ ] Export CSV/JSON button
- [ ] Settings screen for API credentials

---

## Known limitations (track here)

| Limitation | Impact | Resolution |
|---|---|---|
| Filename-only matching | Renamed files not detected | Consider EXIF date+size fallback (Phase 1.6) |
| Google cache is 24 h | Stale if you upload during the day | Add `--refresh-cache` (already exists) |
| OneDrive: one API call per file | Slow for 5 000+ files | Consider building an OneDrive filename cache too |
| No recursive folder scan | Only top-level files checked | Add `--recursive` flag if needed |
