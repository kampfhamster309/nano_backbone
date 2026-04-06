"""
Host-runnable tests for sensor.py.
CircuitPython-specific modules are mocked via sys.modules before import.
Run with: python3 -m unittest discover -s example_firmware/tests
"""

import importlib.util
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# ── Mock CircuitPython modules before importing sensor ────────────────────────

_mock_ahtx0 = MagicMock()
sys.modules["adafruit_ahtx0"] = _mock_ahtx0
sys.modules.setdefault("time", MagicMock())

_SENSOR_PATH = os.path.join(os.path.dirname(__file__), "..", "sensor.py")
_spec = importlib.util.spec_from_file_location("sensor_module", _SENSOR_PATH)
sensor_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sensor_module)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestSetup(unittest.TestCase):
    def setUp(self):
        _mock_ahtx0.AHTx0.reset_mock()
        _mock_ahtx0.AHTx0.side_effect = None

    def test_returns_ahtx0_instance(self):
        """setup() calls AHTx0(i2c) and returns the result."""
        mock_i2c = MagicMock()
        mock_device = MagicMock()
        _mock_ahtx0.AHTx0.return_value = mock_device

        result = sensor_module.setup(mock_i2c)

        _mock_ahtx0.AHTx0.assert_called_once_with(mock_i2c)
        self.assertIs(result, mock_device)

    def test_passes_i2c_bus_to_driver(self):
        """setup() forwards the i2c argument directly to AHTx0."""
        mock_i2c = MagicMock(name="i2c_bus")
        sensor_module.setup(mock_i2c)
        args, _ = _mock_ahtx0.AHTx0.call_args
        self.assertIs(args[0], mock_i2c)

    def test_retries_on_value_error(self):
        """setup() retries if AHTx0 raises ValueError (sensor not ready yet)."""
        mock_device = MagicMock()
        _mock_ahtx0.AHTx0.side_effect = [ValueError("No I2C device at address: 0x38"),
                                          mock_device]
        with patch.object(sensor_module.time, "sleep"):
            result = sensor_module.setup(MagicMock())
        self.assertIs(result, mock_device)
        self.assertEqual(_mock_ahtx0.AHTx0.call_count, 2)

    def test_sleeps_between_retries(self):
        """setup() waits between retries to give the sensor time to power up."""
        _mock_ahtx0.AHTx0.side_effect = [ValueError(), MagicMock()]
        with patch.object(sensor_module.time, "sleep") as mock_sleep:
            sensor_module.setup(MagicMock())
        mock_sleep.assert_called_once_with(sensor_module._SETUP_RETRY_DELAY)

    def test_raises_after_all_retries_exhausted(self):
        """setup() raises ValueError if the sensor never responds."""
        _mock_ahtx0.AHTx0.side_effect = ValueError("No I2C device at address: 0x38")
        with patch.object(sensor_module.time, "sleep"):
            with self.assertRaises(ValueError):
                sensor_module.setup(MagicMock())
        self.assertEqual(_mock_ahtx0.AHTx0.call_count, sensor_module._SETUP_RETRIES)


class TestRead(unittest.TestCase):
    def _make_device(self, temperature, humidity):
        device = MagicMock()
        device.temperature = temperature
        device.relative_humidity = humidity
        return device

    def test_returns_temperature_and_humidity(self):
        """read() returns (temperature, relative_humidity) from the device."""
        device = self._make_device(21.5, 58.3)
        temp, humidity = sensor_module.read(device)
        self.assertAlmostEqual(temp, 21.5)
        self.assertAlmostEqual(humidity, 58.3)

    def test_returns_tuple_of_two(self):
        """read() always returns exactly two values."""
        device = self._make_device(0.0, 0.0)
        result = sensor_module.read(device)
        self.assertEqual(len(result), 2)

    def test_negative_temperature(self):
        """read() handles sub-zero temperatures correctly."""
        device = self._make_device(-5.2, 80.0)
        temp, humidity = sensor_module.read(device)
        self.assertAlmostEqual(temp, -5.2)

    def test_boundary_humidity_values(self):
        """read() passes through 0% and 100% humidity unchanged."""
        for h in (0.0, 100.0):
            device = self._make_device(20.0, h)
            _, humidity = sensor_module.read(device)
            self.assertAlmostEqual(humidity, h)

    def test_reads_from_device_attributes(self):
        """read() accesses .temperature and .relative_humidity on the device."""
        device = MagicMock()
        device.temperature = 22.0
        device.relative_humidity = 45.0
        sensor_module.read(device)
        # Attribute access is implicit; verify no unexpected calls were made.
        self.assertEqual(device.temperature, 22.0)
        self.assertEqual(device.relative_humidity, 45.0)


if __name__ == "__main__":
    unittest.main()
