from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Device, DeviceAPIKey, UpdateEvent, DEVICE_TYPE_NANO_RP2040

NANO = DEVICE_TYPE_NANO_RP2040
REGISTER_URL = "device-register"


class DeviceRegistrationTests(APITestCase):
    def test_register_device_returns_201_and_api_key(self):
        response = self.client.post(
            reverse(REGISTER_URL),
            {"name": "test-device", "device_type": NANO},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertIn("api_key", data)
        self.assertIn("device", data)
        self.assertEqual(data["device"]["name"], "test-device")
        self.assertEqual(data["device"]["device_type"], NANO)
        # API key must be non-empty and only returned once
        self.assertTrue(len(data["api_key"]) > 0)

    def test_register_device_creates_db_records(self):
        self.client.post(
            reverse(REGISTER_URL),
            {"name": "test-device", "device_type": NANO},
            format="json",
        )
        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(DeviceAPIKey.objects.count(), 1)
        self.assertEqual(DeviceAPIKey.objects.first().device.name, "test-device")

    def test_register_duplicate_name_returns_400(self):
        self.client.post(
            reverse(REGISTER_URL),
            {"name": "test-device", "device_type": NANO},
            format="json",
        )
        response = self.client.post(
            reverse(REGISTER_URL),
            {"name": "test-device", "device_type": NANO},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_missing_name_returns_400(self):
        response = self.client.post(
            reverse(REGISTER_URL), {"device_type": NANO}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_missing_device_type_returns_400(self):
        response = self.client.post(
            reverse(REGISTER_URL), {"name": "test-device"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_invalid_device_type_returns_400(self):
        response = self.client.post(
            reverse(REGISTER_URL),
            {"name": "test-device", "device_type": "unknown_device"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PingTests(APITestCase):
    def setUp(self):
        response = self.client.post(
            reverse(REGISTER_URL),
            {"name": "test-device", "device_type": NANO},
            format="json",
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


class UpdateEventTests(APITestCase):
    def setUp(self):
        response = self.client.post(
            reverse(REGISTER_URL),
            {"name": "test-device", "device_type": NANO},
            format="json",
        )
        self.api_key = response.json()["api_key"]
        self.auth = {"HTTP_AUTHORIZATION": f"Api-Key {self.api_key}"}

    def test_update_success_returns_201(self):
        response = self.client.post(
            reverse("device-event"),
            {"event": "update_success", "version": "1.0.1"},
            format="json",
            **self.auth,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_update_failed_returns_201(self):
        response = self.client.post(
            reverse("device-event"),
            {"event": "update_failed", "version": "1.0.1"},
            format="json",
            **self.auth,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_event_is_persisted_to_db(self):
        self.client.post(
            reverse("device-event"),
            {"event": "update_success", "version": "1.0.1"},
            format="json",
            **self.auth,
        )
        self.assertEqual(UpdateEvent.objects.count(), 1)
        ev = UpdateEvent.objects.first()
        self.assertEqual(ev.event, "update_success")
        self.assertEqual(ev.version, "1.0.1")
        self.assertEqual(ev.device.name, "test-device")

    def test_invalid_event_type_returns_400(self):
        response = self.client.post(
            reverse("device-event"),
            {"event": "rebooted", "version": "1.0.0"},
            format="json",
            **self.auth,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_returns_403(self):
        response = self.client.post(
            reverse("device-event"),
            {"event": "update_success", "version": "1.0.0"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_version_is_optional(self):
        response = self.client.post(
            reverse("device-event"),
            {"event": "update_failed"},
            format="json",
            **self.auth,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(UpdateEvent.objects.first().version, "")
