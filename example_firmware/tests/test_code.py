"""
Host-runnable tests for code.py.
CircuitPython-specific modules are mocked via sys.modules before import.
Run with: python3 -m unittest discover -s example_firmware/tests
"""

import importlib.util
import os
import sys
import unittest
from unittest.mock import MagicMock, patch, call

# ── Mock all CircuitPython / hardware modules ─────────────────────────────────

_mock_microcontroller = MagicMock()
_mock_microcontroller.cpu.uid = b"\xe6aL1\x1b\x87a4"  # deterministic fake UID

for mod in (
    "board", "busio", "time", "digitalio",
    "adafruit_esp32spi",
    "adafruit_esp32spi.adafruit_esp32spi",
    "adafruit_esp32spi.adafruit_esp32spi_socketpool",
    "adafruit_requests",
    "adafruit_ahtx0",
    "adafruit_ssd1306",
    "adafruit_framebuf",
):
    sys.modules.setdefault(mod, MagicMock())

sys.modules["microcontroller"] = _mock_microcontroller

# mqtt_ha and its deps must be in sys.modules before code.py is loaded
_mock_mqtt_ha = MagicMock()
sys.modules["mqtt_ha"] = _mock_mqtt_ha

_mock_sensor = MagicMock()
sys.modules["sensor"] = _mock_sensor

_mock_display = MagicMock()
sys.modules["display"] = _mock_display

# minimqtt mock (needed transitively)
_mock_mqtt_parent = MagicMock()
_mock_mqtt_submod = MagicMock()
_mock_mqtt_parent.adafruit_minimqtt = _mock_mqtt_submod
sys.modules.setdefault("adafruit_minimqtt", _mock_mqtt_parent)
sys.modules.setdefault("adafruit_minimqtt.adafruit_minimqtt", _mock_mqtt_submod)

_CODE_PATH = os.path.join(os.path.dirname(__file__), "..", "code.py")
_spec = importlib.util.spec_from_file_location("code_module", _CODE_PATH)
code_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(code_module)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_session():
    session = MagicMock()
    session._socket_pool = MagicMock()
    return session


# ── Tests: DEVICE_ID ──────────────────────────────────────────────────────────

class TestDeviceId(unittest.TestCase):
    def test_device_id_is_hex_string(self):
        """DEVICE_ID is a non-empty hex string derived from the chip UID."""
        self.assertIsInstance(code_module.DEVICE_ID, str)
        self.assertTrue(len(code_module.DEVICE_ID) > 0)
        int(code_module.DEVICE_ID, 16)  # raises ValueError if not valid hex

    def test_device_id_matches_uid_hex(self):
        """DEVICE_ID equals the hex encoding of microcontroller.cpu.uid."""
        import binascii
        expected = binascii.hexlify(_mock_microcontroller.cpu.uid).decode()
        self.assertEqual(code_module.DEVICE_ID, expected)


# ── Tests: _semver_gt() ───────────────────────────────────────────────────────

class TestSemverGt(unittest.TestCase):
    def test_greater_patch(self):
        self.assertTrue(code_module._semver_gt("1.0.1", "1.0.0"))

    def test_greater_minor(self):
        self.assertTrue(code_module._semver_gt("1.1.0", "1.0.9"))

    def test_greater_major(self):
        self.assertTrue(code_module._semver_gt("2.0.0", "1.9.9"))

    def test_equal_returns_false(self):
        self.assertFalse(code_module._semver_gt("1.0.0", "1.0.0"))

    def test_lesser_returns_false(self):
        self.assertFalse(code_module._semver_gt("0.9.9", "1.0.0"))

    def test_bad_input_returns_false(self):
        self.assertFalse(code_module._semver_gt("bad", "1.0.0"))
        self.assertFalse(code_module._semver_gt("1.0.0", "bad"))


# ── Tests: _run_app() — hardware init ─────────────────────────────────────────

