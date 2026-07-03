#!/usr/bin/env bash
# Package the built "Photo Checker.app" into a distributable DMG
# (drag-to-Applications). Run after ./build.sh.
#
# Usage: ./scripts/package_dmg.sh
# Version is taken from $PHOTOCHECKER_VERSION (default 1.0.0).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
APP="$DIST/Photo Checker.app"
VERSION="${PHOTOCHECKER_VERSION:-1.0.0}"
DMG="$DIST/PhotoChecker-$VERSION.dmg"
STAGE="$DIST/dmg_staging"

if [ ! -d "$APP" ]; then
    echo "ERROR: $APP not found — run ./build.sh first." >&2
    exit 1
fi

echo "==> Staging DMG contents…"
rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"   # drag-to-install target

echo "==> Building compressed DMG…"
hdiutil create \
    -volname "Photo Checker" \
    -srcfolder "$STAGE" \
    -ov -format UDZO \
    "$DMG"

rm -rf "$STAGE"

echo ""
echo "==> Done: $DMG"
echo "    Size: $(du -sh "$DMG" | cut -f1)"
echo ""
echo "    Unsigned build — first launch on another Mac:"
echo "      right-click the app → Open,  or:  xattr -cr \"/Applications/Photo Checker.app\""
