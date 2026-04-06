"""
OTA firmware update logic for the Arduino Nano RP2040 Connect.

apply() is called from code.py when a newer firmware version is available.
On success it calls microcontroller.reset() and never returns.
On failure it raises RuntimeError so code.py can continue booting normally.

The firmware package is a zip file containing updated .py files (never
boot.py — that is the safety boundary and must remain stable across updates).

Required library in /lib/: zipfile.py from https://github.com/jonnor/micropython-zipfile
"""

import os
import hashlib
import microcontroller

BACKUP_DIR = "/backup"
OTA_PENDING_PATH = "/ota_pending"
# Must match boot._FIRMWARE_FILES.
_FIRMWARE_FILES = ("code.py", "ota.py", "captive.py", "sensor.py", "display.py", "mqtt_ha.py")
_CHUNK = 1024
_TMP_ZIP = "/fw_update.zip"


# ── Filesystem helpers ─────────────────────────────────────────────────────────


def _ensure_dir(path):
    try:
        os.mkdir(path)
    except OSError:
        pass


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _copy_file(src, dst):
    with open(src, "rb") as s, open(dst, "wb") as d:
        while True:
            chunk = s.read(_CHUNK)
            if not chunk:
                break
            d.write(chunk)


# ── OTA steps ──────────────────────────────────────────────────────────────────


def _backup_current():
    """Copy current firmware files to BACKUP_DIR."""
    _ensure_dir(BACKUP_DIR)
    for name in _FIRMWARE_FILES:
        try:
            _copy_file("/" + name, BACKUP_DIR + "/" + name)
        except OSError:
            pass  # file absent on a first-install device — skip


def _compute_sha256(path):
    """Return the lowercase hex SHA-256 digest of the file at *path*."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(_CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _download(session, url, dest_path):
    """Download *url* via *session* and write bytes to *dest_path*.

    Raises RuntimeError on non-200 status or network error.
    """
    try:
        response = session.get(url)
    except Exception as e:
        raise RuntimeError("Network error: " + str(e))
    if response.status_code != 200:
        raise RuntimeError("HTTP " + str(response.status_code))
    with open(dest_path, "wb") as f:
        f.write(response.content)


def _extract_zip(zip_path):
    """Extract all files from *zip_path* to the root of the filesystem."""
    import zipfile
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            print("[ota] Writing:", name)
            with open("/" + name, "wb") as f:
                f.write(zf.read(name))


# ── Public API ─────────────────────────────────────────────────────────────────


def apply(session, url, expected_sha256, version):
    """Download, verify, and apply a firmware update.

    Parameters
    ----------
    session : adafruit_requests.Session
        Active HTTP session — WiFi must already be connected.
    url : str
        Presigned URL to download the firmware zip from object storage.
    expected_sha256 : str
        Hex SHA-256 digest of the zip as stored on the server.
    version : str
        New firmware version string, written to /ota_pending before
        downloading so that boot.py can roll back on repeated crashes.

    On success calls microcontroller.reset() — never returns.
    On failure raises RuntimeError; the caller should continue booting.
    """
    print("[ota] Backing up current firmware...")
    _backup_current()

    # Write /ota_pending *before* downloading so that a crash mid-download
    # is caught by boot.py's boot-attempt counter.
    with open(OTA_PENDING_PATH, "w") as f:
        f.write(version)

    print("[ota] Downloading firmware...")
    try:
        _download(session, url, _TMP_ZIP)
    except RuntimeError as e:
        _remove(_TMP_ZIP)
        raise

    print("[ota] Verifying checksum...")
    actual = _compute_sha256(_TMP_ZIP)
    if actual != expected_sha256:
        _remove(_TMP_ZIP)
        raise RuntimeError(
            "SHA-256 mismatch: expected " + expected_sha256 + " got " + actual
        )

    print("[ota] Extracting firmware...")
    try:
        _extract_zip(_TMP_ZIP)
    except Exception as e:
        _remove(_TMP_ZIP)
        raise RuntimeError("Extraction failed: " + str(e))

    _remove(_TMP_ZIP)
    print("[ota] Update applied. Rebooting...")
    microcontroller.reset()
