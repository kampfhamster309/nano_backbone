"""
SSD1306 OLED display driver wrapper.

Required libraries in /lib/: adafruit_ssd1306.mpy, adafruit_framebuf.mpy

Uses the raw framebuf path (not displayio) to minimise RAM usage.
Text is rendered at size=2 (10×16 px per character) so both lines fill
the 128×64 screen comfortably.
"""

import adafruit_ssd1306

# Default I2C address — most SSD1306 modules use 0x3C; try 0x3D if init fails.
SSD1306_ADDR = 0x3C
WIDTH = 128
HEIGHT = 64

# Vertical layout for two size-2 lines (each 16 px tall) centred on 64 px.
_LINE1_Y = 14
_LINE2_Y = 34
_TEXT_SIZE = 2


def setup(i2c):
    """Initialise the SSD1306 at SSD1306_ADDR and return the display object.

    Sets maximum contrast and performs an initial clear so the display starts
    in a known state. Some SSD1306 modules default to zero contrast after
    power-on, which makes them appear blank even when content is rendered.

    Parameters
    ----------
    i2c : busio.I2C
        Shared I2C bus instance (board.SDA / board.SCL).

    Returns
    -------
    adafruit_ssd1306.SSD1306_I2C
        Initialised display object; pass to show() on every poll cycle.
    """
    oled = adafruit_ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=SSD1306_ADDR)
    oled.contrast(255)
    oled.fill(0)
    oled.show()
    return oled


def show(oled, temp, humidity):
    """Render temperature and humidity on *oled*.

    Clears the display, then draws two lines:
        T: 21.5 C
        H: 58.3 %

    Parameters
    ----------
    oled : adafruit_ssd1306.SSD1306_I2C
        Display object returned by setup().
    temp : float
        Temperature in degrees Celsius.
    humidity : float
        Relative humidity in percent.
    """
    oled.fill(0)
    oled.text(f"T: {temp:.1f} C", 0, _LINE1_Y, 1, size=_TEXT_SIZE)
    oled.text(f"H: {humidity:.1f} %", 0, _LINE2_Y, 1, size=_TEXT_SIZE)
    oled.show()
