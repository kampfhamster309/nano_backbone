"""
Host-runnable tests for mqtt_ha.py.
CircuitPython-specific modules are mocked via sys.modules before import.
Run with: python3 -m unittest discover -s example_firmware/tests
"""

import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, call, patch

# ── Mock CircuitPython / adafruit modules before importing mqtt_ha ─────────────
#
# When Python resolves `import adafruit_minimqtt.adafruit_minimqtt as mqtt`
# it accesses the `.adafruit_minimqtt` attribute on the parent mock rather
# than looking up sys.modules["adafruit_minimqtt.adafruit_minimqtt"] directly.
# Both must point to the same object so tests reference the real call target.

_mock_parent = MagicMock()
_mock_mqtt_module = MagicMock()
_mock_mqtt_class = MagicMock()
_mock_mqtt_module.MQTT = _mock_mqtt_class
_mock_parent.adafruit_minimqtt = _mock_mqtt_module  # wire parent → submodule

sys.modules["adafruit_minimqtt"] = _mock_parent
sys.modules["adafruit_minimqtt.adafruit_minimqtt"] = _mock_mqtt_module

_MQTT_HA_PATH = os.path.join(os.path.dirname(__file__), "..", "mqtt_ha.py")
_spec = importlib.util.spec_from_file_location("mqtt_ha_module", _MQTT_HA_PATH)
mqtt_ha_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mqtt_ha_module)


# ── Helpers ───────────────────────────────────────────────────────────────────

DEVICE_ID = "e6614c311b876134"
DEVICE_NAME = "Living Room Sensor"


def _make_client():
    client = MagicMock()
    client.is_connected.return_value = True
    return client


# ── Tests: setup() ─────────────────────────────────────────────────────────────

class TestSetup(unittest.TestCase):
    def setUp(self):
        _mock_mqtt_class.reset_mock()

    def test_creates_mqtt_client_with_broker_and_port(self):
        """setup() passes broker and port to MQTT()."""
        pool = MagicMock()
        mqtt_ha_module.setup(pool, "192.168.1.10", 1883)

        _, kwargs = _mock_mqtt_class.call_args
        self.assertEqual(kwargs["broker"], "192.168.1.10")
        self.assertEqual(kwargs["port"], 1883)

    def test_passes_socket_pool(self):
        """setup() passes the socket pool to MQTT()."""
        pool = MagicMock(name="pool")
        mqtt_ha_module.setup(pool, "broker", 1883)

        _, kwargs = _mock_mqtt_class.call_args
        self.assertIs(kwargs["socket_pool"], pool)

    def test_anonymous_when_no_credentials(self):
        """setup() passes username=None when user is absent."""
        mqtt_ha_module.setup(MagicMock(), "broker", 1883)

        _, kwargs = _mock_mqtt_class.call_args
        self.assertIsNone(kwargs["username"])

    def test_anonymous_when_empty_string_credentials(self):
        """setup() treats empty-string user as anonymous (None)."""
        mqtt_ha_module.setup(MagicMock(), "broker", 1883, user="", password="")

        _, kwargs = _mock_mqtt_class.call_args
        self.assertIsNone(kwargs["username"])

    def test_passes_credentials_when_provided(self):
        """setup() passes username and password when supplied."""
        mqtt_ha_module.setup(MagicMock(), "broker", 1883, user="alice", password="secret")

        _, kwargs = _mock_mqtt_class.call_args
        self.assertEqual(kwargs["username"], "alice")
        self.assertEqual(kwargs["password"], "secret")

    def test_uses_device_id_as_client_id(self):
        """setup() uses device_id as the MQTT client_id."""
        mqtt_ha_module.setup(MagicMock(), "broker", 1883, device_id=DEVICE_ID)

        _, kwargs = _mock_mqtt_class.call_args
        self.assertEqual(kwargs["client_id"], DEVICE_ID)

    def test_calls_connect(self):
        """setup() calls connect() on the newly created client."""
        mock_client = MagicMock()
        _mock_mqtt_class.return_value = mock_client

        mqtt_ha_module.setup(MagicMock(), "broker", 1883)

        mock_client.connect.assert_called_once()

    def test_returns_client(self):
        """setup() returns the MQTT client instance."""
        mock_client = MagicMock()
        _mock_mqtt_class.return_value = mock_client

        result = mqtt_ha_module.setup(MagicMock(), "broker", 1883)

        self.assertIs(result, mock_client)


# ── Tests: publish_discovery() ─────────────────────────────────────────────────

