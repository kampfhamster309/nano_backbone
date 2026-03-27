"""
Main entry point for the Arduino Nano RP2040 Connect firmware.

Boot sequence:
  1. If settings.toml is missing or incomplete, enter captive portal provisioning.
  2. Connect to WiFi via the Nina W102 co-processor (adafruit_esp32spi).
  3. Query the server for the latest firmware version.
  4. If an update is available, call ota.apply() (Ticket 5).
  5. Continue to main application logic.

Required libraries in /lib/:
  adafruit_esp32spi/
  adafruit_bus_device/
  adafruit_requests.mpy
"""

import os
import time
import board
import busio
from digitalio import DigitalInOut
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
import adafruit_requests as requests

# WIFI_PASSWORD is intentionally absent — open networks use an empty password.
_REQUIRED_SETTINGS = ("WIFI_SSID", "SERVER_URL", "DEVICE_API_KEY")

WIFI_RETRIES = 5
WIFI_RETRY_DELAY = 3  # seconds between WiFi connection attempts


# ── Pure-Python helpers (no CircuitPython dependencies) ───────────────────────


def _semver_gt(a, b):
    """Return True if semantic version string *a* is strictly greater than *b*.

    Both strings must be in MAJOR.MINOR.PATCH format. Returns False for any
    parse error so callers degrade gracefully when the server returns bad data.
    """
    def _parse(v):
        parts = v.strip().lstrip("v").split(".")
        return tuple(int(x) for x in parts[:3])

    try:
        return _parse(a) > _parse(b)
    except (ValueError, IndexError, AttributeError):
        return False


def _settings_complete():
    return all(os.getenv(k) for k in _REQUIRED_SETTINGS)


# ── ESP32SPI-backed helpers ────────────────────────────────────────────────────


def _setup_esp():
    """Initialise the Nina W102 over SPI (Nano RP2040 Connect pin assignments)."""
    spi = busio.SPI(board.SCK1, board.MOSI1, board.MISO1)
    cs = DigitalInOut(board.CS1)
    ready = DigitalInOut(board.ESP_BUSY)
    reset_pin = DigitalInOut(board.ESP_RESET)
    return adafruit_esp32spi.ESP_SPIcontrol(spi, cs, ready, reset_pin)


def _connect_wifi(esp, ssid, password):
    """Attempt to join *ssid* up to WIFI_RETRIES times.

    Returns True on success, False after all retries are exhausted.
    *password* may be an empty string for open networks.
    """
    pw = password or b""
    for attempt in range(1, WIFI_RETRIES + 1):
        print(f"[code] WiFi attempt {attempt}/{WIFI_RETRIES}: {ssid}")
        try:
            esp.connect_AP(ssid, pw)
            print("[code] WiFi connected. IP:", esp.pretty_ip(esp.ip_address))
            return True
        except Exception as e:
            print("[code] WiFi error:", e)
            if attempt < WIFI_RETRIES:
                time.sleep(WIFI_RETRY_DELAY)
    print("[code] WiFi failed after", WIFI_RETRIES, "attempts.")
    return False


def _check_for_update(session, server_url, api_key, current_version):
    """Query the server for the latest firmware version.

    Returns ``(url, sha256, new_version)`` if a newer release exists, or
    ``None`` if the device is up to date, the server has no releases, or the
    server is unreachable.

    Never raises — all errors are caught and logged so a server outage does
    not block the boot sequence.
    """
    url = server_url.rstrip("/") + "/api/v1/firmware/latest/"
    headers = {"Authorization": "Api-Key " + api_key}
    try:
        response = session.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            server_version = data.get("version", "")
            if _semver_gt(server_version, current_version):
                print(f"[code] Update available: {current_version} -> {server_version}")
                return data.get("url"), data.get("sha256"), server_version
            print(f"[code] Firmware up to date ({current_version}).")
            return None
        if response.status_code == 404:
            print("[code] No firmware release published yet.")
            return None
        print("[code] Unexpected server status:", response.status_code)
        return None
    except Exception as e:
        print("[code] Server unreachable:", e)
        return None


# ── Entry point ────────────────────────────────────────────────────────────────


def main():
    if not _settings_complete():
        import captive
        captive.run()
        return  # captive.run() ends with microcontroller.reset(), never returns

    ssid = os.getenv("WIFI_SSID")
    password = os.getenv("WIFI_PASSWORD", "")
    server_url = os.getenv("SERVER_URL")
    api_key = os.getenv("DEVICE_API_KEY")
    current_version = os.getenv("CURRENT_VERSION", "0.0.0")

    print("[code] Booting. Version:", current_version)
    print("[code] Server:", server_url)

    esp = _setup_esp()
    esp.reset()
    time.sleep(1)

    if not _connect_wifi(esp, ssid, password):
        print("[code] Proceeding without update check.")
        # TODO: main application logic here
        return

    socket.set_interface(esp)
    session = requests.Session(socket, esp)

    result = _check_for_update(session, server_url, api_key, current_version)
    if result is not None:
        fw_url, sha256, new_version = result
        import ota
        try:
            ota.apply(fw_url, sha256, new_version)
        except NotImplementedError:
            print("[code] OTA not yet implemented — update noted, continuing boot.")

    # TODO: main application logic here
    print("[code] Boot complete.")


if __name__ == "__main__":
    main()
