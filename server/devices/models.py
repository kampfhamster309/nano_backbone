import uuid
from django.db import models
from rest_framework_api_key.models import AbstractAPIKey

DEVICE_TYPE_NANO_RP2040 = "arduino_nano_rp2040_connect"
DEVICE_TYPE_ESP32_CYD = "esp32_2432s028"
DEVICE_TYPE_CHOICES = [
    (DEVICE_TYPE_NANO_RP2040, "Arduino Nano RP2040 Connect"),
    (DEVICE_TYPE_ESP32_CYD, "ESP32-2432S028 (CYD)"),
]


class Device(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    # Nullable during migration only — becomes non-nullable in step 6.
    device_type = models.CharField(
        max_length=30,
        choices=DEVICE_TYPE_CHOICES,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class DeviceAPIKey(AbstractAPIKey):
    device = models.OneToOneField(
        Device, on_delete=models.CASCADE, related_name="api_key"
    )

    class Meta(AbstractAPIKey.Meta):
        verbose_name = "Device API key"
        verbose_name_plural = "Device API keys"


class UpdateEvent(models.Model):
    EVENT_SUCCESS = "update_success"
    EVENT_FAILED = "update_failed"
    EVENT_CHOICES = [
        (EVENT_SUCCESS, "Update success"),
        (EVENT_FAILED, "Update failed"),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="events")
    event = models.CharField(max_length=20, choices=EVENT_CHOICES)
    version = models.CharField(max_length=20, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.device.name} — {self.event} ({self.version})"
