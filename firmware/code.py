"""
Main entry point for the Arduino Nano RP2040 Connect firmware.

Boot sequence:
  1. If settings.toml is missing or incomplete, enter captive portal provisioning.
  2. Connect to WiFi via the Nina W102 co-processor (adafruit_esp32spi).
  3. Report any pending OTA outcome to the server (success or rollback).
  4. If no OTA was pending, query the server for the latest firmware version.
  5. If an update is available, call ota.apply() — which resets the device.
  6. Continue to main application logic.

Required libraries in /lib/:
  adafruit_esp32spi/  (including adafruit_esp32spi_socketpool.mpy)
  adafruit_bus_device/
  adafruit_requests.mpy
  adafruit_connection_manager.mpy
  adafruit_zipfile.mpy  (needed by ota.py when applying an update)
"""

import json
import os
import time
import board
import busio
from digitalio import DigitalInOut
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_esp32spi.adafruit_esp32spi_socketpool as socketpool
import adafruit_requests as requests

# WIFI_PASSWORD is intentionally absent — open networks use an empty password.
_REQUIRED_SETTINGS = ("WIFI_SSID", "SERVER_URL", "DEVICE_API_KEY")

WIFI_RETRIES = 5
WIFI_RETRY_DELAY = 3  # seconds between WiFi connection attempts

_OTA_PENDING = "/ota_pending"
_BOOT_ATTEMPTS = "/boot_attempts"
_BACKUP_DIR = "/backup"
_ROLLBACK_DONE = "/rollback_completed"


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


def _file_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _read_text(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _cleanup_backup():
    try:
        for name in os.listdir(_BACKUP_DIR):
            _remove(_BACKUP_DIR + "/" + name)
        os.rmdir(_BACKUP_DIR)
    except OSError:
        pass


def _escape_toml(v):
    return (v or "").replace("\\", "\\\\").replace('"', '\\"')


def _update_current_version(version):
    """Rewrite settings.toml with an updated CURRENT_VERSION.

    All other values are read from the environment (already loaded at boot)
    so nothing is lost.
    """
    content = (
        f'WIFI_SSID = "{_escape_toml(os.getenv("WIFI_SSID", ""))}"\n'
        f'WIFI_PASSWORD = "{_escape_toml(os.getenv("WIFI_PASSWORD", ""))}"\n'
        f'SERVER_URL = "{_escape_toml(os.getenv("SERVER_URL", ""))}"\n'
        f'DEVICE_API_KEY = "{_escape_toml(os.getenv("DEVICE_API_KEY", ""))}"\n'
        f'CURRENT_VERSION = "{_escape_toml(version)}"\n'
    )
    with open("/settings.toml", "w") as f:
        f.write(content)
    print("[code] CURRENT_VERSION updated to", version)


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


def _post_event(session, server_url, api_key, event, version):
    """POST an update outcome event to the server.

    Never raises — a reporting failure must not prevent the device from
    continuing to boot.
    """
    url = server_url.rstrip("/") + "/api/v1/devices/events/"
    headers = {
        "Authorization": "Api-Key " + api_key,
        "Content-Type": "application/json",
    }
    payload = json.dumps({"event": event, "version": version})
    try:
        response = session.post(url, data=payload, headers=headers)
        if response.status_code == 201:
            print(f"[code] Reported {event} ({version}) to server.")
        else:
            print("[code] Event report failed, status:", response.status_code)
    except Exception as e:
        print("[code] Event report error:", e)


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

    pool = socketpool.SocketPool(esp)
    session = requests.Session(pool)

    # ── OTA outcome reporting ──────────────────────────────────────────────────

    if _file_exists(_ROLLBACK_DONE):
        # boot.py restored the backup after too many failed boots.
        failed_version = _read_text(_ROLLBACK_DONE)
        _post_event(session, server_url, api_key, "update_failed", failed_version)
        _remove(_ROLLBACK_DONE)
        # Skip the version check — we just rolled back; no point re-offering
        # the same broken update on this boot.

    elif _file_exists(_OTA_PENDING):
        # The device booted successfully into the new firmware.
        new_version = _read_text(_OTA_PENDING)
        _post_event(session, server_url, api_key, "update_success", new_version)
        _remove(_OTA_PENDING)
        _remove(_BOOT_ATTEMPTS)
        _cleanup_backup()
        _update_current_version(new_version)
        # Skip version check — we just applied an update on this boot.

    else:
        # Normal boot: check whether a newer firmware is available.
        result = _check_for_update(session, server_url, api_key, current_version)
        if result is not None:
            fw_url, sha256, new_version = result
            import ota
            try:
                ota.apply(session, fw_url, sha256, new_version)
            except RuntimeError as e:
                print("[code] OTA failed:", e)
                _post_event(session, server_url, api_key, "update_failed", new_version)

    # TODO: main application logic here
    print("[code] Boot complete.")


if __name__ == "__main__":
    main()
