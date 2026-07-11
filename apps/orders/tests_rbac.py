from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.orders.models import Customer, Order


class RBACHardeningTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="rbac_user", password="testpass123")
        self.manager = User.objects.create_user(username="rbac_manager", password="testpass123")

        for codename in ("can_manage_staff", "can_edit_catalog", "can_discount", "can_change_status"):
            perm = Permission.objects.get(codename=codename)
            self.manager.user_permissions.add(perm)

        self.customer = Customer.objects.create(name="Ali", phone="+96811111111")
        self.order = Order.objects.create(
            branch="muscat",
            order_no="90001",
            customer=self.customer,
            subtotal=5,
            total=5,
            paid=0,
            balance=5,
        )

    def _login_with_branch(self, username: str, password: str):
        self.client.login(username=username, password=password)
        session = self.client.session
        session["active_branch"] = "muscat"
        session.save()

    def test_management_home_requires_permission(self):
        self._login_with_branch("rbac_user", "testpass123")
        response = self.client.get(reverse("management:home"))
        self.assertEqual(response.status_code, 403)

    def test_settings_home_requires_permission(self):
        self._login_with_branch("rbac_user", "testpass123")
        response = self.client.get(reverse("settings_app:home"))
        self.assertEqual(response.status_code, 403)

    def test_catalog_seed_requires_permission(self):
        self._login_with_branch("rbac_user", "testpass123")
        response = self.client.post(reverse("catalog:seed"))
        self.assertEqual(response.status_code, 403)

    def test_catalog_seed_allows_authorized_user(self):
        self._login_with_branch("rbac_manager", "testpass123")
        response = self.client.post(reverse("catalog:seed"))
        self.assertEqual(response.status_code, 302)

    def test_payment_detail_post_requires_permission(self):
        self._login_with_branch("rbac_user", "testpass123")
        response = self.client.post(
            reverse("payments:detail", kwargs={"order_no": self.order.order_no}),
            {"amount": "1.000", "method": "CASH"},
        )
        self.assertEqual(response.status_code, 403)

    def test_pickup_collect_payment_requires_permission(self):
        self._login_with_branch("rbac_user", "testpass123")
        response = self.client.post(
            reverse("orders:pickup"),
            {"action": "collect_payment", "order_no": self.order.order_no, "amount": "1.000", "method": "CASH"},
        )
        self.assertEqual(response.status_code, 400)

    def test_set_urgent_requires_permission(self):
        self._login_with_branch("rbac_user", "testpass123")
        response = self.client.post(
            reverse("orders:set_urgent", kwargs={"order_no": self.order.order_no}),
            {"urgent": "1"},
        )
        self.assertEqual(response.status_code, 400)

    def test_customer_detail_post_requires_permission(self):
        self._login_with_branch("rbac_user", "testpass123")
        response = self.client.post(
            reverse("orders:customer_detail", kwargs={"customer_id": self.customer.id}),
            {"name": "Updated Name"},
        )
        self.assertEqual(response.status_code, 400)
