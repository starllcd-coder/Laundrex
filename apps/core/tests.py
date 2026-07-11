from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class CoreSmokeTests(TestCase):
    def test_home_redirects_when_logged_out(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_home_loads_when_logged_in(self):
        User = get_user_model()
        user = User.objects.create_user(username="smoke_user", password="testpass123")
        self.client.force_login(user)
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
