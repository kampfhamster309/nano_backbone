from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import FirmwareRelease

MOCK_PRESIGNED_URL = "https://minio:9000/firmware/releases/1.0.0/fw.zip?X-Amz-Signature=abc"


class FirmwareReleaseModelTests(APITestCase):
    def test_setting_is_latest_clears_previous_latest(self):
        FirmwareRelease.objects.create(version="1.0.0", is_latest=True)
        FirmwareRelease.objects.create(version="1.0.1", is_latest=True)
        self.assertFalse(FirmwareRelease.objects.get(version="1.0.0").is_latest)
        self.assertTrue(FirmwareRelease.objects.get(version="1.0.1").is_latest)

    def test_only_one_latest_at_a_time(self):
        for v in ["1.0.0", "1.0.1", "1.0.2"]:
            FirmwareRelease.objects.create(version=v, is_latest=True)
        self.assertEqual(FirmwareRelease.objects.filter(is_latest=True).count(), 1)

    def test_non_latest_release_does_not_clear_existing_latest(self):
        FirmwareRelease.objects.create(version="1.0.0", is_latest=True)
        FirmwareRelease.objects.create(version="1.0.1", is_latest=False)
        self.assertTrue(FirmwareRelease.objects.get(version="1.0.0").is_latest)


class FirmwareLatestEndpointTests(APITestCase):
    def setUp(self):
        response = self.client.post(
            reverse("device-register"), {"name": "test-device"}, format="json"
        )
        self.auth = {"HTTP_AUTHORIZATION": f"Api-Key {response.json()['api_key']}"}

    def test_no_latest_release_returns_404(self):
        response = self.client.get(reverse("firmware-latest"), **self.auth)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_release_with_no_file_returns_503(self):
        FirmwareRelease.objects.create(version="1.0.0", is_latest=True)
        response = self.client.get(reverse("firmware-latest"), **self.auth)
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    @patch("firmware.views.generate_presigned_url", return_value=MOCK_PRESIGNED_URL)
    def test_returns_correct_metadata(self, _mock):
        release = FirmwareRelease.objects.create(
            version="1.0.0",
            sha256="a" * 64,
            changelog="Initial release",
            is_latest=True,
        )
        release.file.name = "releases/1.0.0/fw.zip"
        release.save()

        response = self.client.get(reverse("firmware-latest"), **self.auth)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["version"], "1.0.0")
        self.assertEqual(data["url"], MOCK_PRESIGNED_URL)
        self.assertEqual(data["sha256"], "a" * 64)
        self.assertEqual(data["changelog"], "Initial release")

    @patch("firmware.views.generate_presigned_url", return_value=MOCK_PRESIGNED_URL)
    def test_returns_latest_not_most_recent(self, _mock):
        older = FirmwareRelease.objects.create(version="1.0.0", is_latest=False)
        older.file.name = "releases/1.0.0/fw.zip"
        older.save()

        newer = FirmwareRelease.objects.create(version="1.0.1", is_latest=True)
        newer.file.name = "releases/1.0.1/fw.zip"
        newer.save()

        response = self.client.get(reverse("firmware-latest"), **self.auth)
        self.assertEqual(response.json()["version"], "1.0.1")

    def test_unauthenticated_returns_403(self):
        response = self.client.get(reverse("firmware-latest"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
