from django.db import models
from .storage import FirmwareS3Storage
from devices.models import DEVICE_TYPE_CHOICES


def firmware_upload_path(instance, filename):
    return f"releases/{instance.version}/{filename}"


class FirmwareRelease(models.Model):
    version = models.CharField(max_length=20)
    device_type = models.CharField(
        max_length=30,
        choices=DEVICE_TYPE_CHOICES,
    )
    file = models.FileField(
        storage=FirmwareS3Storage,
        upload_to=firmware_upload_path,
        blank=True,
    )
    sha256 = models.CharField(max_length=64, blank=True)
    changelog = models.TextField(blank=True)
    published_at = models.DateTimeField(auto_now_add=True)
    is_latest = models.BooleanField(default=False)

    class Meta:
        ordering = ["-published_at"]
        unique_together = [("version", "device_type")]

    def __str__(self):
        return self.version

    def save(self, *args, **kwargs):
        if self.is_latest:
            FirmwareRelease.objects.exclude(pk=self.pk).filter(
                is_latest=True, device_type=self.device_type
            ).update(is_latest=False)
        super().save(*args, **kwargs)
