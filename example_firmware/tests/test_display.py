"""
Host-runnable tests for display.py.
CircuitPython-specific modules are mocked via sys.modules before import.
Run with: python3 -m unittest discover -s example_firmware/tests
"""

import importlib.util
import os
import sys
import unittest
from unittest.mock import MagicMock, call

# ── Mock CircuitPython modules before importing display ───────────────────────

_mock_ssd1306 = MagicMock()
sys.modules["adafruit_ssd1306"] = _mock_ssd1306
sys.modules["adafruit_framebuf"] = MagicMock()

_DISPLAY_PATH = os.path.join(os.path.dirname(__file__), "..", "display.py")
_spec = importlib.util.spec_from_file_location("display_module", _DISPLAY_PATH)
display_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(display_module)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestSetup(unittest.TestCase):
    def setUp(self):
        _mock_ssd1306.SSD1306_I2C.reset_mock()

    def test_returns_ssd1306_instance(self):
        """setup() calls SSD1306_I2C and returns the result."""
        mock_i2c = MagicMock()
        mock_oled = MagicMock()
        _mock_ssd1306.SSD1306_I2C.return_value = mock_oled

        result = display_module.setup(mock_i2c)

        self.assertIs(result, mock_oled)

    def test_sets_maximum_contrast(self):
        """setup() calls contrast(255) so the display is visible after power-on."""
        mock_oled = MagicMock()
        _mock_ssd1306.SSD1306_I2C.return_value = mock_oled

        display_module.setup(MagicMock())

        mock_oled.contrast.assert_called_once_with(255)

    def test_clears_display_on_init(self):
        """setup() clears the display and flushes so it starts in a known state."""
        mock_oled = MagicMock()
        _mock_ssd1306.SSD1306_I2C.return_value = mock_oled

        display_module.setup(MagicMock())

        mock_oled.fill.assert_called_with(0)
        mock_oled.show.assert_called()

    def test_passes_correct_dimensions(self):
        """setup() passes WIDTH and HEIGHT to SSD1306_I2C."""
        mock_i2c = MagicMock()
        display_module.setup(mock_i2c)

        args, kwargs = _mock_ssd1306.SSD1306_I2C.call_args
        self.assertEqual(args[0], display_module.WIDTH)
        self.assertEqual(args[1], display_module.HEIGHT)

    def test_passes_i2c_bus(self):
        """setup() passes the i2c argument to SSD1306_I2C."""
        mock_i2c = MagicMock(name="i2c_bus")
        display_module.setup(mock_i2c)

        args, _ = _mock_ssd1306.SSD1306_I2C.call_args
        self.assertIs(args[2], mock_i2c)

    def test_passes_default_i2c_address(self):
        """setup() passes SSD1306_ADDR as the addr keyword argument."""
        display_module.setup(MagicMock())

        _, kwargs = _mock_ssd1306.SSD1306_I2C.call_args
        self.assertEqual(kwargs["addr"], display_module.SSD1306_ADDR)
        self.assertEqual(kwargs["addr"], 0x3C)


class TestShow(unittest.TestCase):
    def _make_oled(self):
        return MagicMock()

    def test_clears_display_first(self):
        """show() calls fill(0) before drawing text."""
        oled = self._make_oled()
        display_module.show(oled, 21.5, 58.3)

        # fill(0) must be the first call on the oled mock
        first_call = oled.method_calls[0]
        self.assertEqual(first_call, call.fill(0))

    def test_calls_show_last(self):
        """show() calls oled.show() as the final step to flush the framebuffer."""
        oled = self._make_oled()
        display_module.show(oled, 21.5, 58.3)

        last_call = oled.method_calls[-1]
        self.assertEqual(last_call, call.show())

    def test_renders_temperature_line(self):
        """show() draws a text line containing the formatted temperature."""
        oled = self._make_oled()
        display_module.show(oled, 21.5, 58.3)

        text_calls = [c for c in oled.method_calls if c[0] == "text"]
        temp_line = text_calls[0]
        self.assertIn("21.5", temp_line.args[0])
        self.assertIn("C", temp_line.args[0])

    def test_renders_humidity_line(self):
        """show() draws a text line containing the formatted humidity."""
        oled = self._make_oled()
        display_module.show(oled, 21.5, 58.3)

        text_calls = [c for c in oled.method_calls if c[0] == "text"]
        hum_line = text_calls[1]
        self.assertIn("58.3", hum_line.args[0])
        self.assertIn("%", hum_line.args[0])

    def test_temperature_one_decimal_place(self):
        """show() formats temperature to exactly one decimal place."""
        oled = self._make_oled()
        display_module.show(oled, 21.0, 50.0)

        text_calls = [c for c in oled.method_calls if c[0] == "text"]
        self.assertIn("21.0", text_calls[0].args[0])

    def test_humidity_one_decimal_place(self):
        """show() formats humidity to exactly one decimal place."""
        oled = self._make_oled()
        display_module.show(oled, 20.0, 58.0)

        text_calls = [c for c in oled.method_calls if c[0] == "text"]
        self.assertIn("58.0", text_calls[1].args[0])

    def test_negative_temperature_displayed(self):
        """show() handles negative temperatures without error."""
        oled = self._make_oled()
        display_module.show(oled, -3.7, 90.0)

        text_calls = [c for c in oled.method_calls if c[0] == "text"]
        self.assertIn("-3.7", text_calls[0].args[0])

    def test_text_drawn_with_size_2(self):
        """show() renders text at size=2 for maximum readability."""
        oled = self._make_oled()
        display_module.show(oled, 20.0, 50.0)

        text_calls = [c for c in oled.method_calls if c[0] == "text"]
        for tc in text_calls:
            self.assertEqual(tc.kwargs.get("size"), 2)

    def test_two_text_lines_drawn(self):
        """show() draws exactly two text lines (temperature and humidity)."""
        oled = self._make_oled()
        display_module.show(oled, 20.0, 50.0)

        text_calls = [c for c in oled.method_calls if c[0] == "text"]
        self.assertEqual(len(text_calls), 2)

    def test_lines_at_different_y_positions(self):
        """show() places the two text lines at different vertical positions."""
        oled = self._make_oled()
        display_module.show(oled, 20.0, 50.0)

        text_calls = [c for c in oled.method_calls if c[0] == "text"]
        y1 = text_calls[0].args[2]
        y2 = text_calls[1].args[2]
        self.assertNotEqual(y1, y2)


if __name__ == "__main__":
    unittest.main()
