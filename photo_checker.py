#!/usr/bin/env python3
"""
photo_checker.py — Check if local photos already exist in Apple Photos, Google Photos, or OneDrive.

Usage:
    python photo_checker.py /path/to/folder
    python photo_checker.py /path/to/folder --output results --skip-onedrive
    python photo_checker.py /path/to/folder --refresh-cache
"""

import os
import re
import sys
import json
import csv
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import quote

# ── Config & paths ─────────────────────────────────────────────────────────────

CONFIG_DIR   = Path.home() / '.photo_checker'
CONFIG_FILE  = CONFIG_DIR / 'config.json'
TOKENS_DIR   = CONFIG_DIR / 'tokens'
CACHE_DIR    = CONFIG_DIR / 'cache'

GOOGLE_TOKEN_FILE     = TOKENS_DIR / 'google_token.json'
GOOGLE_CACHE_FILE     = CACHE_DIR  / 'google_filenames.json'
GOOGLE_CACHE_TTL_HRS  = 24

ONEDRIVE_CACHE_FILE   = TOKENS_DIR / 'onedrive_cache.bin'
ONEDRIVE_AUTHORITY    = 'https://login.microsoftonline.com/common'
ONEDRIVE_SCOPES       = ['Files.Read']
GOOGLE_SCOPES         = ['https://www.googleapis.com/auth/photoslibrary.readonly']

IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.heic', '.heif',
    '.raw', '.cr2', '.cr3', '.nef', '.arw', '.dng',
    '.tiff', '.tif', '.gif', '.webp', '.bmp',
    '.mp4', '.mov', '.m4v',
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def status_label(found: bool | None, skipped: bool) -> str:
    if skipped:   return 'skipped'
    if found is None: return 'error'
    return 'yes' if found else 'no'


def scan_folder(folder: Path, recursive: bool = False) -> list[Path]:
    entries = folder.rglob('*') if recursive else folder.iterdir()
    return sorted(
        f for f in entries
        if f.is_file()
        and f.suffix.lower() in IMAGE_EXTENSIONS
        and not f.name.startswith('._')
    )


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        print(f"\nConfig file not found: {CONFIG_FILE}")
        print("Run:  python photo_checker.py --init-config   to create a template.\n")
        sys.exit(1)
    return json.loads(CONFIG_FILE.read_text())


