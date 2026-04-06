# Environment Sensor — Development Plan

## Goal

Build a CircuitPython firmware image for the Arduino Nano RP2040 Connect that:

1. Reads temperature and humidity from a DHT20 sensor (I²C).
2. Displays both values on an SSD1306 OLED display (I²C).
3. Publishes readings to an MQTT broker using Home Assistant MQTT Discovery so
   the device appears automatically as two sensor entities in HA.
4. Receives OTA firmware updates via the nano_backbone server — the boot/OTA
   infrastructure is inherited unchanged from `firmware/`.

The firmware lives in `example_firmware/` and is independently versioned and
deployed. It is not a modification of the reference firmware in `firmware/`.

---

## Architecture

```
example_firmware/
  boot.py          # identical copy of firmware/boot.py (OTA rollback safety boundary)
  code.py          # adapted from firmware/code.py; TODOs replaced with sensor loop
  ota.py           # identical copy of firmware/ota.py
  captive.py       # extended from firmware/captive.py; adds MQTT fields to the form
  sensor.py        # NEW — DHT20 read via adafruit_ahtx0
  display.py       # NEW — SSD1306 render via adafruit_ssd1306
  mqtt_ha.py       # NEW — MQTT publish + HA Discovery config
```

`boot.py` and `ota.py` are copied verbatim; all OTA/rollback behaviour is
inherited. `code.py` fills in the two `# TODO: main application logic here`
stubs with a continuous sensor → display → MQTT publish loop.

### Sensor loop (steady state)

```
while True:
    temp, humidity = sensor.read()
    display.show(temp, humidity)
    mqtt_ha.publish(temp, humidity)
    time.sleep(POLL_INTERVAL)
```

The loop runs after the OTA / boot-reporting sequence completes.  If WiFi
failed, the loop still runs — sensor data is shown on the display and MQTT
publish attempts are skipped (no network).

### Device identity

Each physical device is assigned a unique identifier derived from the RP2040's
hardware chip ID:

```python
import microcontroller, binascii
DEVICE_ID = binascii.hexlify(microcontroller.cpu.uid).decode()
# e.g. "e6614c311b876134"
```

`DEVICE_ID` is:
- **Hardware-bound** — unique per chip, no user configuration required.
- **Stable** — survives reboots, reflashes, and OTA updates.
- **Collision-free** — safe to use across an arbitrary number of devices on
  the same MQTT broker and HA instance.

`DEVICE_NAME` (set via the captive portal) is used only as a human-readable
label in HA (e.g. "Living Room Sensor"). Topics always use `DEVICE_ID`.

### Home Assistant integration

MQTT Discovery is used so no manual HA configuration is required.  On first
connect the device publishes a discovery config payload to:

```
homeassistant/sensor/<DEVICE_ID>/temperature/config
homeassistant/sensor/<DEVICE_ID>/humidity/config
```

Readings are published every `POLL_INTERVAL` seconds to:

```
homeassistant/sensor/<DEVICE_ID>/temperature/state
homeassistant/sensor/<DEVICE_ID>/humidity/state
```

The HA Discovery payload includes both `DEVICE_ID` (as `unique_id`) and
`DEVICE_NAME` (as `name`) so entities are uniquely keyed but display a
friendly label in the HA UI.

### New `settings.toml` fields

| Key | Description |
|---|---|
| `MQTT_BROKER` | Hostname or IP of the MQTT broker |
| `MQTT_PORT` | Port (default `1883`) |
| `MQTT_USER` | Optional username |
| `MQTT_PASSWORD` | Optional password |
| `DEVICE_NAME` | Human-readable label shown in HA (e.g. "Living Room Sensor"); not used in topics |
| `POLL_INTERVAL` | Seconds between readings (default `30`) |

These are captured by the captive portal on first boot and written to
`settings.toml` alongside the existing WiFi / API key fields.

### Required libraries in `lib/` on CIRCUITPY

In addition to the libraries already required by the base firmware:

| Library | Purpose |
|---|---|
| `adafruit_ahtx0.mpy` | DHT20 / AHT20 / AHT21 sensor driver |
| `adafruit_ssd1306.mpy` | SSD1306 OLED driver |
| `adafruit_framebuf.mpy` | Framebuffer dependency of adafruit_ssd1306 |
| `adafruit_minimqtt/` | MQTT client |
| `adafruit_display_text/` | Text label rendering (if displayio path is chosen) |

> **Note**: `adafruit_ssd1306` can operate in two modes: raw framebuf (simpler,
> less RAM) or displayio (richer, more RAM).  The Nano RP2040 Connect has 264 KB
> SRAM which should comfortably fit either.  The framebuf path is preferred here
> to keep the dependency count down.

---

## Open Questions

