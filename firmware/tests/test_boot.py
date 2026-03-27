"""
Host-runnable tests for the OTA rollback logic in boot.py.
CircuitPython-specific modules are mocked via sys.modules before import.
Run with: python3 -m unittest discover firmware/tests/

Strategy: boot.py calls _run_ota_check() at module level. We load it via
importlib (with filesystem mocked to a no-OTA-pending state) and then call
_run_ota_check() directly in each test scenario with specific mocks.
"""
import importlib.util
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch, mock_open, call

# Mock CircuitPython-only modules
for mod in ("storage", "microcontroller"):
    sys.modules.setdefault(mod, MagicMock())

_BOOT_PATH = os.path.join(os.path.dirname(__file__), "..", "boot.py")


def _load_boot():
    """Load a fresh copy of boot.py with _file_exists returning False,
    so the module-level _run_ota_check() is a no-op (no pending OTA)."""
    spec = importlib.util.spec_from_file_location("boot_module", _BOOT_PATH)
    mod = importlib.util.module_from_spec(spec)
    with patch("os.stat", side_effect=OSError), \
         patch("os.listdir", side_effect=OSError):
        spec.loader.exec_module(mod)
    return mod


# Load once; individual tests call boot._run_ota_check() with their own mocks.
boot = _load_boot()


class TestFileHelpers(unittest.TestCase):
    def test_file_exists_true(self):
        with tempfile.NamedTemporaryFile() as f:
            self.assertTrue(boot._file_exists(f.name))

    def test_file_exists_false(self):
        self.assertFalse(boot._file_exists("/no/such/path/xyz"))

    def test_read_int_valid(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("3\n")
            tmp = f.name
        try:
            self.assertEqual(boot._read_int(tmp), 3)
        finally:
            os.remove(tmp)

    def test_read_int_missing_file(self):
        self.assertEqual(boot._read_int("/nonexistent"), 0)

    def test_read_int_bad_content(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("not-a-number\n")
            tmp = f.name
        try:
            self.assertEqual(boot._read_int(tmp), 0)
        finally:
            os.remove(tmp)

    def test_write_int_then_read_int(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            tmp = f.name
        try:
            boot._write_int(tmp, 7)
            self.assertEqual(boot._read_int(tmp), 7)
        finally:
            os.remove(tmp)

    def test_read_text_existing(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("  1.0.1  \n")
            tmp = f.name
        try:
            self.assertEqual(boot._read_text(tmp), "1.0.1")
        finally:
            os.remove(tmp)

    def test_read_text_missing(self):
        self.assertEqual(boot._read_text("/nonexistent"), "")

    def test_remove_existing_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp = f.name
        boot._remove(tmp)
        self.assertFalse(os.path.exists(tmp))

    def test_remove_nonexistent_does_not_raise(self):
        boot._remove("/no/such/file/xyz")  # must not raise


class TestOtaCheck_NoPending(unittest.TestCase):
    def test_no_ota_pending_cleans_up_stale_backup(self):
        cleanup_called = []
        with patch.object(boot, "_file_exists", return_value=False), \
             patch.object(boot, "_cleanup_backup", side_effect=lambda: cleanup_called.append(True)):
            boot._run_ota_check()
        self.assertTrue(cleanup_called)


class TestOtaCheck_FirstAttempt(unittest.TestCase):
    def test_increments_boot_attempt_counter(self):
        written = {}

        def fake_write_int(path, n):
            written[path] = n

        with patch.object(boot, "_file_exists", return_value=True), \
             patch.object(boot, "_read_int", return_value=0), \
             patch.object(boot, "_write_int", side_effect=fake_write_int):
            boot._run_ota_check()

        self.assertEqual(written[boot._BOOT_ATTEMPTS], 1)

    def test_does_not_rollback_on_first_attempt(self):
        with patch.object(boot, "_file_exists", return_value=True), \
             patch.object(boot, "_read_int", return_value=0), \
             patch.object(boot, "_write_int"), \
             patch.object(boot, "_restore_backup") as mock_restore:
            boot._run_ota_check()
        mock_restore.assert_not_called()


class TestOtaCheck_ThresholdReached(unittest.TestCase):
    """boot_attempts is already at _MAX_BOOT_ATTEMPTS; next increment triggers rollback."""

    def _run_rollback_scenario(self):
        reset_mock = sys.modules["microcontroller"].reset
        reset_mock.reset_mock()
        opened = {}

        class _FakeFile:
            def write(self, s):
                opened["written"] = s
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass

        with patch.object(boot, "_file_exists", return_value=True), \
             patch.object(boot, "_read_int", return_value=boot._MAX_BOOT_ATTEMPTS), \
             patch.object(boot, "_read_text", return_value="1.0.1"), \
             patch.object(boot, "_restore_backup") as mock_restore, \
             patch.object(boot, "_remove"), \
             patch.object(boot, "_cleanup_backup"), \
             patch("builtins.open", lambda p, m: _FakeFile()):
            boot._run_ota_check()

        return reset_mock, mock_restore, opened

    def test_restores_backup(self):
        _, mock_restore, _ = self._run_rollback_scenario()
        mock_restore.assert_called_once()

    def test_resets_device(self):
        reset_mock, _, _ = self._run_rollback_scenario()
        reset_mock.assert_called_once()

    def test_writes_rollback_completed_with_version(self):
        _, _, opened = self._run_rollback_scenario()
        self.assertEqual(opened.get("written"), "1.0.1")

    def test_removes_ota_pending_and_boot_attempts(self):
        removed = []
        reset_mock = sys.modules["microcontroller"].reset
        reset_mock.reset_mock()

        class _FakeFile:
            def write(self, s):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass

        with patch.object(boot, "_file_exists", return_value=True), \
             patch.object(boot, "_read_int", return_value=boot._MAX_BOOT_ATTEMPTS), \
             patch.object(boot, "_read_text", return_value="1.0.1"), \
             patch.object(boot, "_restore_backup"), \
             patch.object(boot, "_remove", side_effect=removed.append), \
             patch.object(boot, "_cleanup_backup"), \
             patch("builtins.open", lambda p, m: _FakeFile()):
            boot._run_ota_check()

        self.assertIn(boot._OTA_PENDING, removed)
        self.assertIn(boot._BOOT_ATTEMPTS, removed)


if __name__ == "__main__":
    unittest.main()
