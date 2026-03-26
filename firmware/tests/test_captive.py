"""
Host-runnable tests for the pure-Python logic in captive.py.
CircuitPython-specific modules (wifi, socketpool, microcontroller) are mocked.
Run with: python3 -m pytest firmware/tests/ or python3 -m unittest discover firmware/tests/
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Mock CircuitPython / hardware modules before importing captive
for mod in (
    "board", "busio", "microcontroller", "time",
    "digitalio",
    "adafruit_esp32spi",
    "adafruit_esp32spi.adafruit_esp32spi",
):
    sys.modules.setdefault(mod, MagicMock())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import captive


class TestUrlDecode(unittest.TestCase):
    def test_plain_text_unchanged(self):
        self.assertEqual(captive._url_decode("hello"), "hello")

    def test_plus_becomes_space(self):
        self.assertEqual(captive._url_decode("hello+world"), "hello world")

    def test_percent_encoded_space(self):
        self.assertEqual(captive._url_decode("hello%20world"), "hello world")

    def test_percent_encoded_at_sign(self):
        self.assertEqual(captive._url_decode("user%40example.com"), "user@example.com")

    def test_percent_encoded_url(self):
        self.assertEqual(
            captive._url_decode("http%3A%2F%2Flocalhost%3A8000"),
            "http://localhost:8000",
        )

    def test_invalid_percent_sequence_passed_through(self):
        self.assertEqual(captive._url_decode("%ZZ"), "%ZZ")

    def test_empty_string(self):
        self.assertEqual(captive._url_decode(""), "")


class TestParseForm(unittest.TestCase):
    def test_basic_key_value(self):
        self.assertEqual(
            captive._parse_form("ssid=MyWifi&password=secret"),
            {"ssid": "MyWifi", "password": "secret"},
        )

    def test_url_encoded_server_url(self):
        result = captive._parse_form(
            "server_url=http%3A%2F%2F192.168.1.1%3A8000&api_key=abc123"
        )
        self.assertEqual(result["server_url"], "http://192.168.1.1:8000")
        self.assertEqual(result["api_key"], "abc123")

    def test_empty_password_field(self):
        result = captive._parse_form(
            "ssid=Net&password=&server_url=http%3A%2F%2Fx&api_key=k"
        )
        self.assertEqual(result["password"], "")

    def test_missing_value_ignored(self):
        result = captive._parse_form("ssid=Net&badentry&api_key=k")
        self.assertNotIn("badentry", result)
        self.assertEqual(result["ssid"], "Net")


class TestWriteSettings(unittest.TestCase):
    def _capture_write(self, ssid, password, server_url, api_key):
        written = []

        class _FakeFile:
            def write(self, s):
                written.append(s)
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass

        with patch("builtins.open", lambda path, mode: _FakeFile()):
            captive._write_settings(ssid, password, server_url, api_key)

        return "".join(written)

    def test_all_fields_present(self):
        content = self._capture_write("MySSID", "MyPass", "http://srv:8000", "key123")
        self.assertIn('WIFI_SSID = "MySSID"', content)
        self.assertIn('WIFI_PASSWORD = "MyPass"', content)
        self.assertIn('SERVER_URL = "http://srv:8000"', content)
        self.assertIn('DEVICE_API_KEY = "key123"', content)
        self.assertIn('CURRENT_VERSION = "0.0.0"', content)

    def test_escapes_double_quote_in_value(self):
        content = self._capture_write('my"ssid', "pass", "http://srv", "key")
        self.assertIn(r'WIFI_SSID = "my\"ssid"', content)

    def test_escapes_backslash_in_value(self):
        content = self._capture_write("ssid", "pass\\word", "http://srv", "key")
        self.assertIn(r'WIFI_PASSWORD = "pass\\word"', content)

    def test_writes_to_settings_toml_path(self):
        opened_paths = []

        class _FakeFile:
            def write(self, s):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass

        def _fake_open(path, mode):
            opened_paths.append(path)
            return _FakeFile()

        with patch("builtins.open", _fake_open):
            captive._write_settings("s", "p", "u", "k")

        self.assertEqual(opened_paths, ["/settings.toml"])


if __name__ == "__main__":
    unittest.main()
