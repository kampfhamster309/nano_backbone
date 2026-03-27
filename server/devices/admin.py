from django.contrib import admin
from rest_framework_api_key.admin import APIKeyModelAdmin
from .models import Device, DeviceAPIKey, UpdateEvent


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ["name", "id", "created_at", "last_seen_at"]
    readonly_fields = ["id", "created_at", "last_seen_at"]


@admin.register(DeviceAPIKey)
class DeviceAPIKeyAdmin(APIKeyModelAdmin):
    list_display = [*APIKeyModelAdmin.list_display, "device"]


@admin.register(UpdateEvent)
class UpdateEventAdmin(admin.ModelAdmin):
    list_display = ["device", "event", "version", "timestamp"]
    list_filter = ["event"]
    readonly_fields = ["device", "event", "version", "timestamp"]
