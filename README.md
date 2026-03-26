# nano_backbone

OTA (over-the-air) firmware update system for the Arduino Nano RP2040 Connect.

## Components

- **`server/`** — Django REST Framework update server
- **`firmware/`** — CircuitPython firmware for the Arduino Nano RP2040 Connect

## Local development

### Prerequisites

- Docker and Docker Compose

### Start the server stack

```bash
cp .env.example .env
docker-compose up
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
  -d '{"name": "my-device"}'
```

Returns `{ "device": {...}, "api_key": "..." }`. Save the `api_key` — it is shown only once.

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
```
