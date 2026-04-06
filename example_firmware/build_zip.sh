#!/usr/bin/env bash
# Build a firmware zip for upload to the nano_backbone server.
#
# Usage:   ./build_zip.sh <version>
# Example: ./build_zip.sh 1.0.0
#
# Produces env_sensor_<version>.zip in the example_firmware/ directory and
# prints the SHA-256 digest for local verification (the Django admin computes
# it automatically on save — no manual entry required).
#
# boot.py is intentionally excluded — it is the OTA safety boundary and must
# not be overwritten by an update.

set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version>" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="${SCRIPT_DIR}/env_sensor_${VERSION}.zip"

FILES=(
    code.py
    ota.py
    captive.py
    sensor.py
    display.py
    mqtt_ha.py
)

cd "$SCRIPT_DIR"

# Remove any existing zip for this version
rm -f "$OUT"

zip "$OUT" "${FILES[@]}"

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
