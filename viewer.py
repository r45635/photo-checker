#!/usr/bin/env python3
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image, ImageOps

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

RESULTS_DIR = Path(__file__).parent / "results"
THUMB_SIZE  = (320, 320)
DETAIL_SIZE = (900, 900)
VIDEO_EXTS  = {".mp4", ".mov", ".m4v"}
STATUS_COLOR = {"YES": "#22c55e", "NO": "#ef4444", "MAYBE": "#f59e0b"}

st.set_page_config(
    page_title="Photo Checker",
    page_icon="📷",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.9rem; font-weight: 700; }
[data-testid="stMetricDelta"] { font-size: 0.85rem; }

/* ── Card status strip (always visible, colored by status) ── */
.card-strip {
    font-size: 0.6rem;
    font-weight: 800;
    text-align: center;
    padding: 3px 0 2px;
    border-radius: 5px 5px 0 0;
    letter-spacing: 0.09em;
    color: rgba(255,255,255,0.92);
    margin-bottom: 0;
}

/* ── Card meta ── */
.photo-meta {
    font-size: 0.74rem;
    line-height: 1.35;
    margin: 3px 0 1px;
    overflow: hidden;
}
.fname { font-weight: 600; color: #dde; }
.dim   { color: #606878; font-size: 0.68rem; }
.sf-line {
    font-size: 0.63rem;
    color: #3a5470;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 2px;
    letter-spacing: 0.01em;
}

/* ── Status badge (detail panel) ── */
.badge {
    display: inline-block;
    border-radius: 4px;
    padding: 1px 7px;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    color: white;
    vertical-align: middle;
}

/* ── Detail panel ── */
.detail-meta { font-size: 0.85rem; line-height: 2; }

/* ── Batch bar ── */
.sel-bar {
    background: #111a27;
    border: 1px solid #1d3050;
    border-radius: 8px;
    padding: 0.6rem 1rem;
    margin-bottom: 0.75rem;
}

/* ── Subfolder section header in grid ── */
.sf-header {
    margin: 1.1rem 0 0.2rem;
    padding: 0.3rem 0.8rem;
    background: #0d1520;
    border-left: 3px solid #2563eb;
    border-radius: 0 4px 4px 0;
    font-size: 0.8rem;
    color: #6a9fd4;
    font-weight: 600;
    letter-spacing: 0.02em;
}
</style>
""", unsafe_allow_html=True)


# ── Session state ──────────────────────────────────────────────────────────────

if "selected"           not in st.session_state: st.session_state.selected           = None
if "import_result"      not in st.session_state: st.session_state.import_result      = None
if "imported_files"     not in st.session_state: st.session_state.imported_files     = set()
if "scan_running"       not in st.session_state: st.session_state.scan_running       = False
if "scan_output"        not in st.session_state: st.session_state.scan_output        = None
if "batch"              not in st.session_state: st.session_state.batch              = set()
if "confirm_action"     not in st.session_state: st.session_state.confirm_action     = None
if "scan_folder_path"   not in st.session_state: st.session_state.scan_folder_path   = ""
if "visible_count"      not in st.session_state: st.session_state.visible_count      = 0
if "_grid_sig"          not in st.session_state: st.session_state._grid_sig          = ""
if "playing_videos"     not in st.session_state: st.session_state.playing_videos     = set()
if "selected_subfolder" not in st.session_state: st.session_state.selected_subfolder = None
if "move_target_folder" not in st.session_state: st.session_state.move_target_folder = ""
if "force_confirm_text" not in st.session_state: st.session_state.force_confirm_text = ""


# ── Apple Photos helpers ───────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Loading Apple Photos library…")
def apple_photos_index() -> dict:
    """Returns {lowercase_filename: dict}. Stores plain data, not live PhotoInfo objects."""
    try:
        import osxphotos
        db = osxphotos.PhotosDB()
        index: dict = {}
        for p in db.photos():
            key = p.original_filename.lower()
            if key not in index:
                derivatives = getattr(p, "path_derivatives", None) or []
                index[key] = {
                    "uuid":        p.uuid,
                    "path":        p.path,
                    "derivatives": derivatives,
                    "date":        p.date,
                    "albums":      p.albums,
                    "keywords":    p.keywords,
                    "favorite":    p.favorite,
                    "ismissing":   p.ismissing,
                    "iscloudasset": p.iscloudasset,
                }
        return index
    except Exception as exc:
        st.warning(f"Apple Photos library unavailable: {exc}")
        return {}


def find_in_apple(filename: str) -> dict | None:
    return apple_photos_index().get(filename.lower())


def best_apple_path(ap: dict) -> str | None:
    """Return the best available local path: original → largest derivative → None."""
    if ap.get("path") and Path(ap["path"]).exists():
        return ap["path"]
    for d in sorted(ap.get("derivatives", []), key=lambda p: Path(p).stat().st_size if Path(p).exists() else 0, reverse=True):
        if Path(d).exists():
            return d
    return None


def open_in_photos(uuid: str) -> None:
    script = f'''
tell application "Photos"
    activate
    set thePhoto to media item id "{uuid}"
    spotlight thePhoto
end tell'''
    subprocess.Popen(["osascript", "-e", script])


def _to_jpeg_bytes(path: str, max_size: tuple) -> bytes | None:
    """Always converts via PIL → bytes. Never passes paths to Streamlit (fails on /Volumes/)."""
    try:
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        img.thumbnail(max_size, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88)
        return buf.getvalue()
    except Exception as e:
        st.error(f"Could not open image: {e}")
        return None


def show_image(path: str, max_size: tuple = DETAIL_SIZE) -> None:
    if not Path(path).exists():
        st.warning("File not accessible — is the drive connected?")
        return
    data = _to_jpeg_bytes(path, max_size)
    if data:
        st.image(data, use_container_width=True)


def import_to_apple_photos(path: str) -> tuple[bool, str]:
    safe = path.replace('"', '\\"')
    r = subprocess.run(
        ["osascript", "-e", f'tell application "Photos" to import POSIX file "{safe}"'],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode == 0:
        return True, "Imported successfully into Apple Photos."
    return False, r.stderr.strip() or "Import failed."


def patch_result_json(json_path: Path, filename: str) -> None:
    """Update a single record in the JSON/CSV after a successful import."""
    data = json.loads(json_path.read_text())
    for rec in data:
        if rec["filename"] == filename:
            rec["apple_photos"]   = "yes"
            rec["found_in"]       = "apple_photos"
            rec["safe_to_delete"] = "YES"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    csv_path = json_path.with_suffix(".csv")
    if csv_path.exists():
        import csv as csv_mod
        rows = data
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv_mod.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


def output_name_for(folder: str) -> str:
    """Derive a results filename from a folder path. e.g. /a/b/c/d → c_d"""
    parts = [p for p in Path(folder).parts if p not in ('/', '\\')]
    slug  = "_".join(parts[-2:]) if len(parts) >= 2 else parts[-1]
    return re.sub(r'[^\w\-]', '_', slug)


PHOTO_CHECKER = Path(__file__).parent / "photo_checker.py"


@st.cache_data
def load_results(path: str) -> pd.DataFrame:
    return pd.DataFrame(json.loads(Path(path).read_text()))


def pick_folder() -> str:
    """Open native macOS folder chooser via osascript. Returns path or empty string if cancelled."""
    r = subprocess.run(
        ["osascript", "-e", 'POSIX path of (choose folder with prompt "Select folder to scan")'],
        capture_output=True, text=True, timeout=300,
    )
    if r.returncode == 0:
        return r.stdout.strip().rstrip("/")
    return ""


def run_scan(folder: str, output_base: str, recursive: bool) -> tuple[bool, str]:
    cmd = [
        sys.executable, str(PHOTO_CHECKER),
        folder,
        "--skip-google", "--skip-onedrive",
        "--output", output_base,
    ]
    if recursive:
        cmd.append("--recursive")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    out = r.stdout + ("\n" + r.stderr if r.stderr else "")
    return r.returncode == 0, out


# ── Batch helpers ──────────────────────────────────────────────────────────────

def batch_import(records: list[dict], json_path: Path) -> tuple[int, list[str]]:
    ok_count, failed = 0, []
    bar = st.progress(0, text="Importing…")
    for i, rec in enumerate(records):
        ok, msg = import_to_apple_photos(rec["path"])
        if ok:
            ok_count += 1
            st.session_state.imported_files.add(rec["filename"])
            patch_result_json(json_path, rec["filename"])
        else:
            failed.append(f'{rec["filename"]}: {msg}')
        bar.progress((i + 1) / len(records), text=f"Importing {i+1}/{len(records)}…")
    bar.empty()
    load_results.clear()
    return ok_count, failed


def batch_delete(records: list[dict], json_path: Path) -> tuple[int, list[str]]:
    try:
        from send2trash import send2trash
        use_trash = True
    except ImportError:
        use_trash = False

    ok_count, failed = 0, []
    bar = st.progress(0, text="Moving to Trash…")
    data = json.loads(json_path.read_text())

    for i, rec in enumerate(records):
        try:
            if use_trash:
                send2trash(rec["path"])
            else:
                Path(rec["path"]).unlink()
            # Remove from JSON
            data = [r for r in data if r["filename"] != rec["filename"]]
            ok_count += 1
        except Exception as e:
            failed.append(f'{rec["filename"]}: {e}')
        bar.progress((i + 1) / len(records), text=f"Deleting {i+1}/{len(records)}…")

    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    bar.empty()
    load_results.clear()
    return ok_count, failed


def batch_move(records: list[dict], dest_dir: str, json_path: Path) -> tuple[int, list[str]]:
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    ok_count, failed = 0, []
    bar = st.progress(0, text="Moving files…")
    data = json.loads(json_path.read_text())

    for i, rec in enumerate(records):
        try:
            src = Path(rec["path"])
            target = dest / src.name
            if target.exists():
                target = dest / (src.stem + f"_1{src.suffix}")
            shutil.move(str(src), str(target))
            data = [r for r in data if r["filename"] != rec["filename"]]
            ok_count += 1
        except Exception as e:
            failed.append(f'{rec["filename"]}: {e}')
        bar.progress((i + 1) / len(records), text=f"Moving {i+1}/{len(records)}…")

    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    bar.empty()
    load_results.clear()
    return ok_count, failed


def _sf_of(path: str, root: Path) -> str:
    """Return the subfolder relative to root, or '' if at root level."""
    try:
        rel = Path(path).parent.relative_to(root)
        return str(rel) if str(rel) != "." else ""
    except ValueError:
        return ""


def _scan_root_for(paths: list[str]) -> Path:
    if not paths:
        return Path(".")
    root = Path(os.path.commonpath(paths))
    return root if root.is_dir() else root.parent


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📷 Photo Checker")

    # ── Scan a new folder ──────────────────────────────────────────────────────
    with st.expander("🔍 Scan a folder", expanded=False):
        # Browse button — opens native macOS folder picker
        if st.button("📁 Browse…", use_container_width=True):
            chosen = pick_folder()
            if chosen:
                st.session_state.scan_folder_path = chosen
                st.rerun()

        # Editable path field (pre-filled by picker, or typed manually)
        scan_folder_input = st.text_input(
            "Folder path",
            value=st.session_state.scan_folder_path,
            placeholder="/Volumes/My Passport/Photos",
            label_visibility="collapsed",
        )
        if scan_folder_input != st.session_state.scan_folder_path:
            st.session_state.scan_folder_path = scan_folder_input

        recursive = st.checkbox("Include subfolders", value=False)

        if st.button("▶ Scan", type="primary", use_container_width=True,
                     disabled=not st.session_state.scan_folder_path):
            folder_path = st.session_state.scan_folder_path.strip()
            if not Path(folder_path).is_dir():
                st.error("Folder not found.")
            else:
                out_name = output_name_for(folder_path)
                out_base = str(RESULTS_DIR / out_name)
                with st.spinner(f"Scanning {'recursively ' if recursive else ''}…"):
                    ok, log = run_scan(folder_path, out_base, recursive)
                if ok:
                    load_results.clear()
                    st.session_state.imported_files = set()
                    st.session_state.selected       = None
                    st.session_state.batch          = set()
                    st.success(f"Done — results saved as `{out_name}`")
                    st.rerun()
                else:
                    st.error("Scan failed.")
                    st.code(log[-2000:])

    st.divider()

    # ── Results file picker ────────────────────────────────────────────────────
    result_files = sorted(RESULTS_DIR.glob("*.json"))
    if not result_files:
        st.error("No result files found. Scan a folder first.")
        st.stop()

    selected_file = st.selectbox(
        "Results file",
        result_files,
        format_func=lambda p: p.stem,
    )

    _rscan_col, _finder_col = st.columns(2)
    with _rscan_col:
        if st.button("🔄 Re-scan", use_container_width=True):
            try:
                _df_tmp   = pd.DataFrame(json.loads(selected_file.read_text()))
                _folder   = str(Path(_df_tmp.iloc[0]["path"]).parent)
                _out_base = str(selected_file.with_suffix(""))
                with st.spinner("Re-scanning…"):
                    ok, log = run_scan(_folder, _out_base, recursive=False)
                if ok:
                    load_results.clear()
                    st.session_state.imported_files = set()
                    st.session_state.selected       = None
                    st.rerun()
                else:
                    st.error("Re-scan failed.")
                    st.code(log[-2000:])
            except Exception as e:
                st.error(f"Could not determine folder: {e}")
    with _finder_col:
        if st.button("📂 Finder", use_container_width=True):
            try:
                _df_tmp = pd.DataFrame(json.loads(selected_file.read_text()))
                _folder = str(Path(_df_tmp.iloc[0]["path"]).parent)
                subprocess.Popen(["open", _folder])
            except Exception as e:
                st.error(f"Could not open folder: {e}")

    st.divider()

    # ── Filters ────────────────────────────────────────────────────────────────
    filter_status = st.radio(
        "Filter",
        ["All", "YES", "NO", "MAYBE"],
        index=1,
        captions=["All files", "Safe to delete", "Keep locally", "Check manually"],
    )

    search = st.text_input("Search filename", placeholder="IMG_1234…")

    st.divider()

    view_mode = st.radio("View", ["Grid", "Table"], horizontal=True)
    if view_mode == "Grid":
        grid_cols = st.slider("Columns", 2, 6, 4)
        photos_per_page = grid_cols * 8

    sort_by   = st.radio("Sort by", ["Name", "Date", "Subfolder"], horizontal=True)
    sort_desc = st.checkbox("Descending", value=False)

    # ── Folder tree (loaded from cache — no extra I/O) ─────────────────────────
    try:
        _sb_df    = load_results(str(selected_file))
        _sb_paths = _sb_df["path"].tolist()
        _sb_root  = _scan_root_for(_sb_paths)
        _sb_df    = _sb_df.copy()
        _sb_df["_sf"] = _sb_df["path"].apply(lambda p: _sf_of(p, _sb_root))
        _sf_has   = _sb_df["_sf"].ne("").any()

        if _sf_has:
            st.divider()
            st.markdown(
                '<p style="font-size:0.72rem;color:#556;margin:0 0 6px;'
                'text-transform:uppercase;letter-spacing:0.07em">Folders</p>',
                unsafe_allow_html=True,
            )
            _sf_counts = _sb_df.groupby("_sf").size()
            total_all  = len(_sb_df)

            _sf_active = st.session_state.selected_subfolder
            if st.button(
                f"📁  All  ({total_all})",
                key="sf_all",
                use_container_width=True,
                type="primary" if _sf_active is None else "secondary",
            ):
                st.session_state.selected_subfolder = None
                st.rerun()

            for _sf_path in sorted(_sf_counts.index):
                _depth  = _sf_path.count(os.sep)
                _name   = _sf_path.split(os.sep)[-1]
                _indent = "   " * _depth
                _lbl    = f"{_indent}{'└ ' if _depth else ''}📂  {_name}  ({_sf_counts[_sf_path]})"
                if st.button(
                    _lbl,
                    key=f"sf_{_sf_path}",
                    use_container_width=True,
                    type="primary" if _sf_active == _sf_path else "secondary",
                ):
                    st.session_state.selected_subfolder = _sf_path
                    st.rerun()
    except Exception:
        pass


# ── Data ───────────────────────────────────────────────────────────────────────

df_all = load_results(str(selected_file)).copy()

# Apply in-session import overrides so UI reflects imports without a full re-scan
if st.session_state.imported_files:
    mask = df_all["filename"].isin(st.session_state.imported_files)
    df_all.loc[mask, "apple_photos"]   = "yes"
    df_all.loc[mask, "found_in"]       = "apple_photos"
    df_all.loc[mask, "safe_to_delete"] = "YES"

# Compute subfolder for every record (uses module-level helpers)
_all_paths  = df_all["path"].tolist()
_scan_root  = _scan_root_for(_all_paths)
df_all["_subfolder"] = df_all["path"].apply(lambda p: _sf_of(p, _scan_root))
_has_subfolders = df_all["_subfolder"].ne("").any()

# Filter
df = df_all.copy()
if filter_status != "All":
    df = df[df["safe_to_delete"] == filter_status]
if search:
    df = df[df["filename"].str.contains(search, case=False, na=False)]
if st.session_state.selected_subfolder is not None:
    df = df[df["_subfolder"] == st.session_state.selected_subfolder]

# Sort
_DATE_RE = re.compile(r"(\d{8})")
def _date_key(fname: str) -> str:
    m = _DATE_RE.search(fname)
    return m.group(1) + fname if m else fname

_asc = not sort_desc
if sort_by == "Name":
    df = df.sort_values("filename", ascending=_asc, key=lambda s: s.str.lower())
elif sort_by == "Date":
    df = df.sort_values("filename", ascending=_asc,
                        key=lambda s: s.map(_date_key).str.lower())
elif sort_by == "Subfolder":
    df = df.sort_values(["_subfolder", "filename"], ascending=[_asc, True],
                        key=lambda s: s.str.lower())


# ── Metrics ────────────────────────────────────────────────────────────────────

yes_count   = (df_all["safe_to_delete"] == "YES").sum()
no_count    = (df_all["safe_to_delete"] == "NO").sum()
maybe_count = (df_all["safe_to_delete"] == "MAYBE").sum()
rec_mb      = df_all.loc[df_all["safe_to_delete"] == "YES", "size_kb"].sum() / 1024

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total scanned",  f"{len(df_all):,}")
c2.metric("Safe to delete", f"{yes_count:,}", delta=f"{rec_mb:.0f} MB recoverable")
c3.metric("Keep locally",   f"{no_count:,}")
c4.metric("Check manually", f"{maybe_count:,}")

_sort_label = f"{sort_by} {'↓' if sort_desc else '↑'}"
_sf_label   = f" · 📂 {st.session_state.selected_subfolder}" if st.session_state.selected_subfolder else ""
st.caption(f"Showing **{len(df):,}** of {len(df_all):,} · `{selected_file.stem}` · {_sort_label}{_sf_label}")
st.divider()


# ── Batch action bar ───────────────────────────────────────────────────────────

if st.session_state.batch:
    batch_recs       = df_all[df_all["filename"].isin(st.session_state.batch)].to_dict("records")
    batch_mb         = sum(r["size_kb"] for r in batch_recs) / 1024
    can_delete       = [r for r in batch_recs if r["safe_to_delete"] == "YES"]
    can_import       = [r for r in batch_recs if r["safe_to_delete"] == "NO"]
    can_force_delete = [r for r in batch_recs if r["safe_to_delete"] in ("NO", "MAYBE")]

    with st.container():
        st.markdown('<div class="sel-bar">', unsafe_allow_html=True)
        b1, b2, b3, b4, b5, b6 = st.columns([3, 2, 2, 2, 1, 1])
        with b1:
            st.markdown(
                f"**{len(st.session_state.batch)} selected** &nbsp;·&nbsp; {batch_mb:.1f} MB",
                unsafe_allow_html=True,
            )
        with b2:
            if can_import:
                if st.button(f"⬆ Import {len(can_import)}", use_container_width=True,
                             help="Import NO files into Apple Photos"):
                    st.session_state.confirm_action = "import"
        with b3:
            if can_delete:
                if st.button(f"🗑 Trash {len(can_delete)}", use_container_width=True,
                             help="Move YES files to macOS Trash", type="primary"):
                    st.session_state.confirm_action = "delete"
        with b4:
            if can_force_delete:
                if st.button(f"⚠ Supprimer {len(can_force_delete)}", use_container_width=True,
                             help="Supprimer des fichiers sans backup (NO/MAYBE) — double confirmation requise"):
                    st.session_state.confirm_action = "force_delete_1"
                    st.session_state.force_confirm_text = ""
        with b5:
            if st.button("Tout", use_container_width=True, help="Sélectionner tout le visible"):
                st.session_state.batch = set(df["filename"].tolist())
                st.session_state.confirm_action = None
                st.rerun()
        with b6:
            if st.button("✕", use_container_width=True, help="Désélectionner tout"):
                st.session_state.batch = set()
                st.session_state.confirm_action = None
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Confirmations ──────────────────────────────────────────────────────────
    if st.session_state.confirm_action == "delete":
        total_mb = sum(r["size_kb"] for r in can_delete) / 1024
        with st.container(border=True):
            st.warning(
                f"**Déplacer {len(can_delete)} fichier(s) dans la Corbeille** ({total_mb:.1f} MB)  \n"
                "Récupérables depuis la Corbeille macOS jusqu'à son vidage.",
                icon="⚠️",
            )
            names = [r["filename"] for r in can_delete[:8]]
            if len(can_delete) > 8:
                names.append(f"… et {len(can_delete)-8} de plus")
            st.code("\n".join(names), language=None)
            cc1, cc2, _ = st.columns([1, 1, 5])
            with cc1:
                if st.button("✓ Confirmer", type="primary", key="confirm_del"):
                    with st.spinner("Déplacement vers la Corbeille…"):
                        n, errors = batch_delete(can_delete, selected_file)
                    st.session_state.batch = set()
                    st.session_state.confirm_action = None
                    if errors:
                        st.error(f"{n} supprimés, {len(errors)} erreurs:\n" + "\n".join(errors))
                    else:
                        st.success(f"{n} fichier(s) déplacés dans la Corbeille.")
                    st.rerun()
            with cc2:
                if st.button("Annuler", key="cancel_del"):
                    st.session_state.confirm_action = None
                    st.rerun()

    elif st.session_state.confirm_action == "import":
        with st.container(border=True):
            st.info(
                f"**Importer {len(can_import)} fichier(s) dans Apple Photos**  \n"
                "Les fichiers seront ajoutés à ta bibliothèque.",
                icon="⬆️",
            )
            names = [r["filename"] for r in can_import[:8]]
            if len(can_import) > 8:
                names.append(f"… et {len(can_import)-8} de plus")
            st.code("\n".join(names), language=None)
            ci1, ci2, _ = st.columns([1, 1, 5])
            with ci1:
                if st.button("✓ Confirmer l'import", type="primary", key="confirm_imp"):
                    with st.spinner("Import en cours…"):
                        n, errors = batch_import(can_import, selected_file)
                    st.session_state.batch = set()
                    st.session_state.confirm_action = None
                    if errors:
                        st.error(f"{n} importés, {len(errors)} erreurs:\n" + "\n".join(errors))
                    else:
                        st.success(f"{n} fichier(s) importés dans Apple Photos.")
                    st.rerun()
            with ci2:
                if st.button("Annuler", key="cancel_import"):
                    st.session_state.confirm_action = None
                    st.rerun()

    elif st.session_state.confirm_action == "force_delete_1":
        total_mb = sum(r["size_kb"] for r in can_force_delete) / 1024
        with st.container(border=True):
            st.error(
                f"**ATTENTION — {len(can_force_delete)} fichier(s) sans backup confirmé** ({total_mb:.1f} MB)  \n"
                "Ces fichiers sont marqués NO ou MAYBE : ils ne sont pas confirmés dans Apple Photos.  \n"
                "Deux options : les **supprimer** (Corbeille) ou les **déplacer** dans un dossier d'archive.",
                icon="🚨",
            )
            names = [r["filename"] for r in can_force_delete[:10]]
            if len(can_force_delete) > 10:
                names.append(f"… et {len(can_force_delete)-10} de plus")
            st.code("\n".join(names), language=None)

            _dest_col, _browse_col = st.columns([5, 1])
            with _dest_col:
                _dest = st.text_input(
                    "Dossier de destination (optionnel — laisser vide pour envoyer en Corbeille)",
                    value=st.session_state.move_target_folder,
                    placeholder="/Volumes/Backup/Archives",
                    label_visibility="visible",
                    key="move_dest_input",
                )
                if _dest != st.session_state.move_target_folder:
                    st.session_state.move_target_folder = _dest
            with _browse_col:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("📁 Choisir", use_container_width=True, key="browse_dest"):
                    _chosen = pick_folder()
                    if _chosen:
                        st.session_state.move_target_folder = _chosen
                        st.rerun()

            fd1, fd2, _ = st.columns([1, 1, 4])
            with fd1:
                if st.button("Continuer →", type="primary", key="force_step2"):
                    st.session_state.confirm_action = "force_delete_2"
                    st.rerun()
            with fd2:
                if st.button("Annuler", key="cancel_force1"):
                    st.session_state.confirm_action = None
                    st.session_state.move_target_folder = ""
                    st.rerun()

    elif st.session_state.confirm_action == "force_delete_2":
        total_mb = sum(r["size_kb"] for r in can_force_delete) / 1024
        dest     = st.session_state.move_target_folder.strip()
        action   = f"déplacer vers {dest}" if dest else "envoyer en Corbeille"
        with st.container(border=True):
            st.error(
                f"**DERNIÈRE CONFIRMATION** — {len(can_force_delete)} fichier(s) · {total_mb:.1f} MB  \n"
                f"Action : **{action}**  \n"
                "Tape **SUPPRIMER** ci-dessous pour confirmer.",
                icon="🚨",
            )
            typed = st.text_input("", placeholder="SUPPRIMER", key="force_confirm_input",
                                  label_visibility="collapsed")
            ready = typed.strip().upper() == "SUPPRIMER"
            fd2a, fd2b, _ = st.columns([1, 1, 4])
            with fd2a:
                if st.button("✓ Exécuter", type="primary", key="force_exec",
                             disabled=not ready):
                    if dest:
                        with st.spinner(f"Déplacement vers {dest}…"):
                            n, errors = batch_move(can_force_delete, dest, selected_file)
                        action_done = f"{n} fichier(s) déplacés vers {dest}."
                    else:
                        with st.spinner("Déplacement vers la Corbeille…"):
                            n, errors = batch_delete(can_force_delete, selected_file)
                        action_done = f"{n} fichier(s) envoyés en Corbeille."
                    st.session_state.batch = set()
                    st.session_state.confirm_action = None
                    st.session_state.move_target_folder = ""
                    if errors:
                        st.error(f"{n} traités, {len(errors)} erreurs:\n" + "\n".join(errors))
                    else:
                        st.success(action_done)
                    st.rerun()
            with fd2b:
                if st.button("Annuler", key="cancel_force2"):
                    st.session_state.confirm_action = None
                    st.rerun()

    st.divider()


# ── Detail panel ───────────────────────────────────────────────────────────────

if st.session_state.selected:
    rec    = st.session_state.selected
    status = rec["safe_to_delete"]
    color  = STATUS_COLOR.get(status, "#888")

    hdr, close_col = st.columns([11, 1])
    with hdr:
        st.markdown(
            f'<span class="badge" style="background:{color}">{status}</span>'
            f'&ensp;<strong style="font-size:1.05rem">{rec["filename"]}</strong>',
            unsafe_allow_html=True,
        )
    with close_col:
        if st.button("✕ Close", key="close"):
            st.session_state.selected = None
            st.session_state.import_result = None
            st.rerun()

    left, right = st.columns(2)

    # ── Left: backup copy ──────────────────────────────────────────────────────
    with left:
        st.caption("📂 Backup copy")
        ext = Path(rec["path"]).suffix.lower()
        if ext in VIDEO_EXTS:
            st.video(rec["path"])
        elif Path(rec["path"]).exists():
            show_image(rec["path"])
        else:
            st.warning("File not accessible — is the drive connected?")
        st.markdown(
            f'<div class="detail-meta dim">'
            f'{rec["path"]}<br>{rec["size_kb"] / 1024:.2f} MB'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Right: Apple Photos version or import ──────────────────────────────────
    with right:
        if status == "YES":
            ap = find_in_apple(rec["filename"])
            if ap:
                img_path = best_apple_path(ap)
                is_icloud_only = not ap.get("path") or not Path(ap["path"]).exists()

                if is_icloud_only:
                    st.caption("🍎 In Apple Photos (☁️ iCloud — showing cached thumbnail)")
                else:
                    st.caption("🍎 In Apple Photos — verified copy")

                if img_path:
                    show_image(img_path)
                else:
                    st.info("No local copy or thumbnail available (fully remote iCloud asset).")

                date_str = ap["date"].strftime("%Y-%m-%d %H:%M") if ap.get("date") else "—"
                albums   = ", ".join(ap["albums"])   if ap.get("albums")   else "—"
                keywords = ", ".join(ap["keywords"]) if ap.get("keywords") else "—"
                icloud_badge = " ☁️" if ap.get("iscloudasset") else ""
                st.markdown(
                    f'<div class="detail-meta">'
                    f'📅 &nbsp;<strong>{date_str}</strong><br>'
                    f'📁 &nbsp;<strong>{albums}</strong><br>'
                    f'🏷 &nbsp;<strong>{keywords}</strong><br>'
                    f'⭐ &nbsp;<strong>{"Favourite" if ap.get("favorite") else "Not favourite"}</strong>'
                    f'{icloud_badge}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.markdown("")
                if st.button("Open in Photos.app ↗", key="open_photos"):
                    open_in_photos(ap["uuid"])
            else:
                st.warning("Filename matched but photo not found in library index.")

        elif status == "NO":
            st.caption("🍎 Not in Apple Photos")
            st.info("This photo has **no backup** in Apple Photos yet.")
            st.markdown("Import it now to back it up.")

            if st.session_state.import_result:
                ok, msg = st.session_state.import_result
                (st.success if ok else st.error)(msg)

            if st.button("⬆ Import into Apple Photos", type="primary", key="import_btn"):
                with st.spinner("Importing…"):
                    ok, msg = import_to_apple_photos(rec["path"])
                st.session_state.import_result = (ok, msg)
                if ok:
                    st.session_state.imported_files.add(rec["filename"])
                    patch_result_json(selected_file, rec["filename"])
                    load_results.clear()
                    # Update the selected record so detail panel reflects new status
                    st.session_state.selected = {**rec, "apple_photos": "yes",
                                                  "found_in": "apple_photos",
                                                  "safe_to_delete": "YES"}
                st.rerun()

        else:
            st.info("Status unclear — check manually.")

    st.divider()


# ── Thumbnail helpers ──────────────────────────────────────────────────────────

@st.cache_data(max_entries=100, show_spinner=False)
def make_video_thumbnail(path: str) -> bytes | None:
    """Extract a preview frame from a video using macOS Quick Look (qlmanage)."""
    import tempfile
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                ["qlmanage", "-t", "-s", "640", "-o", tmpdir, path],
                capture_output=True, timeout=15,
            )
            # qlmanage names the output file <original_basename>.png
            out = Path(tmpdir) / (Path(path).name + ".png")
            if not out.exists():
                # Sometimes uses just .png with a different naming
                pngs = list(Path(tmpdir).glob("*.png"))
                if not pngs:
                    return None
                out = pngs[0]
            img = Image.open(out).convert("RGB")
            img.thumbnail(THUMB_SIZE, Image.LANCZOS)
            bg = Image.new("RGB", THUMB_SIZE, (18, 18, 18))
            offset = ((THUMB_SIZE[0] - img.width) // 2, (THUMB_SIZE[1] - img.height) // 2)
            bg.paste(img, offset)
            buf = io.BytesIO()
            bg.save(buf, format="JPEG", quality=82)
            return buf.getvalue()
    except Exception:
        return None


@st.cache_data(max_entries=600, show_spinner=False)
def make_thumbnail(path: str) -> bytes | None:
    try:
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        img.thumbnail(THUMB_SIZE, Image.LANCZOS)
        bg = Image.new("RGB", THUMB_SIZE, (18, 18, 18))
        offset = ((THUMB_SIZE[0] - img.width) // 2, (THUMB_SIZE[1] - img.height) // 2)
        bg.paste(img, offset)
        buf = io.BytesIO()
        bg.save(buf, format="JPEG", quality=82)
        return buf.getvalue()
    except Exception:
        return None


# ── Grid view ──────────────────────────────────────────────────────────────────

if view_mode == "Grid":
    records = df.to_dict("records")
    if not records:
        st.info("No photos match the current filter.")
        st.stop()

    # Reset visible count when filter/sort/file/cols change
    grid_sig = f"{filter_status}|{search}|{selected_file}|{grid_cols}|{sort_by}|{sort_desc}"
    if st.session_state._grid_sig != grid_sig:
        st.session_state._grid_sig     = grid_sig
        st.session_state.visible_count = grid_cols * 6  # initial batch = 6 rows

    visible = records[: st.session_state.visible_count]

    # Subfolder grouping — only when sort_by == "Subfolder" and subfolders exist
    _current_sf = None

    for row_start in range(0, len(visible), grid_cols):
        row  = visible[row_start : row_start + grid_cols]

        # Inject subfolder header before a new group begins
        if sort_by == "Subfolder" and _has_subfolders:
            sf = row[0].get("_subfolder", "")
            if sf != _current_sf:
                _current_sf = sf
                label = f"📁 {sf}" if sf else "📁 (root)"
                st.markdown(
                    f'<div style="margin:1.2rem 0 0.4rem;padding:0.4rem 0.8rem;'
                    f'background:#1e2a3a;border-left:3px solid #4a9eff;border-radius:4px;'
                    f'font-size:0.85rem;color:#aac8ff;font-weight:600">{label}</div>',
                    unsafe_allow_html=True,
                )

        cols = st.columns(grid_cols)
        for col, rec in zip(cols, row):
            fname       = rec["filename"]
            is_selected = fname in st.session_state.batch
            status      = rec["safe_to_delete"]
            color       = STATUS_COLOR.get(status, "#888")

            with col:
                # ── Colored status strip (always visible) ──────────────────────
                strip_label = f"☑  {status}" if is_selected else status
                st.markdown(
                    f'<div class="card-strip" style="background:{color}">{strip_label}</div>',
                    unsafe_allow_html=True,
                )

                # ── Media ──────────────────────────────────────────────────────
                ext        = Path(rec["path"]).suffix.lower()
                is_video   = ext in VIDEO_EXTS
                is_playing = fname in st.session_state.playing_videos

                if is_video and is_playing:
                    st.video(rec["path"])
                else:
                    if is_video:
                        vthumb = make_video_thumbnail(rec["path"])
                        if vthumb:
                            st.image(vthumb, use_container_width=True)
                        else:
                            st.markdown(
                                '<div style="height:160px;display:flex;align-items:center;'
                                'justify-content:center;background:#0e1520;font-size:2rem">🎬</div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        thumb = make_thumbnail(rec["path"])
                        if thumb:
                            st.image(thumb, use_container_width=True)
                        else:
                            st.markdown(
                                '<div style="height:160px;display:flex;align-items:center;'
                                'justify-content:center;background:#0e1520;'
                                'color:#333;font-size:0.75rem">Inaccessible</div>',
                                unsafe_allow_html=True,
                            )

                # ── Meta ───────────────────────────────────────────────────────
                name_disp = fname if len(fname) <= 26 else fname[:24] + "…"
                size_mb   = rec["size_kb"] / 1024
                sf        = rec.get("_subfolder", "")
                sf_html   = (
                    f'<div class="sf-line" title="{sf}">⌂ {sf}</div>'
                    if sf and _has_subfolders else ""
                )
                st.markdown(
                    f'<div class="photo-meta">{sf_html}'
                    f'<span class="fname" title="{fname}">{name_disp}</span><br>'
                    f'<span class="dim">{size_mb:.1f} MB</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # ── Action buttons ─────────────────────────────────────────────
                if is_video and is_playing:
                    if st.button("⏹  Stop", key=f"stop_{fname}", use_container_width=True):
                        st.session_state.playing_videos.discard(fname)
                        st.rerun()
                elif is_video:
                    va, vb, vc = st.columns([2, 1, 1])
                    with va:
                        if st.button("▶ Play", key=f"play_{fname}", use_container_width=True,
                                     type="primary"):
                            st.session_state.playing_videos.add(fname)
                            st.rerun()
                    with vb:
                        lbl = "☑" if is_selected else "☐"
                        if st.button(lbl, key=f"sel_{fname}", use_container_width=True,
                                     help="Sélectionner"):
                            if is_selected:
                                st.session_state.batch.discard(fname)
                            else:
                                st.session_state.batch.add(fname)
                            st.session_state.confirm_action = None
                            st.rerun()
                    with vc:
                        if st.button("↗", key=f"btn_{fname}", use_container_width=True,
                                     help="Voir le détail"):
                            st.session_state.selected = rec
                            st.session_state.import_result = None
                            st.rerun()
                else:
                    ba, bb = st.columns([1, 1])
                    with ba:
                        lbl = "☑" if is_selected else "☐"
                        if st.button(lbl, key=f"sel_{fname}", use_container_width=True,
                                     help="Sélectionner"):
                            if is_selected:
                                st.session_state.batch.discard(fname)
                            else:
                                st.session_state.batch.add(fname)
                            st.session_state.confirm_action = None
                            st.rerun()
                    with bb:
                        if st.button("↗", key=f"btn_{fname}", use_container_width=True,
                                     help="Voir le détail"):
                            st.session_state.selected = rec
                            st.session_state.import_result = None
                            st.rerun()

    # ── Infinite scroll ────────────────────────────────────────────────────────
    remaining = len(records) - len(visible)
    if remaining > 0:
        # Hidden trigger button — clicked by the scroll-watcher below
        if st.button("__more__", key="auto_load_more"):
            st.session_state.visible_count += grid_cols * 6
            st.rerun()

        # Inject a scroll-watcher into the parent window.
        # When the user reaches within 400 px of the page bottom,
        # it clicks the hidden button above, causing Streamlit to rerun.
        st.components.v1.html(
            """
            <script>
            (function() {
                var P = window.parent;

                // Remove any listener left over from the previous render
                if (P.__pcScrollHandler) {
                    P.removeEventListener("scroll", P.__pcScrollHandler);
                    P.__pcScrollHandler = null;
                }

                function findBtn() {
                    var ps = P.document.querySelectorAll("button p");
                    for (var i = 0; i < ps.length; i++) {
                        if (ps[i].innerText.trim() === "__more__")
                            return ps[i].closest("button");
                    }
                    return null;
                }

                // Make the trigger invisible but keep it in the DOM
                var btn = findBtn();
                if (btn) {
                    btn.style.cssText =
                        "opacity:0!important;height:1px!important;" +
                        "overflow:hidden!important;padding:0!important;" +
                        "margin:0!important;border:0!important;" +
                        "pointer-events:none!important;display:block!important;";
                }

                function check() {
                    var d = P.document.documentElement;
                    var fromBottom = d.scrollHeight - d.scrollTop - d.clientHeight;
                    if (fromBottom < 400) {
                        var b = findBtn();
                        if (b) {
                            P.removeEventListener("scroll", P.__pcScrollHandler);
                            P.__pcScrollHandler = null;
                            b.click();
                        }
                    }
                }

                P.__pcScrollHandler = check;
                P.addEventListener("scroll", check, { passive: true });
                // Also fire immediately — handles the case where the page is
                // already short enough to show the bottom without scrolling
                setTimeout(check, 120);
            })();
            </script>
            """,
            height=0,
            scrolling=False,
        )

        st.markdown(
            f'<p style="text-align:center;color:#2a3550;font-size:0.7rem;margin:4px 0">'
            f'{remaining} photos restantes</p>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<p style="text-align:center;color:#2a3550;font-size:0.7rem;margin:8px 0">'
            f'— {len(records)} photos chargées —</p>',
            unsafe_allow_html=True,
        )


# ── Table view ─────────────────────────────────────────────────────────────────

else:
    _cols = ["filename", "size_kb", "apple_photos", "google_photos",
             "onedrive", "found_in", "safe_to_delete"]
    if _has_subfolders:
        _cols = ["_subfolder"] + _cols
    display = df[_cols].copy()
    display.insert(_cols.index("size_kb") + 1, "size_mb", (display["size_kb"] / 1024).round(2))
    display = display.drop(columns=["size_kb"])

    _col_cfg = {
        "filename":       st.column_config.TextColumn("Filename", width="large"),
        "size_mb":        st.column_config.NumberColumn("Size", format="%.1f MB"),
        "apple_photos":   st.column_config.TextColumn("Apple Photos"),
        "google_photos":  st.column_config.TextColumn("Google Photos"),
        "onedrive":       st.column_config.TextColumn("OneDrive"),
        "found_in":       st.column_config.TextColumn("Found in"),
        "safe_to_delete": st.column_config.TextColumn("Status"),
    }
    if _has_subfolders:
        _col_cfg["_subfolder"] = st.column_config.TextColumn("Subfolder")

    event = st.dataframe(
        display,
        use_container_width=True,
        height=640,
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row",
        column_config=_col_cfg,
    )

    if event.selection and event.selection.rows:
        selected_names = set(df.iloc[event.selection.rows]["filename"].tolist())
        if selected_names != st.session_state.batch:
            st.session_state.batch = selected_names
            st.session_state.confirm_action = None
            st.rerun()
