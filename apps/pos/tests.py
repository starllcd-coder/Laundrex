from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
class PosSmokeTests(TestCase):
    def test_pos_requires_login(self):
        response = self.client.get(reverse("pos:new_order"))
        self.assertEqual(response.status_code, 302)

    def test_pos_loads_when_logged_in(self):
        User = get_user_model()
        user = User.objects.create_user(username="pos_user", password="testpass123")
        self.client.force_login(user)
        response = self.client.get(reverse("pos:new_order"))
        self.assertEqual(response.status_code, 200)
