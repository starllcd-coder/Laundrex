from django.test import TestCase, override_settings
from django.urls import reverse


class SyncEndpointTests(TestCase):
    def test_sync_pull_blocked_when_disabled(self):
        url = reverse("orders:sync_pull")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    @override_settings(SYNC_ENDPOINTS_ENABLED=True, SYNC_API_TOKEN="test-token")
    def test_sync_pull_requires_token(self):
        url = reverse("orders:sync_pull")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    @override_settings(SYNC_ENDPOINTS_ENABLED=True, SYNC_API_TOKEN="test-token")
    def test_sync_pull_ok_with_token(self):
        url = reverse("orders:sync_pull")
        response = self.client.get(url, HTTP_X_SYNC_TOKEN="test-token")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("ok"))
