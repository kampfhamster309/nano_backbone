from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import Device, DeviceAPIKey, UpdateEvent
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


@api_view(["POST"])
def report_event(request):
    """Device reports the outcome of a firmware update attempt.

    The device is identified from its API key — no device ID is required in
    the URL or body. Accepted events: ``update_success``, ``update_failed``.
    """
    key_str = HasDeviceAPIKey().get_key(request)
    try:
        api_key_obj = DeviceAPIKey.objects.get_from_key(key_str)
    except DeviceAPIKey.DoesNotExist:
        return Response(status=status.HTTP_403_FORBIDDEN)

    event = request.data.get("event", "")
    if event not in (UpdateEvent.EVENT_SUCCESS, UpdateEvent.EVENT_FAILED):
        return Response(
            {"error": "event must be 'update_success' or 'update_failed'"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    version = request.data.get("version", "")
    UpdateEvent.objects.create(
        device=api_key_obj.device,
        event=event,
        version=version,
    )
    return Response({"status": "ok"}, status=status.HTTP_201_CREATED)
