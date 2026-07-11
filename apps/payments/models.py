from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from apps.orders.models import Order

User = get_user_model()


class Payment(models.Model):
	class Method(models.TextChoices):
		CASH = "CASH", _("Cash")
		CARD = "CARD", _("Card")
		WALLET = "WALLET", _("Wallet")
		BANK = "BANK", _("Bank Transfer")

	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
	method = models.CharField(max_length=10, choices=Method.choices, default=Method.CASH)
	amount = models.DecimalField(max_digits=10, decimal_places=3, default=0)
	reference = models.CharField(max_length=120, blank=True, default="")
	note = models.CharField(max_length=255, blank=True, default="")
	proof = models.FileField(upload_to="payment_proofs/", blank=True, null=True)
	created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"#{self.order.order_no} {self.method} {self.amount}"
