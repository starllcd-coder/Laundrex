from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Branch(models.Model):
	code = models.CharField(max_length=40, unique=True)
	name = models.CharField(max_length=120)
	name_ar = models.CharField(max_length=120, blank=True, default="")
	active = models.BooleanField(default=True)
	address = models.CharField(max_length=255, blank=True, default="")
	address_ar = models.CharField(max_length=255, blank=True, default="")
	phone = models.CharField(max_length=40, blank=True, default="")
	tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
	allow_discounts = models.BooleanField(default=True)
	max_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=30)
	receipt_header = models.CharField(max_length=255, blank=True, default="")
	receipt_footer = models.CharField(max_length=255, blank=True, default="")
	receipt_footer_ar = models.CharField(max_length=255, blank=True, default="")
	receipt_logo = models.FileField(upload_to="branch_receipt_logos/", blank=True, null=True)
	cr_number = models.CharField(max_length=120, blank=True, default="")
	vat_number = models.CharField(max_length=120, blank=True, default="")
	printer_name = models.CharField(max_length=120, blank=True, default="")
	receipt_copies = models.PositiveIntegerField(default=1)
	receipt_template = models.CharField(max_length=10, default="80mm")
	delivery_slot_templates = models.TextField(blank=True, default="")

	def __str__(self):
		return f"{self.name} ({self.code})"


class AuditLog(models.Model):
	action = models.CharField(max_length=80)
	entity_type = models.CharField(max_length=80)
	entity_id = models.CharField(max_length=40, blank=True, default="")
	message = models.CharField(max_length=255, blank=True, default="")
	branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
	user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"{self.entity_type}:{self.entity_id} {self.action}"
