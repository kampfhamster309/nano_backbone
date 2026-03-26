from django.contrib import admin
from .models import FirmwareRelease
from .utils import compute_sha256


@admin.register(FirmwareRelease)
class FirmwareReleaseAdmin(admin.ModelAdmin):
    list_display = ["version", "is_latest", "published_at", "sha256"]
    readonly_fields = ["published_at", "sha256"]
    list_filter = ["is_latest"]

    def save_model(self, request, obj, form, change):
        if "file" in form.changed_data and form.cleaned_data.get("file"):
            obj.sha256 = compute_sha256(form.cleaned_data["file"])
        super().save_model(request, obj, form, change)
