"""
Host-runnable tests for the pure-Python logic in code.py.
CircuitPython-specific modules are mocked via sys.modules before import.
Run with: python3 -m pytest firmware/tests/ or python3 -m unittest discover firmware/tests/

Note: 'code' is a Python stdlib module, so we load firmware/code.py via importlib
to avoid shadowing the built-in.
"""
import sys
import os
import importlib.util
import unittest
from unittest.mock import MagicMock, call, patch

# Mock CircuitPython / hardware modules before importing code.py
for mod in (
    "board", "busio", "microcontroller", "time",
    "digitalio",
    "adafruit_esp32spi",
    "adafruit_esp32spi.adafruit_esp32spi",
    "adafruit_esp32spi.adafruit_esp32spi_socketpool",
    "adafruit_requests",
):
    sys.modules.setdefault(mod, MagicMock())

_CODE_PATH = os.path.join(os.path.dirname(__file__), "..", "code.py")
_spec = importlib.util.spec_from_file_location("firmware_code", _CODE_PATH)
firmware_code = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(firmware_code)


class TestSemverGt(unittest.TestCase):
    def test_patch_increment(self):
        self.assertTrue(firmware_code._semver_gt("1.0.1", "1.0.0"))

    def test_minor_increment(self):
        self.assertTrue(firmware_code._semver_gt("1.1.0", "1.0.9"))

    def test_major_increment(self):
        self.assertTrue(firmware_code._semver_gt("2.0.0", "1.9.9"))

    def test_equal_versions_returns_false(self):
        self.assertFalse(firmware_code._semver_gt("1.0.0", "1.0.0"))

    def test_older_version_returns_false(self):
        self.assertFalse(firmware_code._semver_gt("1.0.0", "1.0.1"))

    def test_invalid_a_returns_false(self):
        self.assertFalse(firmware_code._semver_gt("bad", "1.0.0"))

    def test_invalid_b_returns_false(self):
        self.assertFalse(firmware_code._semver_gt("1.0.0", "bad"))

    def test_v_prefix_stripped(self):
        self.assertTrue(firmware_code._semver_gt("v1.0.1", "v1.0.0"))


class TestConnectWifi(unittest.TestCase):
    def _make_esp(self):
        esp = MagicMock()
        esp.pretty_ip.return_value = "192.168.1.10"
        esp.ip_address = b"\xc0\xa8\x01\x0a"
        return esp

    def test_returns_true_on_first_attempt(self):
        esp = self._make_esp()
        self.assertTrue(firmware_code._connect_wifi(esp, "MySSID", "secret"))
        esp.connect_AP.assert_called_once()

    def test_retries_and_succeeds_on_second_attempt(self):
        esp = self._make_esp()
        esp.connect_AP.side_effect = [Exception("timeout"), None]
        self.assertTrue(firmware_code._connect_wifi(esp, "MySSID", "secret"))
        self.assertEqual(esp.connect_AP.call_count, 2)

    def test_returns_false_after_all_retries_exhausted(self):
        esp = self._make_esp()
        esp.connect_AP.side_effect = Exception("fail")
        self.assertFalse(firmware_code._connect_wifi(esp, "MySSID", "secret"))
        self.assertEqual(esp.connect_AP.call_count, firmware_code.WIFI_RETRIES)

    def test_empty_password_passes_empty_bytes(self):
        esp = self._make_esp()
        firmware_code._connect_wifi(esp, "OpenNet", "")
        esp.connect_AP.assert_called_once_with("OpenNet", b"")

    def test_none_password_passes_empty_bytes(self):
        esp = self._make_esp()
        firmware_code._connect_wifi(esp, "OpenNet", None)
        esp.connect_AP.assert_called_once_with("OpenNet", b"")


class TestCheckForUpdate(unittest.TestCase):
    def _make_session(self, status_code, json_data=None):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = json_data or {}
        session = MagicMock()
        session.get.return_value = response
        return session

    def test_returns_tuple_when_update_available(self):
        session = self._make_session(200, {
            "version": "1.0.1",
            "url": "http://example.com/fw.zip",
            "sha256": "deadbeef",
            "changelog": "Fix bug",
        })
        result = firmware_code._check_for_update(session, "http://srv:8000", "key", "1.0.0")
        self.assertIsNotNone(result)
        url, sha256, version = result
        self.assertEqual(version, "1.0.1")
        self.assertEqual(url, "http://example.com/fw.zip")
        self.assertEqual(sha256, "deadbeef")

    def test_returns_none_when_already_up_to_date(self):
        session = self._make_session(200, {
            "version": "1.0.0",
            "url": "http://example.com/fw.zip",
            "sha256": "deadbeef",
        })
        result = firmware_code._check_for_update(session, "http://srv:8000", "key", "1.0.0")
        self.assertIsNone(result)

    def test_returns_none_when_server_version_older(self):
        session = self._make_session(200, {
            "version": "0.9.0",
            "url": "http://example.com/fw.zip",
            "sha256": "deadbeef",
        })
        result = firmware_code._check_for_update(session, "http://srv:8000", "key", "1.0.0")
        self.assertIsNone(result)

    def test_returns_none_on_404(self):
        session = self._make_session(404)
        self.assertIsNone(
            firmware_code._check_for_update(session, "http://srv:8000", "key", "1.0.0")
        )

    def test_returns_none_on_unexpected_status(self):
        session = self._make_session(503)
        self.assertIsNone(
            firmware_code._check_for_update(session, "http://srv:8000", "key", "1.0.0")
        )

    def test_returns_none_on_connection_error(self):
        session = MagicMock()
        session.get.side_effect = Exception("Connection refused")
        self.assertIsNone(
            firmware_code._check_for_update(session, "http://srv:8000", "key", "1.0.0")
        )

    def test_constructs_correct_url(self):
        session = self._make_session(404)
        firmware_code._check_for_update(session, "http://srv:8000", "mykey", "1.0.0")
        session.get.assert_called_once_with(
            "http://srv:8000/api/v1/firmware/latest/",
            headers={"Authorization": "Api-Key mykey"},
        )

    def test_trailing_slash_on_server_url_is_normalised(self):
        session = self._make_session(404)
        firmware_code._check_for_update(session, "http://srv:8000/", "key", "1.0.0")
        called_url = session.get.call_args[0][0]
        self.assertEqual(called_url, "http://srv:8000/api/v1/firmware/latest/")


if __name__ == "__main__":
    unittest.main()
