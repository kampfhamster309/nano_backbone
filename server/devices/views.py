from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import Device, DeviceAPIKey
from .permissions import HasDeviceAPIKey
from .serializers import DeviceRegistrationSerializer, DeviceSerializer


@api_view(["POST"])
@permission_classes([])
def register_device(request):
    serializer = DeviceRegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    device = serializer.save()
    _, key = DeviceAPIKey.objects.create_key(name=device.name, device=device)
    return Response(
        {
            "device": DeviceSerializer(device).data,
            "api_key": key,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
def ping(request):
    return Response({"status": "ok"})
