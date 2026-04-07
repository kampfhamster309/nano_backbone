#!/usr/bin/env bash
# Build a firmware zip for upload to the nano_backbone server.
#
# Usage:   ./build_zip.sh <version>
# Example: ./build_zip.sh 1.0.0
#
# Produces firmware_<version>.zip in the firmware/ directory and
# prints the SHA-256 digest for local verification (the Django admin computes
# it automatically on save — no manual entry required).
#
# boot.py is intentionally excluded — it is the OTA safety boundary and must
# not be overwritten by an update.
#
# If a release introduces a new library dependency, stage it in lib/ before
# building so it gets bundled alongside the firmware files:
#
#   lib/<library>.mpy   — from the Adafruit CircuitPython Bundle

set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version>" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="${SCRIPT_DIR}/firmware_${VERSION}.zip"

FILES=(
    code.py
    ota.py
    captive.py
)

LIB_FILES=()

cd "$SCRIPT_DIR"

# Verify all required library files are present before building.
for lib in "${LIB_FILES[@]}"; do
    if [[ ! -f "$lib" ]]; then
        echo "Error: missing $lib" >&2
        echo "Copy it into firmware/lib/ first." >&2
        exit 1
    fi
done

# Generate firmware_manifest.txt — one filename per line, listing every
# file boot.py must restore during a rollback. This lets boot.py discover
# the file list dynamically without needing to be updated itself.
MANIFEST="firmware_manifest.txt"
printf "%s\n" "${FILES[@]}" "$MANIFEST" > "$MANIFEST"

# Remove any existing zip for this version
rm -f "$OUT"

if [[ ${#LIB_FILES[@]} -gt 0 ]]; then
    zip "$OUT" "${FILES[@]}" "${LIB_FILES[@]}" "$MANIFEST"
else
    zip "$OUT" "${FILES[@]}" "$MANIFEST"
fi

rm -f "$MANIFEST"

# sha256sum (Linux) / shasum -a 256 (macOS)
if command -v sha256sum &>/dev/null; then
    SHA256=$(sha256sum "$OUT" | awk '{print $1}')
else
    SHA256=$(shasum -a 256 "$OUT" | awk '{print $1}')
fi

echo ""
echo "Created : $OUT"
echo "SHA256  : $SHA256"
echo ""
echo "Upload this zip via the Django admin (SHA-256 is computed automatically on save):"
echo "  http://<server>:8000/admin/firmware/firmwarerelease/add/"
