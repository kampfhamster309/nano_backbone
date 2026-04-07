"""
boot.py — runs before code.py on every reset.

Responsibilities:
  1. Remount the filesystem as writable (required for OTA and settings writes).
  2. Detect an in-progress OTA update (/ota_pending) and track boot attempts.
     - If the new firmware boots successfully, code.py reports success and
       cleans up the flag files.
     - If the device crashes repeatedly, restore the backup after
       _MAX_BOOT_ATTEMPTS failures and flag /rollback_completed for code.py
       to report to the server once WiFi is available.

NOTE: No network I/O here — this module must work even if the firmware is
broken enough to prevent WiFi initialisation.
"""

import storage
import os

storage.remount("/", readonly=False)

_OTA_PENDING = "/ota_pending"
_BOOT_ATTEMPTS = "/boot_attempts"
_BACKUP_DIR = "/backup"
_ROLLBACK_DONE = "/rollback_completed"
_MAX_BOOT_ATTEMPTS = 3
_CHUNK = 1024
_MANIFEST = "firmware_manifest.txt"
# Fallback used only when no manifest exists in the backup (i.e. the device
# has never received an OTA update that carried a firmware_manifest.txt).
_FIRMWARE_FILES_FALLBACK = ("code.py", "ota.py", "captive.py")


# ── Filesystem helpers ─────────────────────────────────────────────────────────


def _file_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _read_int(path):
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0


def _write_int(path, n):
    with open(path, "w") as f:
        f.write(str(n))


def _read_text(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _read_manifest():
    """Return the list of firmware filenames from the backed-up manifest.

    Falls back to _FIRMWARE_FILES_FALLBACK if no manifest was included in the
    backup (i.e. the device has never received a manifest-aware OTA update).
    """
    try:
        with open(_BACKUP_DIR + "/" + _MANIFEST) as f:
            files = [line.strip() for line in f.readlines() if line.strip()]
        if files:
            return files
    except OSError:
        pass
    return list(_FIRMWARE_FILES_FALLBACK)


def _restore_backup():
    """Overwrite current firmware files with the backed-up copies."""
    for name in _read_manifest():
        src = _BACKUP_DIR + "/" + name
        dst = "/" + name
        try:
            with open(src, "rb") as s, open(dst, "wb") as d:
                while True:
                    chunk = s.read(_CHUNK)
                    if not chunk:
                        break
                    d.write(chunk)
        except OSError:
            pass  # backup file absent — skip


def _cleanup_backup():
    """Delete the /backup directory and all its contents."""
    try:
        for name in os.listdir(_BACKUP_DIR):
            _remove(_BACKUP_DIR + "/" + name)
        os.rmdir(_BACKUP_DIR)
    except OSError:
        pass


# ── OTA boot check ─────────────────────────────────────────────────────────────


def _run_ota_check():
    if _file_exists(_OTA_PENDING):
        attempts = _read_int(_BOOT_ATTEMPTS) + 1
        if attempts > _MAX_BOOT_ATTEMPTS:
            print(
                "[boot] OTA failed after",
                _MAX_BOOT_ATTEMPTS,
                "attempts. Rolling back...",
            )
            version = _read_text(_OTA_PENDING)
            _restore_backup()
            _remove(_OTA_PENDING)
            _remove(_BOOT_ATTEMPTS)
            _cleanup_backup()
            # Write the failed version into the flag so code.py can include
            # it in the update_failed event payload once WiFi is available.
            with open(_ROLLBACK_DONE, "w") as f:
                f.write(version)
            import microcontroller
            microcontroller.reset()
        else:
            print(
                "[boot] OTA pending — boot attempt",
                attempts,
                "/",
                _MAX_BOOT_ATTEMPTS,
            )
            _write_int(_BOOT_ATTEMPTS, attempts)
    else:
        # No pending OTA — remove any stale backup from a previous update
        # that succeeded but whose cleanup was interrupted.
        _cleanup_backup()


_run_ota_check()
