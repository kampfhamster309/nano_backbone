from rest_framework import serializers
from .models import Device


class DeviceRegistrationSerializer(serializers.ModelSerializer):
    device_type = serializers.ChoiceField(choices=Device._meta.get_field("device_type").choices)

    class Meta:
        model = Device
        fields = ["name", "device_type"]


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ["id", "name", "device_type", "created_at", "last_seen_at"]
