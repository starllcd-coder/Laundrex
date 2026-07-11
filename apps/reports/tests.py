from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse


class ReportsSmokeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="report_user", password="testpass123")

    def test_reports_requires_login(self):
        response = self.client.get(reverse("reports:home"))
        self.assertEqual(response.status_code, 302)

    def test_reports_requires_permission(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("reports:home"))
        self.assertEqual(response.status_code, 403)

    def test_reports_loads_with_permission(self):
        perm = Permission.objects.get(codename="can_view_reports")
        self.user.user_permissions.add(perm)
        self.client.force_login(self.user)
        response = self.client.get(reverse("reports:home"))
        self.assertEqual(response.status_code, 200)
