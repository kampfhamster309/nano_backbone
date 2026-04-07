# Firmware — Reference Implementation

Minimal CircuitPython firmware scaffold for the **Arduino Nano RP2040 Connect**.
Handles WiFi provisioning, OTA update checks, and graceful rollback. It does not
include any application logic — that belongs in a concrete implementation built on
top of this scaffold (see [`example_firmware/`](../example_firmware/README.md) for
a working example).

---

## Files

| File | Purpose |
|---|---|
| `boot.py` | Runs before `code.py` on every reset. Remounts the filesystem as writable and manages OTA rollback if the new firmware fails to boot. |
| `code.py` | Main entry point. Handles WiFi connection, OTA version check, and calls into application logic. |
| `captive.py` | SoftAP captive portal shown on first boot to collect WiFi credentials and the device API key. |
| `ota.py` | Downloads, SHA-256 verifies, and extracts a firmware zip. Calls `microcontroller.reset()` on success. |
| `build_zip.sh` | Packages the firmware files into a versioned zip ready for upload to the nano_backbone server. |

`boot.py` is the OTA safety boundary and is **never** included in an update zip — it must be deployed manually and remains stable across updates.

---

## Required libraries

Copy the following into the `lib/` folder on the `CIRCUITPY` drive (from the
[Adafruit CircuitPython Bundle](https://circuitpython.org/libraries)):

| File / folder | Notes |
|---|---|
| `adafruit_esp32spi/` | WiFi via Nina W102 co-processor |
| `adafruit_bus_device/` | SPI/I²C device abstraction |
| `adafruit_requests.mpy` | HTTP client |
| `adafruit_connection_manager.mpy` | Dependency of `adafruit_requests` |
| `zipfile.py` | OTA zip extraction — from [jonnor/micropython-zipfile](https://github.com/jonnor/micropython-zipfile). Copy `zipfile.py` from the repo root into `lib/`. |

---

## First-boot provisioning

On first boot (no `settings.toml`), the device starts a Wi-Fi access point
named **`nano-backbone`**.

1. Connect to `nano-backbone` (no password).
2. Open `http://192.168.4.1/` in a browser.
3. Fill in the provisioning form with your WiFi credentials and the device API
   key obtained from `POST /api/v1/devices/register/`.
4. Click **Save and Reboot**.

After provisioning the device connects to your network and begins the normal
boot sequence on every subsequent reset.

---

## Boot sequence

1. `boot.py` remounts the filesystem as writable and checks for a pending OTA.
2. If WiFi credentials and a server URL are present in `settings.toml`, the
   device connects to the nano_backbone server.
3. Any pending OTA outcome (success or rollback) is reported to the server.
4. On a normal boot, the server is queried for a newer firmware version.
5. If an update is available, it is downloaded, verified, and applied — the
   device resets into the new firmware.
6. Application logic runs.

---

## OTA rollback

`boot.py` tracks how many times the device has booted while an update is
pending. If the new firmware fails to report `update_success` within three
boot attempts, `boot.py` restores the files from `/backup/` and flags
`/rollback_completed` so `code.py` can report the failure to the server once
WiFi is available.

The list of files to restore is read from `/backup/firmware_manifest.txt`,
which is included in every zip produced by `build_zip.sh`. This means
`boot.py` never needs to be modified when files are added or removed from the
firmware — only `build_zip.sh` needs updating.

---

## Building a release zip

```bash
cd firmware
./build_zip.sh 1.0.0
```

Output:

```
Created : firmware_1.0.0.zip
SHA256  : <hex digest>

Upload this zip via the Django admin (SHA-256 is computed automatically on save):
  http://<server>:8000/admin/firmware/firmwarerelease/add/
```

The script:
- Packages `code.py`, `ota.py`, and `captive.py`.
- Auto-generates `firmware_manifest.txt` and includes it in the zip.
- Verifies any staged library files in `lib/` before building (see below).

`boot.py` is excluded — it is the safety boundary and must not be overwritten
by an update.

### Bundling new library dependencies

If a release requires a library that is not yet on target devices, stage it in
`lib/` and add it to `LIB_FILES` in `build_zip.sh`:

```bash
# 1. Copy the library into the staging directory
cp /path/to/bundle/lib/some_library.mpy firmware/lib/

# 2. Add it to LIB_FILES in build_zip.sh
LIB_FILES=(
    lib/some_library.mpy
)

# 3. Build as normal
./build_zip.sh 1.1.0
```

The `lib/` directory is gitignored. The OTA extractor writes each zip entry
to `/<name>`, so `lib/some_library.mpy` lands at `/lib/some_library.mpy` on
the device.

---

## Uploading to the server

1. Log in to the Django admin at `http://<server>:8000/admin/`.
2. Go to **Firmware → Firmware releases → Add**.
3. Set **Version** (e.g. `1.0.0`) and **Device type** (`arduino_nano_rp2040_connect`).
4. Upload the zip produced by `build_zip.sh`.
5. Check **Is latest** to make it the active release.
6. Save — the SHA-256 is computed automatically.

On the next boot, all registered devices of this type will receive the update.

---

## Extending the scaffold

`code.py` calls into application logic after the OTA check. To build a
concrete firmware on top of this scaffold:

1. Add your application modules alongside `code.py`.
2. Add them to `FILES` in `build_zip.sh` and to `_FIRMWARE_FILES` in `ota.py`.
3. Import and call them from `code.py`.

See [`example_firmware/`](../example_firmware/README.md) for a complete
worked example (DHT20 sensor, SSD1306 OLED, Home Assistant MQTT Discovery).