1. ~~**MQTT broker**~~ — An MQTT broker is already running on the network. No
   changes to the docker-compose stack are needed.

2. ~~**MQTT credentials**~~ — Credentials are optional. `MQTT_USER` and
   `MQTT_PASSWORD` in `settings.toml` may be left blank; the firmware connects
   anonymously if they are absent. The captive portal does not mark these fields
   as required.

3. ~~**I²C addresses**~~ — Both devices share the same I²C bus (`board.SDA` /
   `board.SCL`). Default addresses are assumed: SSD1306 at `0x3C`, DHT20 at
   `0x38`. If the display fails to initialise on the device, `0x3D` is the first
   thing to try.

4. ~~**Poll interval**~~ — 30 s confirmed. This is the hardcoded default in
   `settings.toml.example` and the fallback if `POLL_INTERVAL` is not set.

5. ~~**Display layout**~~ — Confirmed: both values on one screen, °C to one
   decimal place, %RH to one decimal place, largest font that fits both lines.

6. ~~**Sleep / power**~~ — Continuous loop confirmed. Sleep is out of scope for v1.

7. ~~**MQTT retain flag**~~ — Confirmed: all readings published with `retain=True`.

8. ~~**OTA packaging**~~ — A `README.md` will be created in `example_firmware/`
   covering: required hardware, wiring, library installation, first-boot
   provisioning, and OTA packaging/upload instructions (zip layout + build
   script).

---

## Implementation Steps

### ~~Step 1 — Project scaffold~~ ✓
- Create the `example_firmware/` directory structure listed above.
- Copy `boot.py` and `ota.py` verbatim from `firmware/`.
- Create skeleton `code.py` (adapted from `firmware/code.py`), `captive.py`,
  `sensor.py`, `display.py`, and `mqtt_ha.py` with `raise NotImplementedError`
  stubs.
- Add a `settings.toml.example` documenting all required keys.

### ~~Step 2 — Sensor module (`sensor.py`)~~ ✓
- Implement `setup(i2c)` → returns an AHTx0 device object.
- Implement `read(device)` → returns `(temperature_c, humidity_pct)`.
- Write host-runnable unit tests mocking `adafruit_ahtx0`.

### ~~Step 3 — Display module (`display.py`)~~ ✓
- Implement `setup(i2c)` → initialises SSD1306 over I²C and returns display
  object.
- Implement `show(display, temp, humidity)` → renders two lines of text.
- Write host-runnable unit tests mocking `adafruit_ssd1306` and
  `adafruit_framebuf`.

### ~~Step 4 — MQTT / HA module (`mqtt_ha.py`)~~ ✓
- Implement `setup(pool, broker, port, user, password)` → returns connected
  MQTT client.
- Implement `publish_discovery(client, device_id, device_name)` → publishes HA
  Discovery config payloads for both sensor entities (once per boot); `device_id`
  sets the topic and `unique_id`, `device_name` sets the human-readable label.
- Implement `publish_readings(client, device_id, temp, humidity)` → publishes
  current readings to state topics.
- Handle disconnect/reconnect gracefully so a transient broker outage does not
  crash the loop.
- Write host-runnable unit tests mocking `adafruit_minimqtt`.

### ~~Step 5 — Captive portal extension (`captive.py`)~~ ✓
- Copy `firmware/captive.py` as the base.
- Extend the HTML form to include fields for `MQTT_BROKER`, `MQTT_PORT`,
  `MQTT_USER`, `MQTT_PASSWORD`, `DEVICE_NAME`, and `POLL_INTERVAL`.
- Extend `settings.toml` write logic to include the new fields.
- Update `_REQUIRED_SETTINGS` to require `MQTT_BROKER` and `DEVICE_NAME` in
  addition to the existing fields.

### ~~Step 6 — Main firmware (`code.py`)~~ ✓
- Adapt `firmware/code.py`:
  - Import `sensor`, `display`, `mqtt_ha`.
  - After OTA sequence, initialise I²C, sensor, display, and MQTT client.
  - Replace both `# TODO` stubs with the sensor loop (see Architecture above).
  - If WiFi failed, still run the display loop, skipping MQTT.

### ~~Step 7 — Integration test~~ ✓
Requires physical hardware. Checklist documented in `README.md` under
**Integration test checklist**.

### ~~Step 8 — README and OTA packaging~~ ✓
- Create `example_firmware/README.md` covering:
  - Required hardware (Nano RP2040 Connect, SSD1306, DHT20) and wiring.
  - Library installation (which `.mpy` files go in `lib/`).
  - First-boot provisioning via the captive portal (fields and their meaning).
  - OTA packaging: zip layout the server expects and a `build_zip.sh` script
    that packages all firmware files into a deployable archive.
  - How to register the device and upload the first release to the
    nano_backbone server.
