import os

_REQUIRED_SETTINGS = ("WIFI_SSID", "WIFI_PASSWORD", "SERVER_URL", "DEVICE_API_KEY")


def _settings_complete():
    return all(os.getenv(k) for k in _REQUIRED_SETTINGS)


if not _settings_complete():
    # No valid settings.toml found — enter provisioning mode.
    import captive
    captive.run()

# Settings present: proceed to normal operation.
# Ticket 4 will add WiFi connection and OTA version check here.
print("Settings OK.")
print("SSID:", os.getenv("WIFI_SSID"))
print("Server:", os.getenv("SERVER_URL"))
print("Version:", os.getenv("CURRENT_VERSION", "unknown"))
