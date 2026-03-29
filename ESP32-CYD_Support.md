# ESP32-CYD (ESP32-2432S028) Server-Side Support

Adding a second device type to nano_backbone while keeping the two firmware
tracks completely independent on the server side.

The ESP32-CYD firmware will live in a separate project. Only the server
needs changes.

---

## Open Questions

These must be resolved before implementation begins.

### Q1 — Device type identifier strings

What canonical string identifiers should be used in the database and API?

Options:
- `"nano_rp2040"` / `"esp32_cyd"`
- `"arduino_nano_rp2040_connect"` / `"esp32_2432s028"`
- Something else?

**Why it matters:** stored in DB, sent over the wire, appears in admin and
future firmware metadata. Hard to change after devices are registered.

---

### Q2 — Is `device_type` required at registration?

`POST /api/v1/devices/register/` currently accepts only `name`.

Options:
a. **Required field** — clean but breaks the existing Nano firmware (the
   captive portal would need to be updated to include `device_type`).
b. **Optional with a sensible default** — backwards-compatible, but
   introduces a "unknown type" state that must be handled everywhere.
c. **Optional, defaults to `"nano_rp2040"`** — pragmatic for now, but
   silently mislabels any future unknown device type.

---

### Q3 — What happens to already-registered devices and firmware releases?

There are already Device rows and FirmwareRelease rows in the DB with no
device_type. Options:
a. **Data migration sets them to `"nano_rp2040"`** — safe assumption given
   only one device type has ever existed.
b. **Leave as null, handle null as "all devices"** — more flexible but adds
   edge cases to every query.

Recommendation: option (a) — migrate existing rows to `"nano_rp2040"` and
make the field non-nullable going forward.

---

### Q4 — Does the Nano RP2040 firmware need updating?

The firmware check endpoint (`GET /api/v1/firmware/latest/`) currently
identifies the device from the API key and looks up its stored type. If
device_type is stored on the Device model (set at registration time), the
firmware never needs to send its own type — the server already knows it.

**Confirmed assumption:** device_type is a property of the registered Device,
not something the device announces on each request.

Does this hold? Or should the device assert its type on every firmware check
as a sanity guard?

---

### Q5 — `is_latest` exclusivity scope

Currently `FirmwareRelease.save()` clears `is_latest` globally (one latest
across all devices). With two device types this must be scoped per type: one
latest per device_type.

**Confirm:** is this the intended behaviour?

---

### Q6 — Firmware release admin workflow for the ESP32-CYD

When uploading a new FirmwareRelease in the Django admin, the admin user
selects the `device_type`. SHA-256 is auto-computed (existing behaviour).

Is there anything specific about the ESP32-CYD firmware file format or naming
that the admin upload needs to accommodate (e.g. `.bin` instead of `.zip`)?

---

## Planned Implementation Steps

*(Start here once all open questions are resolved.)*

### 1. Add `device_type` to `Device` model

```python
DEVICE_TYPE_NANO_RP2040 = "nano_rp2040"
DEVICE_TYPE_ESP32_CYD   = "esp32_cyd"
DEVICE_TYPE_CHOICES = [
    (DEVICE_TYPE_NANO_RP2040, "Arduino Nano RP2040 Connect"),
    (DEVICE_TYPE_ESP32_CYD,   "ESP32-2432S028 (CYD)"),
]

device_type = models.CharField(
    max_length=30,
    choices=DEVICE_TYPE_CHOICES,
    default=DEVICE_TYPE_NANO_RP2040,
)
```

### 2. Add `device_type` to `FirmwareRelease` model

Same choices, same field. Non-nullable (every release belongs to exactly one
device type).

### 3. Fix `is_latest` exclusivity to be per device_type

Change the `save()` override in `FirmwareRelease`:

```python
def save(self, *args, **kwargs):
    if self.is_latest:
        FirmwareRelease.objects.exclude(pk=self.pk).filter(
            is_latest=True, device_type=self.device_type
        ).update(is_latest=False)
    super().save(*args, **kwargs)
```

### 4. Update `GET /api/v1/firmware/latest/`

Filter by the requesting device's type (looked up from API key — no URL or
body change needed):

```python
device = api_key_obj.device
release = FirmwareRelease.objects.filter(
    is_latest=True, device_type=device.device_type
).first()
```

### 5. Update `POST /api/v1/devices/register/`

Accept optional `device_type` in the request body (default: `"nano_rp2040"`
for backwards compatibility). Validate against the choices list.

### 6. Write and apply migrations

- Migration 1: add nullable `device_type` to both models.
- Migration 2 (data migration): set existing rows to `"nano_rp2040"`.
- Migration 3: make the field non-nullable.

(Or combine into one migration with a suitable default.)

### 7. Update admin views

- `FirmwareReleaseAdmin`: add `device_type` to `list_display`, `list_filter`,
  and `fieldsets`.
- `DeviceAdmin`: add `device_type` to `list_display` and `list_filter`.

### 8. Update all server tests

- Pass `device_type` where required in registration calls.
- Add test cases for cross-type isolation (Nano device must not receive
  ESP32-CYD firmware and vice versa).

### 9. Update CLAUDE.md and README.md

- Document the two device types and their identifiers.
- Note that firmware releases are per-device-type.
