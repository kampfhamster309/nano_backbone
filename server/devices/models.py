import uuid
from django.db import models
from rest_framework_api_key.models import AbstractAPIKey


class Device(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
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
