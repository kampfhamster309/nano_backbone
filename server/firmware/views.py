from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import FirmwareRelease
from .utils import generate_presigned_url


@api_view(["GET"])
def latest_firmware(request):
    try:
        release = FirmwareRelease.objects.get(is_latest=True)
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
