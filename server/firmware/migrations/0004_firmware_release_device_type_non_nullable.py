from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("firmware", "0003_backfill_device_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="firmwarerelease",
            name="device_type",
            field=models.CharField(
                choices=[
                    ("arduino_nano_rp2040_connect", "Arduino Nano RP2040 Connect"),
                    ("esp32_2432s028", "ESP32-2432S028 (CYD)"),
                ],
                max_length=30,
            ),
        ),
    ]
