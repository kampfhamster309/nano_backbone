from django.contrib import admin
from rest_framework_api_key.admin import APIKeyModelAdmin
from .models import Device, DeviceAPIKey


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ["name", "id", "created_at", "last_seen_at"]
    readonly_fields = ["id", "created_at", "last_seen_at"]


@admin.register(DeviceAPIKey)
class DeviceAPIKeyAdmin(APIKeyModelAdmin):
    list_display = [*APIKeyModelAdmin.list_display, "device"]
