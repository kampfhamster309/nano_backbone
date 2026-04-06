"""
Host-runnable tests for the pure-Python logic in captive.py.
CircuitPython-specific modules are mocked via sys.modules before import.
Run with: python3 -m unittest discover -s example_firmware/tests
"""

import importlib.util
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# ── Mock CircuitPython / hardware modules before importing captive ─────────────

for mod in (
    "board", "busio", "microcontroller", "time",
    "digitalio",
    "adafruit_esp32spi",
    "adafruit_esp32spi.adafruit_esp32spi",
):
    sys.modules.setdefault(mod, MagicMock())

_CAPTIVE_PATH = os.path.join(os.path.dirname(__file__), "..", "captive.py")
_spec = importlib.util.spec_from_file_location("captive_module", _CAPTIVE_PATH)
captive_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(captive_module)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _capture_write(ssid="net", password="pass", server_url="http://srv:8000",
                   api_key="key", mqtt_broker="192.168.1.10", mqtt_port="1883",
                   mqtt_user="", mqtt_password="", device_name="Test Sensor",
                   poll_interval="30"):
    """Call _write_settings and return the written content as a string."""
    written = []

    class _FakeFile:
        def write(self, s):
            written.append(s)
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    with patch("builtins.open", lambda path, mode: _FakeFile()):
        captive_module._write_settings(
            ssid, password, server_url, api_key,
            mqtt_broker, mqtt_port, mqtt_user, mqtt_password,
            device_name, poll_interval,
        )
    return "".join(written)


# ── Tests: _url_decode() ──────────────────────────────────────────────────────

class TestUrlDecode(unittest.TestCase):
    def test_plain_text_unchanged(self):
        self.assertEqual(captive_module._url_decode("hello"), "hello")

    def test_plus_becomes_space(self):
        self.assertEqual(captive_module._url_decode("hello+world"), "hello world")

    def test_percent_encoded_space(self):
        self.assertEqual(captive_module._url_decode("hello%20world"), "hello world")

    def test_percent_encoded_at_sign(self):
        self.assertEqual(captive_module._url_decode("user%40example.com"), "user@example.com")

    def test_percent_encoded_url(self):
        self.assertEqual(
            captive_module._url_decode("http%3A%2F%2Flocalhost%3A8000"),
            "http://localhost:8000",
        )

    def test_invalid_percent_sequence_passed_through(self):
        self.assertEqual(captive_module._url_decode("%ZZ"), "%ZZ")

    def test_empty_string(self):
        self.assertEqual(captive_module._url_decode(""), "")


# ── Tests: _parse_form() ──────────────────────────────────────────────────────

class TestParseForm(unittest.TestCase):
    def test_basic_key_value(self):
        self.assertEqual(
            captive_module._parse_form("ssid=MyWifi&password=secret"),
            {"ssid": "MyWifi", "password": "secret"},
        )

    def test_url_encoded_server_url(self):
        result = captive_module._parse_form(
            "server_url=http%3A%2F%2F192.168.1.1%3A8000&api_key=abc123"
        )
        self.assertEqual(result["server_url"], "http://192.168.1.1:8000")

    def test_empty_optional_fields(self):
        result = captive_module._parse_form(
            "ssid=Net&password=&mqtt_user=&mqtt_password="
        )
        self.assertEqual(result["password"], "")
        self.assertEqual(result["mqtt_user"], "")
        self.assertEqual(result["mqtt_password"], "")

    def test_all_new_fields_parsed(self):
        body = (
            "ssid=Net&password=pw&server_url=http%3A%2F%2Fx&api_key=k"
            "&mqtt_broker=192.168.1.10&mqtt_port=1883"
            "&mqtt_user=alice&mqtt_password=secret"
            "&device_name=Living+Room+Sensor&poll_interval=30"
        )
        result = captive_module._parse_form(body)
        self.assertEqual(result["mqtt_broker"], "192.168.1.10")
        self.assertEqual(result["mqtt_port"], "1883")
        self.assertEqual(result["mqtt_user"], "alice")
        self.assertEqual(result["mqtt_password"], "secret")
        self.assertEqual(result["device_name"], "Living Room Sensor")
        self.assertEqual(result["poll_interval"], "30")

    def test_missing_value_ignored(self):
        result = captive_module._parse_form("ssid=Net&badentry&api_key=k")
        self.assertNotIn("badentry", result)