class TestRunAppHardwareInit(unittest.TestCase):
    def setUp(self):
        _mock_sensor.reset_mock()
        _mock_display.reset_mock()
        _mock_mqtt_ha.reset_mock()
        sys.modules["busio"].I2C.reset_mock()
        sys.modules["board"].SCL = MagicMock()
        sys.modules["board"].SDA = MagicMock()

    def _run(self, session=None, pool=None, device_name="Test", poll_interval=0):
        """Run _run_app for one loop iteration then break via side_effect."""
        call_count = [0]

        def _fake_sleep(t):
            call_count[0] += 1
            if call_count[0] >= 1:
                raise StopIteration

        with patch.object(sys.modules["time"], "sleep", side_effect=_fake_sleep):
            try:
                code_module._run_app(session, pool, device_name, poll_interval)
            except StopIteration:
                pass

    def test_initialises_i2c_bus(self):
        """_run_app() creates an I2C bus on board.SCL / board.SDA."""
        self._run()
        sys.modules["busio"].I2C.assert_called()

    def test_initialises_sensor(self):
        """_run_app() calls sensor.setup() with the I2C bus."""
        self._run()
        _mock_sensor.setup.assert_called_once()

    def test_initialises_display(self):
        """_run_app() calls display.setup() with the I2C bus."""
        self._run()
        _mock_display.setup.assert_called_once()

    def test_reads_sensor_each_iteration(self):
        """_run_app() calls sensor.read() on every loop iteration."""
        _mock_sensor.read.return_value = (21.5, 58.3)
        self._run()
        _mock_sensor.read.assert_called()

    def test_updates_display_each_iteration(self):
        """_run_app() calls display.show() on every loop iteration."""
        _mock_sensor.read.return_value = (21.5, 58.3)
        self._run()
        _mock_display.show.assert_called()

    def test_display_receives_sensor_values(self):
        """_run_app() passes temperature and humidity from sensor to display."""
        _mock_sensor.read.return_value = (21.5, 58.3)
        self._run()
        args = _mock_display.show.call_args.args
        self.assertAlmostEqual(args[1], 21.5)
        self.assertAlmostEqual(args[2], 58.3)


# ── Tests: _run_app() — MQTT behaviour ────────────────────────────────────────

