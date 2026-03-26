from django.utils import timezone
from rest_framework_api_key.permissions import BaseHasAPIKey
from .models import DeviceAPIKey


class HasDeviceAPIKey(BaseHasAPIKey):
    model = DeviceAPIKey

    def has_permission(self, request, view):
        allowed = super().has_permission(request, view)
        if allowed:
            key_str = self.get_key(request)
            try:
                api_key = DeviceAPIKey.objects.get_from_key(key_str)
                api_key.device.last_seen_at = timezone.now()
                api_key.device.save(update_fields=["last_seen_at"])
            except DeviceAPIKey.DoesNotExist:
                pass
        return allowed
