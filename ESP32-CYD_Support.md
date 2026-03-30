# ESP32-CYD (ESP32-2432S028) Server-Side Support

Adding a second device type to nano_backbone while keeping the two firmware
tracks completely independent on the server side.

The ESP32-CYD firmware will live in a separate project. Only the server
needs changes.

---

## Open Questions

These must be resolved before implementation begins.

### ~~Q1 — Device type identifier strings~~ — **Resolved**

Use the full, precise identifiers:
- `"arduino_nano_rp2040_connect"`
- `"esp32_2432s028"`

---

### ~~Q2 — Is `device_type` required at registration?~~ — **Resolved**

`device_type` is a **required field** at registration. The Nano RP2040
captive portal must be updated to include it in the registration request.

---

### ~~Q3 — What happens to already-registered devices and firmware releases?~~ — **Resolved**

Data migration sets all existing Device and FirmwareRelease rows to
`"arduino_nano_rp2040_connect"`. Field is non-nullable going forward.

---

### ~~Q4 — Does the Nano RP2040 firmware need updating?~~ — **Resolved**

The device asserts its type on every firmware check as a sanity guard, sent
as a query parameter:

```
GET /api/v1/firmware/latest/?device_type=arduino_nano_rp2040_connect
```

The server selects firmware using the **stored** type from the Device record.
If the asserted type does not match the stored type, the server returns 400.
`firmware/code.py` (`_check_for_update`) must be updated to include the
query parameter.

---

### ~~Q5 — `is_latest` exclusivity scope~~ — **Resolved**

`is_latest` is scoped per `device_type`: one latest release per device type
at a time.

---

### ~~Q6 — Firmware release admin workflow for the ESP32-CYD~~ — **Resolved**

ESP32-CYD firmware is uploaded as a `.bin` file. The server requires no
special handling — `FileField` and S3 store any file type transparently, and
SHA-256 is computed from raw bytes regardless of format. The device is
responsible for flashing the binary after download.

---

## Planned Implementation Steps

*(Start here once all open questions are resolved.)*

### ~~1. Add `device_type` to `Device` model~~ ✓


```python
DEVICE_TYPE_NANO_RP2040 = "arduino_nano_rp2040_connect"
DEVICE_TYPE_ESP32_CYD   = "esp32_2432s028"
DEVICE_TYPE_CHOICES = [
    (DEVICE_TYPE_NANO_RP2040, "Arduino Nano RP2040 Connect"),
    (DEVICE_TYPE_ESP32_CYD,   "ESP32-2432S028 (CYD)"),
]

device_type = models.CharField(
    max_length=30,
    choices=DEVICE_TYPE_CHOICES,
)
```

### ~~2. Add `device_type` to `FirmwareRelease` model~~ ✓


Same choices, same field. Non-nullable in step 6.

Also change the `version` uniqueness constraint from `unique=True` on the
field to `unique_together = [("version", "device_type")]` — the same version
number must be usable independently per device type.

### ~~3. Fix `is_latest` exclusivity to be per device_type~~ ✓

Change the `save()` override in `FirmwareRelease`:

```python
def save(self, *args, **kwargs):
    if self.is_latest:
        FirmwareRelease.objects.exclude(pk=self.pk).filter(
            is_latest=True, device_type=self.device_type
        ).update(is_latest=False)
    super().save(*args, **kwargs)
```

### ~~4. Update `GET /api/v1/firmware/latest/`~~ ✓

Accept a `device_type` query parameter. Validate it against the stored type
on the Device record (looked up from API key). Return 400 on mismatch.
Select firmware by the stored type:

```python
device = api_key_obj.device
asserted_type = request.query_params.get("device_type", "")
if asserted_type != device.device_type:
    return Response(
        {"error": "device_type mismatch"},
        status=status.HTTP_400_BAD_REQUEST,
    )
release = FirmwareRelease.objects.filter(
    is_latest=True, device_type=device.device_type
).first()
```

### 5. Update `POST /api/v1/devices/register/`

Accept required `device_type` in the request body. Validate against the
choices list (`"arduino_nano_rp2040_connect"` or `"esp32_2432s028"`).

### 6. Write and apply migrations

- Migration 1: add nullable `device_type` to both models.
- Migration 2 (data migration): set all existing rows to `"arduino_nano_rp2040_connect"`.
- Migration 3: make the field non-nullable.

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