def init_config():
    """Write a config template and exit."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    template = {
        "google": {
            "client_id":     "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com",
            "client_secret": "YOUR_GOOGLE_CLIENT_SECRET"
        },
        "onedrive": {
            "client_id": "YOUR_MICROSOFT_APP_CLIENT_ID"
        }
    }
    CONFIG_FILE.write_text(json.dumps(template, indent=2))
    print(f"Config template written to: {CONFIG_FILE}")
    print("Edit it with your API credentials, then re-run the tool.")
    print("\nSetup instructions:")
    print("  Google  → https://console.cloud.google.com (enable Photos Library API, create OAuth client, Desktop app type)")
    print("  OneDrive → https://portal.azure.com (App registrations, add Files.Read scope, Public client)")

# ── Apple Photos ───────────────────────────────────────────────────────────────

def _nfc(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFC", s)


_COPY_SUFFIX_RE = re.compile(
    r'(\s*-\s*copi[ey]|\s+copi[ey]|_copi[ey]|\s*-\s*copy|\s+copy|_copy|\s+\(\d+\))+$',
    re.IGNORECASE,
)

def _strip_copy_suffix(stem: str) -> str:
    """Remove trailing copy markers: ' - Copy', ' (2)', '_copy', etc."""
    return _COPY_SUFFIX_RE.sub('', stem)


def _photos_library_path() -> Path | None:
    """Find the default Photos library path."""
    candidates = [
        Path.home() / "Pictures" / "Photos Library.photoslibrary",
    ]
    for c in candidates:
        db = c / "database" / "Photos.sqlite"
        if db.exists():
            return db
    return None


def _file_sha1(path: Path) -> str:
    import hashlib
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_apple_photos_filenames() -> tuple[set, dict, set] | None:
    """Return (name_set, size_index, stem_set) or None on failure.

    name_set  : lowercased NFC filenames from ZORIGINALFILENAME
    size_index: {file_size_bytes: [(uuid, extension), ...]} for SHA1 fallback
    stem_set  : lowercased NFC stems (no extension) for cross-format matching
                e.g. IMG_1495 matches IMG_1495.HEIC when backup is IMG_1495.JPG

    Reads Photos.sqlite directly (WAL included) — osxphotos misses recent
    imports because Photos.app keeps WAL changes in memory."""
    import sqlite3

    db_path = _photos_library_path()
    if db_path is None:
        print("Apple Photos library not found.")
        return None
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = con.cursor()
        cur.execute("""
            SELECT aa.ZORIGINALFILENAME,
                   aa.ZORIGINALFILESIZE,
                   a.ZUUID,
                   a.ZFILENAME
            FROM   ZASSET a
            JOIN   ZADDITIONALASSETATTRIBUTES aa ON aa.ZASSET = a.Z_PK
            WHERE  a.ZTRASHEDSTATE = 0
              AND  aa.ZORIGINALFILENAME IS NOT NULL
        """)
        names: set = set()
        stems: set = set()
        size_index: dict = {}
        for orig_fn, size, uuid, zfilename in cur.fetchall():
            nfc_fn = _nfc(orig_fn).lower()
            names.add(nfc_fn)
            stems.add(Path(nfc_fn).stem)
            if size and uuid and zfilename:
                ext = Path(zfilename).suffix  # e.g. ".jpeg"
                size_index.setdefault(int(size), []).append((uuid, ext))
        con.close()
        logging.info(f"Apple Photos: {len(names)} filenames, {len(size_index)} sizes loaded")
        return names, size_index, stems
    except Exception as e:
        print(f"Apple Photos error: {e}")
        return None


def check_apple(filename: str, name_idx: set | None,
                size_idx: dict | None = None,
                filepath: Path | None = None,
                stem_idx: set | None = None) -> bool | None:
    if name_idx is None:
        return None
    p = Path(filename)
    # 1. Exact name match
    if _nfc(filename).lower() in name_idx:
        return True
    # 2. Backup has " - Copy" → Apple Photos stripped it
    stem_stripped = _strip_copy_suffix(p.stem)
    if stem_stripped != p.stem:
        if _nfc(stem_stripped + p.suffix).lower() in name_idx:
            return True
    # 3. Backup has no " - Copy" → Apple Photos added it on import
    if _nfc(p.stem + " - Copy" + p.suffix).lower() in name_idx:
        return True
    # 4. Cross-format stem match: IMG_1495.JPG → IMG_1495.HEIC (iPhone Live Photo)
    if stem_idx is not None and _nfc(p.stem).lower() in stem_idx:
        return True
    # 5. SHA1 fallback: match by file size then content
    if size_idx and filepath and filepath.is_file():
        try:
            size = filepath.stat().st_size
            candidates = size_idx.get(size, [])
            if candidates:
                backup_sha1 = _file_sha1(filepath)
                lib_root = _photos_library_path()
                if lib_root:
                    originals = lib_root.parent.parent / "originals"
                    for uuid, ext in candidates:
                        lib_file = originals / uuid[0] / f"{uuid}{ext}"
                        if lib_file.exists() and _file_sha1(lib_file) == backup_sha1:
                            return True
        except Exception:
            pass
    return False

# ── Google Photos ──────────────────────────────────────────────────────────────

def _google_credentials(config: dict):
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    creds = None
    if GOOGLE_TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN_FILE), GOOGLE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_cfg = {
                "installed": {
                    "client_id":     config['google']['client_id'],
                    "client_secret": config['google']['client_secret'],
                    "redirect_uris": ["http://localhost"],
                    "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
                    "token_uri":     "https://oauth2.googleapis.com/token",
                }
            }
            flow = InstalledAppFlow.from_client_config(client_cfg, GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)

        TOKENS_DIR.mkdir(parents=True, exist_ok=True)
        GOOGLE_TOKEN_FILE.write_text(creds.to_json())

    return creds


def _fetch_google_filenames(config: dict) -> set:
    import requests as req
    creds = _google_credentials(config)

    filenames: set = set()
    page_token = None
    page = 0

    print("  Fetching Google Photos library (paginated, may take a while for large libraries)...")

    while True:
        params = {'pageSize': 100}
        if page_token:
            params['pageToken'] = page_token

        resp = req.get(
            'https://photoslibrary.googleapis.com/v1/mediaItems',
            headers={'Authorization': f'Bearer {creds.token}'},
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        for item in data.get('mediaItems', []):
            name = item.get('filename', '').strip()
            if name:
                filenames.add(name.lower())

        page += 1
        if page % 10 == 0:
            print(f"    ...{len(filenames):,} items so far")

        page_token = data.get('nextPageToken')
        if not page_token:
            break

    return filenames


def load_google_filenames(config: dict, force_refresh: bool = False) -> set | None:
    try:
        if not force_refresh and GOOGLE_CACHE_FILE.exists():
            cached = json.loads(GOOGLE_CACHE_FILE.read_text())
            age = datetime.now() - datetime.fromisoformat(cached['fetched_at'])
            if age < timedelta(hours=GOOGLE_CACHE_TTL_HRS):
                names = set(cached['filenames'])
                print(f"  Google Photos: {len(names):,} items from cache (age {int(age.total_seconds()//3600)}h).")
                return names

        names = _fetch_google_filenames(config)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        GOOGLE_CACHE_FILE.write_text(json.dumps({
            'fetched_at': datetime.now().isoformat(),
            'filenames':  list(names),
        }))
        print(f"  Google Photos: {len(names):,} items indexed and cached.")
        return names

    except ImportError:
        print("  WARNING: google-auth-oauthlib not installed — skipping Google Photos.")
        return None
    except Exception as e:
        print(f"  WARNING: Google Photos error ({e}) — skipping.")
        return None


def check_google(filename: str, index: set | None) -> bool | None:
    if index is None:
        return None
    return filename.lower() in index

# ── OneDrive ───────────────────────────────────────────────────────────────────

def _onedrive_token(config: dict) -> str:
    import msal

    cache = msal.SerializableTokenCache()
    if ONEDRIVE_CACHE_FILE.exists():
        cache.deserialize(ONEDRIVE_CACHE_FILE.read_bytes())

    app = msal.PublicClientApplication(
        config['onedrive']['client_id'],
        authority=ONEDRIVE_AUTHORITY,
        token_cache=cache,
    )

    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(ONEDRIVE_SCOPES, account=accounts[0])

    if not result:
        print("\n  OneDrive authentication required:")
        flow = app.initiate_device_flow(scopes=ONEDRIVE_SCOPES)
        print(f"  {flow['message']}\n")
        result = app.acquire_token_by_device_flow(flow)

    if cache.has_state_changed:
        TOKENS_DIR.mkdir(parents=True, exist_ok=True)
        ONEDRIVE_CACHE_FILE.write_bytes(cache.serialize().encode())

    if 'access_token' not in result:
        raise RuntimeError(f"OneDrive auth failed: {result.get('error_description', result)}")

    return result['access_token']


_onedrive_token_cache: str | None = None

def check_onedrive(filename: str, config: dict) -> bool | None:
    global _onedrive_token_cache
    try:
        import requests as req

        if _onedrive_token_cache is None:
            _onedrive_token_cache = _onedrive_token(config)

        # Use search endpoint; encode filename safely
        safe_name = filename.replace("'", "''")  # escape single quotes in OData
        url = f"https://graph.microsoft.com/v1.0/me/drive/root/search(q='{quote(safe_name)}')"

        resp = req.get(
            url,
            headers={'Authorization': f'Bearer {_onedrive_token_cache}'},
            params={'$select': 'name,id', '$top': 10},
            timeout=20,
        )

        if resp.status_code == 401:
            # Token expired mid-run; clear cache and retry once
            _onedrive_token_cache = _onedrive_token(config)
            resp = req.get(url,
                           headers={'Authorization': f'Bearer {_onedrive_token_cache}'},
                           params={'$select': 'name,id', '$top': 10},
                           timeout=20)

        resp.raise_for_status()
        items = resp.json().get('value', [])
        return any(item.get('name', '').lower() == filename.lower() for item in items)

    except ImportError:
        print("  WARNING: msal not installed — skipping OneDrive.")
        return None
    except Exception as e:
        logging.debug(f"OneDrive check error for {filename}: {e}")
        return None

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Check if local photos exist in Apple Photos, Google Photos, and/or OneDrive.'
    )
    parser.add_argument('folder', nargs='?', help='Folder to scan')
    parser.add_argument('--output', default='photo_check_results',
                        help='Output file base name (default: photo_check_results)')
    parser.add_argument('--skip-apple',    action='store_true', help='Skip Apple Photos check')
    parser.add_argument('--skip-google',   action='store_true', help='Skip Google Photos check')
    parser.add_argument('--skip-onedrive', action='store_true', help='Skip OneDrive check')
    parser.add_argument('--refresh-cache', action='store_true', help='Force refresh of Google Photos cache')
    parser.add_argument('--init-config',   action='store_true', help='Write a config.json template and exit')
    parser.add_argument('--dry-run',       action='store_true',
                        help='Show which files would be deleted (safe_to_delete=YES) without making any changes')
    parser.add_argument('--delete',        action='store_true',
                        help='Move files marked safe_to_delete=YES to the system trash (requires confirmation)')
    parser.add_argument('--recursive',      action='store_true', help='Scan subfolders recursively')
    parser.add_argument('--verbose',       action='store_true', help='Show debug logging')
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    if args.init_config:
        init_config()
        return

    if not args.folder:
        parser.print_help()
        sys.exit(1)

    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        print(f"Error: not a directory: {folder}")
        sys.exit(1)

    need_config = not args.skip_google or not args.skip_onedrive
    config = load_config() if need_config else {}

    # ── Scan ──────────────────────────────────────────────────────────────────
    photos = scan_folder(folder, recursive=args.recursive)
    if not photos:
        print(f"No photos found in {folder}")
        sys.exit(0)
    print(f"\nFound {len(photos):,} photos in {folder}\n")

    # ── Build indexes ─────────────────────────────────────────────────────────
    apple_result  = load_apple_photos_filenames() if not args.skip_apple else None
    apple_names: set | None  = apple_result[0] if apple_result else None
    apple_sizes: dict | None = apple_result[1] if apple_result else None
    apple_stems: set | None  = apple_result[2] if apple_result else None
    google_idx = None if args.skip_google else load_google_filenames(config, args.refresh_cache)

    print()

    # ── Process each photo ────────────────────────────────────────────────────
    results = []
    for i, photo in enumerate(photos, 1):
        apple    = check_apple(photo.name, apple_names, apple_sizes, photo, apple_stems) if not args.skip_apple else None
        google   = check_google(photo.name, google_idx) if not args.skip_google else None
        onedrive = check_onedrive(photo.name, config)   if not args.skip_onedrive else None

        found_in = [
            repo for repo, found in [('apple_photos', apple), ('google_photos', google), ('onedrive', onedrive)]
            if found is True
        ]
        # Safe to delete = found in at least one repo AND no check resulted in an error
        checks = [(apple, args.skip_apple), (google, args.skip_google), (onedrive, args.skip_onedrive)]
        has_error = any(v is None and not skipped for v, skipped in checks)
        safe = bool(found_in) and not has_error

        results.append({
            'filename':      photo.name,
            'path':          str(photo),
            'size_kb':       round(photo.stat().st_size / 1024, 1),
            'apple_photos':  status_label(apple,    args.skip_apple),
            'google_photos': status_label(google,   args.skip_google),
            'onedrive':      status_label(onedrive, args.skip_onedrive),
            'found_in':      ', '.join(found_in) if found_in else '—',
            'safe_to_delete': 'YES' if safe else ('MAYBE' if found_in and has_error else 'NO'),
        })

        icon = 'OK' if safe else ('?' if found_in and has_error else 'NO')
        print(f"[{i:>4}/{len(photos)}] [{icon}] {photo.name}")

    # ── Write output ──────────────────────────────────────────────────────────
    csv_path  = Path(args.output).with_suffix('.csv')
    json_path = Path(args.output).with_suffix('.json')

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    # ── Summary ───────────────────────────────────────────────────────────────
    safe_count  = sum(1 for r in results if r['safe_to_delete'] == 'YES')
    maybe_count = sum(1 for r in results if r['safe_to_delete'] == 'MAYBE')
    no_count    = sum(1 for r in results if r['safe_to_delete'] == 'NO')

    mode_tag = ' [DRY RUN]' if args.dry_run else ''
    print(f"""
