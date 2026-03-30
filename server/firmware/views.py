from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from devices.models import DeviceAPIKey
from devices.permissions import HasDeviceAPIKey
from .models import FirmwareRelease
from .utils import generate_presigned_url


@api_view(["GET"])
def latest_firmware(request):
    # Identify the requesting device from its API key.
    key_str = HasDeviceAPIKey().get_key(request)
    try:
        api_key_obj = DeviceAPIKey.objects.get_from_key(key_str)
    except DeviceAPIKey.DoesNotExist:
        return Response(status=status.HTTP_403_FORBIDDEN)

    device = api_key_obj.device

    # Sanity-check: device asserts its own type; reject if it disagrees with
    # what was stored at registration time.
    asserted_type = request.query_params.get("device_type", "")
    if asserted_type and asserted_type != device.device_type:
        return Response(
            {"detail": "device_type mismatch."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        release = FirmwareRelease.objects.get(
            is_latest=True, device_type=device.device_type
        )
    except FirmwareRelease.DoesNotExist:
        return Response(
            {"detail": "No firmware release available."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not release.file:
        return Response(
            {"detail": "Firmware file not available."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    url = generate_presigned_url(release.file.name)
    return Response({
        "version": release.version,
        "url": url,
        "sha256": release.sha256,
        "changelog": release.changelog,
    })