class TestRunAppMqtt(unittest.TestCase):
    def setUp(self):
        _mock_sensor.reset_mock()
        _mock_display.reset_mock()
        _mock_mqtt_ha.reset_mock()
        sys.modules["busio"].I2C.reset_mock()
        # reset_mock() does not clear side_effect on child mocks — do it explicitly
        # to prevent exhausted iterators or injected exceptions leaking between tests.
        _mock_sensor.read.side_effect = None
        _mock_mqtt_ha.setup.side_effect = None
        _mock_sensor.read.return_value = (20.0, 50.0)

    def _run(self, session=None, pool=None, device_name="Test", poll_interval=0):
        call_count = [0]

        def _fake_sleep(t):
            call_count[0] += 1
            if call_count[0] >= 1:
                raise StopIteration

        with patch.object(sys.modules["time"], "sleep", side_effect=_fake_sleep):
            try:
                code_module._run_app(session, pool, device_name, poll_interval)
            except StopIteration:
                pass

    def test_skips_mqtt_when_no_pool(self):
        """_run_app() does not touch mqtt_ha at all when pool is None."""
        self._run(pool=None)
        _mock_mqtt_ha.setup.assert_not_called()
        _mock_mqtt_ha.publish_discovery.assert_not_called()
        _mock_mqtt_ha.publish_readings.assert_not_called()

    def test_sets_up_mqtt_with_pool(self):
        """_run_app() passes pool directly to mqtt_ha.setup()."""
        env = {
            "MQTT_BROKER": "192.168.1.10",
            "MQTT_PORT": "1883",
            "MQTT_USER": "",
            "MQTT_PASSWORD": "",
        }
        mock_pool = MagicMock(name="pool")
        with patch.object(sys.modules["os"], "getenv", lambda k, d="": env.get(k, d)):
            self._run(pool=mock_pool)
        args = _mock_mqtt_ha.setup.call_args.args
        self.assertIs(args[0], mock_pool)

    def test_publishes_discovery_once_per_boot(self):
        """_run_app() calls mqtt_ha.publish_discovery() exactly once."""
        env = {
            "MQTT_BROKER": "192.168.1.10",
            "MQTT_PORT": "1883",
            "MQTT_USER": "",
            "MQTT_PASSWORD": "",
        }
        with patch.object(sys.modules["os"], "getenv", lambda k, d="": env.get(k, d)):
            self._run(pool=MagicMock(), device_name="Living Room")
        _mock_mqtt_ha.publish_discovery.assert_called_once_with(
            _mock_mqtt_ha.setup.return_value,
            code_module.DEVICE_ID,
            "Living Room",
        )

    def test_publishes_readings_each_iteration(self):
        """_run_app() calls mqtt_ha.publish_readings() on every loop iteration."""
        env = {
            "MQTT_BROKER": "192.168.1.10",
            "MQTT_PORT": "1883",
            "MQTT_USER": "",
            "MQTT_PASSWORD": "",
        }
        with patch.object(sys.modules["os"], "getenv", lambda k, d="": env.get(k, d)):
            self._run(pool=MagicMock())
        _mock_mqtt_ha.publish_readings.assert_called()

    def test_continues_without_mqtt_on_setup_failure(self):
        """_run_app() falls back to display-only if MQTT setup raises."""
        _mock_mqtt_ha.setup.side_effect = Exception("broker unreachable")
        env = {"MQTT_BROKER": "bad-host", "MQTT_PORT": "1883"}
        with patch.object(sys.modules["os"], "getenv", lambda k, d="": env.get(k, d)):
            self._run(pool=MagicMock())
        _mock_display.show.assert_called()
        _mock_mqtt_ha.setup.side_effect = None

    def test_clears_devices_on_oserror(self):
        """_run_app() deinits I2C and clears device refs after OSError."""
        mock_i2c = MagicMock()
        sys.modules["busio"].I2C.return_value = mock_i2c
        # First call raises OSError; subsequent calls succeed so the loop can end.
        _mock_sensor.read.side_effect = [OSError(19, "ENODEV"), (20.0, 50.0)]

        # Allow two sleep calls so the loop runs the error path then one clean iter.
        call_count = [0]
        def _fake_sleep(t):
            call_count[0] += 1
            if call_count[0] >= 2:
                raise StopIteration

        with patch.object(sys.modules["time"], "sleep", side_effect=_fake_sleep):
            try:
                code_module._run_app(None, None, "Test", 0)
            except StopIteration:
                pass

        mock_i2c.deinit.assert_called()

    def test_reinit_attempted_after_oserror(self):
        """_run_app() attempts I2C reinit on the next cycle after an OSError."""
        mock_i2c = MagicMock()
        sys.modules["busio"].I2C.return_value = mock_i2c
        _mock_sensor.read.side_effect = [OSError(19, "ENODEV"), (20.0, 50.0)]

        call_count = [0]
        def _fake_sleep(t):
            call_count[0] += 1
            if call_count[0] >= 2:
                raise StopIteration

        with patch.object(sys.modules["time"], "sleep", side_effect=_fake_sleep):
            try:
                code_module._run_app(None, None, "Test", 0)
            except StopIteration:
                pass

        # I2C should have been created at least twice: initial + reinit after error.
        self.assertGreaterEqual(sys.modules["busio"].I2C.call_count, 2)

    def test_init_failure_retried_next_cycle(self):
        """_run_app() skips the cycle and retries init when _init_i2c_devices fails."""
        sys.modules["busio"].I2C.side_effect = [OSError("bus fail"), MagicMock()]
        _mock_sensor.read.return_value = (20.0, 50.0)

        call_count = [0]
        def _fake_sleep(t):
            call_count[0] += 1
            if call_count[0] >= 2:
                raise StopIteration

        with patch.object(sys.modules["time"], "sleep", side_effect=_fake_sleep):
            try:
                code_module._run_app(None, None, "Test", 0)
            except StopIteration:
                pass

        sys.modules["busio"].I2C.side_effect = None

    def test_i2c_deinited_when_sensor_setup_fails(self):
        """_init_i2c_devices() deinits the I2C bus if sensor.setup() raises.

        Without this, the SCL/SDA pins stay claimed and every subsequent
        busio.I2C() call raises 'pin in use', stalling recovery forever.
        """
        mock_i2c = MagicMock()
        sys.modules["busio"].I2C.return_value = mock_i2c
        _mock_sensor.setup.side_effect = OSError(19, "ENODEV")

        call_count = [0]
        def _fake_sleep(t):
            call_count[0] += 1
            if call_count[0] >= 1:
                raise StopIteration

        with patch.object(sys.modules["time"], "sleep", side_effect=_fake_sleep):
            try:
                code_module._run_app(None, None, "Test", 0)
            except StopIteration:
                pass

        mock_i2c.deinit.assert_called()
        _mock_sensor.setup.side_effect = None

    def test_sensor_error_does_not_crash_loop(self):
        """_run_app() catches non-OSError exceptions and continues the loop."""
        _mock_sensor.read.side_effect = Exception("unexpected error")
        self._run(pool=None)


if __name__ == "__main__":
    unittest.main()