class TestPublishDiscovery(unittest.TestCase):
    def test_publishes_two_config_messages(self):
        """publish_discovery() publishes exactly two discovery payloads."""
        client = _make_client()
        mqtt_ha_module.publish_discovery(client, DEVICE_ID, DEVICE_NAME)

        self.assertEqual(client.publish.call_count, 2)

    def test_temperature_config_topic(self):
        """publish_discovery() sends temperature config to the correct topic."""
        client = _make_client()
        mqtt_ha_module.publish_discovery(client, DEVICE_ID, DEVICE_NAME)

        topics = [c.args[0] for c in client.publish.call_args_list]
        expected = f"homeassistant/sensor/{DEVICE_ID}/temperature/config"
        self.assertIn(expected, topics)

    def test_humidity_config_topic(self):
        """publish_discovery() sends humidity config to the correct topic."""
        client = _make_client()
        mqtt_ha_module.publish_discovery(client, DEVICE_ID, DEVICE_NAME)

        topics = [c.args[0] for c in client.publish.call_args_list]
        expected = f"homeassistant/sensor/{DEVICE_ID}/humidity/config"
        self.assertIn(expected, topics)

    def test_temperature_payload_fields(self):
        """Temperature discovery payload contains required HA fields."""
        client = _make_client()
        mqtt_ha_module.publish_discovery(client, DEVICE_ID, DEVICE_NAME)

        temp_call = next(
            c for c in client.publish.call_args_list
            if "temperature/config" in c.args[0]
        )
        payload = json.loads(temp_call.args[1])

        self.assertEqual(payload["device_class"], "temperature")
        self.assertEqual(payload["unit_of_measurement"], "°C")
        self.assertIn(DEVICE_ID, payload["unique_id"])
        self.assertIn("temperature", payload["state_topic"])

    def test_humidity_payload_fields(self):
        """Humidity discovery payload contains required HA fields."""
        client = _make_client()
        mqtt_ha_module.publish_discovery(client, DEVICE_ID, DEVICE_NAME)

        hum_call = next(
            c for c in client.publish.call_args_list
            if "humidity/config" in c.args[0]
        )
        payload = json.loads(hum_call.args[1])

        self.assertEqual(payload["device_class"], "humidity")
        self.assertEqual(payload["unit_of_measurement"], "%")
        self.assertIn(DEVICE_ID, payload["unique_id"])
        self.assertIn("humidity", payload["state_topic"])

    def test_device_block_contains_device_id_and_name(self):
        """Discovery payload device block carries device_id and device_name."""
        client = _make_client()
        mqtt_ha_module.publish_discovery(client, DEVICE_ID, DEVICE_NAME)

        for c in client.publish.call_args_list:
            payload = json.loads(c.args[1])
            self.assertIn(DEVICE_ID, payload["device"]["identifiers"])
            self.assertEqual(payload["device"]["name"], DEVICE_NAME)

    def test_config_messages_published_with_retain(self):
        """publish_discovery() sets retain=True on all config messages."""
        client = _make_client()
        mqtt_ha_module.publish_discovery(client, DEVICE_ID, DEVICE_NAME)

        for c in client.publish.call_args_list:
            self.assertTrue(c.kwargs.get("retain"))

    def test_unique_ids_are_unique(self):
        """Each sensor entity has a distinct unique_id."""
        client = _make_client()
        mqtt_ha_module.publish_discovery(client, DEVICE_ID, DEVICE_NAME)

        unique_ids = [
            json.loads(c.args[1])["unique_id"]
            for c in client.publish.call_args_list
        ]
        self.assertEqual(len(unique_ids), len(set(unique_ids)))


# ── Tests: publish_readings() ──────────────────────────────────────────────────

class TestPublishReadings(unittest.TestCase):
    def test_publishes_temperature_to_correct_topic(self):
        """publish_readings() publishes temperature to the state topic."""
        client = _make_client()
        mqtt_ha_module.publish_readings(client, DEVICE_ID, 21.5, 58.3)

        topics = [c.args[0] for c in client.publish.call_args_list]
        expected = f"homeassistant/sensor/{DEVICE_ID}/temperature/state"
        self.assertIn(expected, topics)

    def test_publishes_humidity_to_correct_topic(self):
        """publish_readings() publishes humidity to the state topic."""
        client = _make_client()
        mqtt_ha_module.publish_readings(client, DEVICE_ID, 21.5, 58.3)

        topics = [c.args[0] for c in client.publish.call_args_list]
        expected = f"homeassistant/sensor/{DEVICE_ID}/humidity/state"
        self.assertIn(expected, topics)

    def test_temperature_value_formatted(self):
        """publish_readings() formats temperature to one decimal place."""
        client = _make_client()
        mqtt_ha_module.publish_readings(client, DEVICE_ID, 21.5, 58.3)

        temp_call = next(
            c for c in client.publish.call_args_list
            if "temperature/state" in c.args[0]
        )
        self.assertEqual(temp_call.args[1], "21.5")

    def test_humidity_value_formatted(self):
        """publish_readings() formats humidity to one decimal place."""
        client = _make_client()
        mqtt_ha_module.publish_readings(client, DEVICE_ID, 21.5, 58.3)

        hum_call = next(
            c for c in client.publish.call_args_list
            if "humidity/state" in c.args[0]
        )
        self.assertEqual(hum_call.args[1], "58.3")

    def test_readings_published_with_retain(self):
        """publish_readings() sets retain=True on both state messages."""
        client = _make_client()
        mqtt_ha_module.publish_readings(client, DEVICE_ID, 21.5, 58.3)

        for c in client.publish.call_args_list:
            self.assertTrue(c.kwargs.get("retain"))

    def test_reconnects_when_disconnected(self):
        """publish_readings() calls reconnect() when not connected."""
        client = _make_client()
        client.is_connected.return_value = False

        mqtt_ha_module.publish_readings(client, DEVICE_ID, 21.5, 58.3)

        client.reconnect.assert_called_once()

    def test_no_reconnect_when_connected(self):
        """publish_readings() skips reconnect() when already connected."""
        client = _make_client()
        mqtt_ha_module.publish_readings(client, DEVICE_ID, 21.5, 58.3)

        client.reconnect.assert_not_called()

    def test_does_not_raise_on_publish_error(self):
        """publish_readings() swallows exceptions to keep the sensor loop alive."""
        client = _make_client()
        client.publish.side_effect = Exception("broker gone")

        # Should not raise
        mqtt_ha_module.publish_readings(client, DEVICE_ID, 21.5, 58.3)

    def test_publishes_two_messages(self):
        """publish_readings() publishes exactly two state messages."""
        client = _make_client()
        mqtt_ha_module.publish_readings(client, DEVICE_ID, 21.5, 58.3)

        self.assertEqual(client.publish.call_count, 2)


if __name__ == "__main__":
    unittest.main()
