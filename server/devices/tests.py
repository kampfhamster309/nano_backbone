from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Device, DeviceAPIKey


class DeviceRegistrationTests(APITestCase):
    def test_register_device_returns_201_and_api_key(self):
        response = self.client.post(
            reverse("device-register"), {"name": "test-device"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertIn("api_key", data)
        self.assertIn("device", data)
        self.assertEqual(data["device"]["name"], "test-device")
        # API key must be non-empty and only returned once
        self.assertTrue(len(data["api_key"]) > 0)

    def test_register_device_creates_db_records(self):
        self.client.post(
            reverse("device-register"), {"name": "test-device"}, format="json"
        )
        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(DeviceAPIKey.objects.count(), 1)
        self.assertEqual(DeviceAPIKey.objects.first().device.name, "test-device")

    def test_register_duplicate_name_returns_400(self):
        self.client.post(
            reverse("device-register"), {"name": "test-device"}, format="json"
        )
        response = self.client.post(
            reverse("device-register"), {"name": "test-device"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_missing_name_returns_400(self):
        response = self.client.post(reverse("device-register"), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PingTests(APITestCase):
    def setUp(self):
        response = self.client.post(
            reverse("device-register"), {"name": "test-device"}, format="json"
        )
        self.api_key = response.json()["api_key"]

    def test_ping_with_valid_key_returns_200(self):
        response = self.client.get(
            reverse("ping"),
            HTTP_AUTHORIZATION=f"Api-Key {self.api_key}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_ping_without_key_returns_403(self):
        response = self.client.get(reverse("ping"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ping_with_invalid_key_returns_403(self):
        response = self.client.get(
            reverse("ping"),
            HTTP_AUTHORIZATION="Api-Key invalid-key-value",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ping_updates_last_seen_at(self):
        device = Device.objects.get(name="test-device")
        self.assertIsNone(device.last_seen_at)

        self.client.get(
            reverse("ping"),
            HTTP_AUTHORIZATION=f"Api-Key {self.api_key}",
        )

        device.refresh_from_db()
        self.assertIsNotNone(device.last_seen_at)
