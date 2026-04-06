# nano_backbone

OTA (over-the-air) firmware update system supporting multiple device types.

## Supported device types

| Identifier | Device |
|---|---|
| `arduino_nano_rp2040_connect` | Arduino Nano RP2040 Connect |
| `esp32_2432s028` | ESP32-2432S028 (CYD) |

Each device type has an independent firmware track on the server. Firmware releases for one type never affect the other.

## Components

- **`server/`** — Django REST Framework update server (supports all device types)
- **`firmware/`** — CircuitPython firmware scaffold for the Arduino Nano RP2040 Connect (ESP32-CYD firmware lives in a separate project)
- **`example_firmware/`** — Full working implementation for an environment sensor node: DHT20 temperature/humidity sensor, SSD1306 OLED display, and Home Assistant MQTT Discovery, with OTA updates via this server. See [`example_firmware/README.md`](example_firmware/README.md) for setup and usage.

### Device libraries required in `lib/` on CIRCUITPY

- `adafruit_esp32spi/` (including `adafruit_esp32spi_socketpool.mpy`)
- `adafruit_bus_device/`
- `adafruit_requests.mpy`
- `adafruit_connection_manager.mpy`

## Local development

### Prerequisites

- Docker and Docker Compose

### Start the server stack

```bash
cp .env.example .env
docker compose up
```

This starts:
- **Django** at `http://localhost:8000`
- **PostgreSQL** at `localhost:5432`
- **MinIO** at `http://localhost:9000` (console at `http://localhost:9001`)

### API

#### Register a device

```bash
curl -X POST http://localhost:8000/api/v1/devices/register/ \
  -H "Content-Type: application/json" \
  -d '{"name": "my-device", "device_type": "arduino_nano_rp2040_connect"}'
```

Returns `{ "device": {...}, "api_key": "..." }`. Save the `api_key` — it is shown only once. `device_type` must be one of the supported identifiers listed above.

#### Ping (smoke-test auth)

```bash
curl http://localhost:8000/api/v1/ping/ \
  -H "Authorization: Api-Key <your-api-key>"
```

Returns `{ "status": "ok" }`.

### Running tests

**Server** (in-memory SQLite, no Docker required):
```bash
cd server
python manage.py test devices firmware --settings=config.test_settings
```

**Firmware** (host-runnable, no hardware required):
```bash
python3 -m unittest discover -s firmware/tests
python3 -m unittest discover -s example_firmware/tests
```
