from django.db import migrations

NANO = "arduino_nano_rp2040_connect"


def backfill_device_type(apps, schema_editor):
    FirmwareRelease = apps.get_model("firmware", "FirmwareRelease")
    FirmwareRelease.objects.filter(device_type__isnull=True).update(device_type=NANO)


class Migration(migrations.Migration):

    dependencies = [
        ("firmware", "0002_firmware_release_device_type_nullable"),
    ]

    operations = [
        migrations.RunPython(backfill_device_type, migrations.RunPython.noop),
    ]
