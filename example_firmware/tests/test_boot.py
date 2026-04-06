"""
Host-runnable tests for the pure-Python helpers in boot.py.
CircuitPython-specific modules are mocked via sys.modules before import.
Run with: python3 -m unittest discover -s example_firmware/tests
"""

import importlib.util
import os
import sys
import unittest
from unittest.mock import MagicMock, patch, mock_open, call
import io

# ── Mock CircuitPython modules before importing boot ──────────────────────────

sys.modules.setdefault("storage", MagicMock())
sys.modules.setdefault("microcontroller", MagicMock())

# boot.py calls _run_ota_check() at import time; patch _file_exists to
# return False so no OTA logic runs during module load.
_BOOT_PATH = os.path.join(os.path.dirname(__file__), "..", "boot.py")

with patch("builtins.open", mock_open(read_data="")):
    _spec = importlib.util.spec_from_file_location("boot_module", _BOOT_PATH)
    boot_module = importlib.util.module_from_spec(_spec)
    with patch.object(
        # Prevent _run_ota_check() side-effects at import time.
        sys.modules["storage"], "remount"
    ):
        with patch("os.stat", side_effect=OSError):
            _spec.loader.exec_module(boot_module)


# ── Tests: _read_manifest() ───────────────────────────────────────────────────

class TestReadManifest(unittest.TestCase):
    def test_returns_files_from_manifest(self):
        """_read_manifest() parses the backed-up manifest line by line."""
        manifest_content = "code.py\nota.py\nled.py\nfirmware_manifest.txt\n"
        with patch("builtins.open", mock_open(read_data=manifest_content)):
            result = boot_module._read_manifest()
        self.assertEqual(result, ["code.py", "ota.py", "led.py", "firmware_manifest.txt"])

    def test_ignores_blank_lines(self):
        """_read_manifest() skips empty lines in the manifest."""
        manifest_content = "code.py\n\nota.py\n\n"
        with patch("builtins.open", mock_open(read_data=manifest_content)):
            result = boot_module._read_manifest()
        self.assertEqual(result, ["code.py", "ota.py"])

    def test_falls_back_when_manifest_missing(self):
        """_read_manifest() returns the hardcoded fallback when no manifest exists."""
        with patch("builtins.open", side_effect=OSError("not found")):
            result = boot_module._read_manifest()
        self.assertEqual(result, list(boot_module._FIRMWARE_FILES_FALLBACK))

    def test_falls_back_when_manifest_empty(self):
        """_read_manifest() returns the fallback when the manifest file is empty."""
        with patch("builtins.open", mock_open(read_data="")):
            result = boot_module._read_manifest()
        self.assertEqual(result, list(boot_module._FIRMWARE_FILES_FALLBACK))

    def test_reads_from_backup_directory(self):
        """_read_manifest() opens the manifest from the backup directory."""
        with patch("builtins.open", mock_open(read_data="code.py\n")) as m:
            boot_module._read_manifest()
        expected_path = boot_module._BACKUP_DIR + "/" + boot_module._MANIFEST
        m.assert_called_once_with(expected_path)


# ── Tests: _restore_backup() uses manifest ────────────────────────────────────

class TestRestoreBackup(unittest.TestCase):
    def test_restores_files_listed_in_manifest(self):
        """_restore_backup() copies every file named in the manifest."""
        manifest_files = ["code.py", "led.py", "firmware_manifest.txt"]

        with patch.object(boot_module, "_read_manifest", return_value=manifest_files):
            opened_paths = []

            def _track_open(path, mode="r"):
                opened_paths.append((path, mode))
                return io.BytesIO(b"data")

            with patch("builtins.open", side_effect=_track_open):
                boot_module._restore_backup()

        read_paths = [p for p, m in opened_paths if m == "rb"]
        self.assertCountEqual(
            read_paths,
            [boot_module._BACKUP_DIR + "/" + f for f in manifest_files],
        )

    def test_uses_fallback_when_no_manifest(self):
        """_restore_backup() falls back to _FIRMWARE_FILES_FALLBACK when manifest absent."""
        with patch.object(boot_module, "_read_manifest",
                          return_value=list(boot_module._FIRMWARE_FILES_FALLBACK)):
            opened_paths = []

            def _track_open(path, mode="r"):
                opened_paths.append((path, mode))
                return io.BytesIO(b"data")

            with patch("builtins.open", side_effect=_track_open):
                boot_module._restore_backup()

        read_paths = [p for p, m in opened_paths if m == "rb"]
        self.assertCountEqual(
            read_paths,
            [boot_module._BACKUP_DIR + "/" + f for f in boot_module._FIRMWARE_FILES_FALLBACK],
        )

    def test_skips_missing_backup_files_gracefully(self):
        """_restore_backup() continues if a backup file is absent."""
        with patch.object(boot_module, "_read_manifest", return_value=["missing.py"]):
            with patch("builtins.open", side_effect=OSError("not found")):
                boot_module._restore_backup()  # must not raise


if __name__ == "__main__":
    unittest.main()