# ── Tests: _write_settings() ──────────────────────────────────────────────────

class TestWriteSettings(unittest.TestCase):
    def test_wifi_fields_written(self):
        content = _capture_write(ssid="MySSID", password="MyPass")
        self.assertIn('WIFI_SSID = "MySSID"', content)
        self.assertIn('WIFI_PASSWORD = "MyPass"', content)

    def test_server_fields_written(self):
        content = _capture_write(server_url="http://srv:8000", api_key="key123")
        self.assertIn('SERVER_URL = "http://srv:8000"', content)
        self.assertIn('DEVICE_API_KEY = "key123"', content)

    def test_current_version_initialised_to_zero(self):
        content = _capture_write()
        self.assertIn('CURRENT_VERSION = "0.0.0"', content)

    def test_mqtt_broker_written(self):
        content = _capture_write(mqtt_broker="192.168.1.10")
        self.assertIn('MQTT_BROKER = "192.168.1.10"', content)

    def test_mqtt_port_written_as_integer(self):
        content = _capture_write(mqtt_port="1883")
        self.assertIn("MQTT_PORT = 1883", content)
        # Must not be quoted
        self.assertNotIn('MQTT_PORT = "1883"', content)

    def test_mqtt_credentials_written(self):
        content = _capture_write(mqtt_user="alice", mqtt_password="secret")
        self.assertIn('MQTT_USER = "alice"', content)
        self.assertIn('MQTT_PASSWORD = "secret"', content)

    def test_empty_mqtt_credentials_written_as_empty_string(self):
        content = _capture_write(mqtt_user="", mqtt_password="")
        self.assertIn('MQTT_USER = ""', content)
        self.assertIn('MQTT_PASSWORD = ""', content)

    def test_device_name_written(self):
        content = _capture_write(device_name="Living Room Sensor")
        self.assertIn('DEVICE_NAME = "Living Room Sensor"', content)

    def test_poll_interval_written_as_integer(self):
        content = _capture_write(poll_interval="30")
        self.assertIn("POLL_INTERVAL = 30", content)
        self.assertNotIn('POLL_INTERVAL = "30"', content)

    def test_all_eleven_keys_present(self):
        content = _capture_write()
        expected_keys = (
            "WIFI_SSID", "WIFI_PASSWORD", "SERVER_URL", "DEVICE_API_KEY",
            "CURRENT_VERSION", "MQTT_BROKER", "MQTT_PORT", "MQTT_USER",
            "MQTT_PASSWORD", "DEVICE_NAME", "POLL_INTERVAL",
        )
        for key in expected_keys:
            self.assertIn(key, content, f"Missing key: {key}")

    def test_escapes_double_quote_in_ssid(self):
        content = _capture_write(ssid='my"ssid')
        self.assertIn(r'WIFI_SSID = "my\"ssid"', content)

    def test_escapes_backslash_in_password(self):
        content = _capture_write(password="pass\\word")
        self.assertIn(r'WIFI_PASSWORD = "pass\\word"', content)

    def test_escapes_special_chars_in_device_name(self):
        content = _capture_write(device_name='Sensor "A"')
        self.assertIn(r'DEVICE_NAME = "Sensor \"A\""', content)

    def test_writes_to_settings_toml_path(self):
        opened_paths = []

        class _FakeFile:
            def write(self, s):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass

        with patch("builtins.open", lambda path, mode: (opened_paths.append(path), _FakeFile())[1]):
            captive_module._write_settings(
                "s", "p", "u", "k", "broker", "1883", "", "", "name", "30"
            )

        self.assertEqual(opened_paths, ["/settings.toml"])

    def test_default_mqtt_port_when_empty(self):
        """If mqtt_port is falsy, defaults to 1883."""
        content = _capture_write(mqtt_port="")
        self.assertIn("MQTT_PORT = 1883", content)

    def test_default_poll_interval_when_empty(self):
        """If poll_interval is falsy, defaults to 30."""
        content = _capture_write(poll_interval="")
        self.assertIn("POLL_INTERVAL = 30", content)


if __name__ == "__main__":
    unittest.main()
