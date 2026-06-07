#!/usr/bin/env bash
# Build Photo Checker — self-contained macOS .app
# Usage: ./build.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
WEB="$ROOT/web"
OUT="$WEB/out"
DIST="$ROOT/dist"

echo "==> 1/4  Building Next.js frontend (static export)…"
cd "$WEB"
npm install --silent
NEXT_PUBLIC_API_URL="" npm run build
echo "    Static files in: $OUT"

echo ""
echo "==> 2/4  Installing Python build deps…"
cd "$ROOT"
venv/bin/pip install --quiet pyinstaller

echo ""
echo "==> 3/4  Bundling with PyInstaller…"
venv/bin/pyinstaller photo_checker.spec --clean --noconfirm

echo ""
echo "==> 4/4  Done!"
APP="$DIST/Photo Checker.app"
if [ -d "$APP" ]; then
    echo "    App bundle : $APP"
    echo "    Size       : $(du -sh "$APP" | cut -f1)"
    echo ""
    echo "    IMPORTANT: Before first run, grant Full Disk Access in"
    echo "    System Settings → Privacy & Security → Full Disk Access"
    echo "    and add 'Photo Checker' to the list."
    echo ""
    echo "    To run: open \"$APP\""
else
    echo "    WARNING: .app bundle not found — check PyInstaller output above."
fi
