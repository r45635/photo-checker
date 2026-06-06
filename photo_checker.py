#!/usr/bin/env python3
"""
photo_checker.py — Check if local photos already exist in Apple Photos, Google Photos, or OneDrive.

Usage:
    python photo_checker.py /path/to/folder
    python photo_checker.py /path/to/folder --output results --skip-onedrive
    python photo_checker.py /path/to/folder --refresh-cache
"""

import os
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


def scan_folder(folder: Path) -> list[Path]:
    return sorted(
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
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

def load_apple_photos_filenames() -> set | None:
    try:
        import osxphotos
        print("Loading Apple Photos library (may take a moment for large libraries)...")
        db = osxphotos.PhotosDB()
        names = {p.original_filename.lower() for p in db.photos()}
        print(f"  Apple Photos: {len(names):,} items indexed.")
        return names
    except ImportError:
        print("  WARNING: osxphotos not installed — skipping Apple Photos. Run: pip install osxphotos")
        return None
    except Exception as e:
        print(f"  WARNING: Apple Photos error ({e}) — skipping.")
        return None


def check_apple(filename: str, index: set | None) -> bool | None:
    if index is None:
        return None
    return filename.lower() in index

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

    config = load_config()

    # ── Scan ──────────────────────────────────────────────────────────────────
    photos = scan_folder(folder)
    if not photos:
        print(f"No photos found in {folder}")
        sys.exit(0)
    print(f"\nFound {len(photos):,} photos in {folder}\n")

    # ── Build indexes ─────────────────────────────────────────────────────────
    apple_idx  = None if args.skip_apple  else load_apple_photos_filenames()
    google_idx = None if args.skip_google else load_google_filenames(config, args.refresh_cache)

    print()

    # ── Process each photo ────────────────────────────────────────────────────
    results = []
    for i, photo in enumerate(photos, 1):
        apple    = check_apple(photo.name, apple_idx)   if not args.skip_apple  else None
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
