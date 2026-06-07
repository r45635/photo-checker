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

---

## Phase 2 — API integrations

### 2.1 — Google Photos
- [ ] Create Google Cloud project, enable Photos Library API
- [ ] Create OAuth 2.0 Desktop credentials, fill `~/.photo_checker/config.json`
- [ ] Run first auth flow, verify token saved
- [ ] Full scan with Google Photos enabled, verify cache written
- [ ] UI toggle to enable/disable Google Photos check

### 2.2 — OneDrive
- [ ] Register app in Azure portal, add `Files.Read` delegated scope
- [ ] Enable public client / native flows, fill `client_id` in config
- [ ] Run first auth (device flow), verify token cached
- [ ] Full scan with OneDrive enabled
- [ ] UI toggle to enable/disable OneDrive check

### 2.3 — Combined run
- [ ] Run all three sources on the same folder
- [ ] Spot-check accuracy: 5 YES files confirmed, 5 NO files confirmed absent

---

## Phase 3 — Performance & accuracy

- [ ] Large folder test: 5 000+ files, measure total runtime
- [ ] OneDrive: consider building a filename cache (currently one API call per file)
- [ ] Google token auto-refresh validation
- [ ] EXIF date+size as secondary signal for renamed files (reduce false negatives)
- [ ] Hash-based fallback for Apple Photos (already have fingerprint index — wire into scan)

---

## Phase 4 — Polish

- [ ] Settings screen (API credentials, cache management)
- [ ] Progress streaming during scan (SSE or WebSocket)
- [ ] Export filtered results as CSV
- [ ] Dark/light mode
- [ ] Keyboard shortcuts (j/k navigation, space to select, d to delete)
- [ ] Packaged macOS app (PyInstaller + Next.js static bundle)

---

## Known limitations

| Limitation | Impact | Resolution |
|---|---|---|
| Filename-only matching | Renamed files not detected | Phase 3: EXIF date+size fallback |
| Google cache is 24 h | Stale if you upload during the day | `--refresh-cache` flag exists; add UI button |
| OneDrive: one API call per file | Slow for 5 000+ files | Phase 3: build an OneDrive filename cache |
| Apple Photos only (Google/OneDrive not wired to UI) | Only one source checked | Phase 2 |
