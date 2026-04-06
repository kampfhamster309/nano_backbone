"""
DHT20 (AHT20-compatible) sensor driver wrapper.

Required library in /lib/: adafruit_ahtx0.mpy
"""

import time
import adafruit_ahtx0

# I2C address of the DHT20 / AHT20 — fixed by the hardware, not configurable.
DHT20_ADDR = 0x38

# The DHT20/AHT20 requires up to 100 ms after power-on before it responds on
# I2C. Retry a few times with a short delay to survive tight boot sequences.
_SETUP_RETRIES = 5
_SETUP_RETRY_DELAY = 0.1  # seconds


def setup(i2c):
    """Initialise the DHT20 on *i2c* and return the device object.

    Retries up to _SETUP_RETRIES times with a short delay between attempts to
    allow the sensor time to power up before raising.

    Parameters
    ----------
    i2c : busio.I2C
        Shared I2C bus instance (board.SDA / board.SCL).

    Returns
    -------
    adafruit_ahtx0.AHTx0
        Initialised sensor object; pass to read() on every poll cycle.

    Raises
    ------
    ValueError
        If the sensor is not found after all retries.
    """
    last_error = None
    for attempt in range(_SETUP_RETRIES):
        try:
            return adafruit_ahtx0.AHTx0(i2c)
        except ValueError as e:
            last_error = e
            print(f"[sensor] DHT20 not found (attempt {attempt + 1}/{_SETUP_RETRIES}), retrying...")
            if attempt < _SETUP_RETRIES - 1:
                time.sleep(_SETUP_RETRY_DELAY)
    raise last_error


def read(device):
    """Return the current temperature and humidity from *device*.

    Parameters
    ----------
    device : adafruit_ahtx0.AHTx0
        Sensor object returned by setup().

    Returns
    -------
    tuple[float, float]
        ``(temperature_celsius, humidity_percent)``
    """
    return device.temperature, device.relative_humidity