─────────────────────────────────────────
 Results for {folder.name}/{mode_tag}
─────────────────────────────────────────
 Total photos scanned : {len(results):>5}
 Safe to delete (YES) : {safe_count:>5}  ← found in all checked repos, no errors
 Check manually (MAYBE): {maybe_count:>4}  ← found somewhere but a check had an error
 Keep locally (NO)    : {no_count:>5}
─────────────────────────────────────────
 CSV  → {csv_path}
 JSON → {json_path}
""")

    # ── Delete / dry-run ──────────────────────────────────────────────────────
    safe_files = [r for r in results if r['safe_to_delete'] == 'YES']

    if args.dry_run:
        if not safe_files:
            print("[DRY RUN] No files would be deleted.")
        else:
            total_kb = sum(r['size_kb'] for r in safe_files)
            print(f"[DRY RUN] Would delete {len(safe_files)} file(s) ({total_kb:,.0f} KB freed):\n")
            for r in safe_files:
                print(f"  - {r['filename']}  ({r['size_kb']} KB)  backed up in: {r['found_in']}")
        print("\nRe-run with --delete to actually move these to the trash.")

    elif args.delete:
        if not safe_files:
            print("Nothing to delete (no files with safe_to_delete=YES).")
        else:
            total_kb = sum(r['size_kb'] for r in safe_files)
            print(f"About to move {len(safe_files)} file(s) ({total_kb:,.0f} KB) to trash:\n")
            for r in safe_files:
                print(f"  - {r['filename']}  ({r['size_kb']} KB)")
            print()
            confirm = input("Type 'yes' to confirm deletion: ").strip().lower()
            if confirm != 'yes':
                print("Aborted — no files deleted.")
            else:
                _do_delete(safe_files, folder)


def _do_delete(safe_files: list[dict], folder: Path) -> None:
    try:
        from send2trash import send2trash
        use_trash = True
    except ImportError:
        use_trash = False

    if not use_trash:
        # Fallback: move to a timestamped sibling folder
        backup_dir = folder.parent / f"_photo_checker_trash_{datetime.now():%Y%m%d_%H%M%S}"
        backup_dir.mkdir()
        print(f"(send2trash not installed — moving files to {backup_dir})\n")

    deleted, errors = 0, 0
    for r in safe_files:
        p = Path(r['path'])
        try:
            if use_trash:
                from send2trash import send2trash
                send2trash(str(p))
            else:
                p.rename(backup_dir / p.name)
            print(f"  Trashed: {r['filename']}")
            deleted += 1
        except Exception as e:
            print(f"  ERROR deleting {r['filename']}: {e}")
            errors += 1

    print(f"\nDone: {deleted} file(s) moved to trash, {errors} error(s).")


if __name__ == '__main__':
    main()
