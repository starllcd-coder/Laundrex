from django.db import models

from apps.orders.models import Order, Customer


class WhatsAppSettings(models.Model):
	enabled = models.BooleanField(default=False)
	sender_name = models.CharField(max_length=120, blank=True, default="")
	allow_manual_send = models.BooleanField(default=True)
	allow_auto_send = models.BooleanField(default=False)

	def __str__(self):
		return "WhatsApp Settings"


class WhatsAppTemplate(models.Model):
	key = models.CharField(max_length=40, unique=True)
	name = models.CharField(max_length=120)
	enabled = models.BooleanField(default=True)
	template_name_en = models.CharField(max_length=120, blank=True, default="")
	template_name_ar = models.CharField(max_length=120, blank=True, default="")
	body_en = models.TextField(blank=True, default="")
	body_ar = models.TextField(blank=True, default="")

	def __str__(self):
		return self.name


class WhatsAppMessageLog(models.Model):
	STATUS_CHOICES = [
		("queued", "Queued"),
		("sent", "Sent"),
		("delivered", "Delivered"),
		("read", "Read"),
		("failed", "Failed"),
	]

	order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)
	customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
	template_key = models.CharField(max_length=40)
	language = models.CharField(max_length=5, default="en")
	to_number = models.CharField(max_length=40)
	message_body = models.TextField(blank=True, default="")
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
	provider_message_id = models.CharField(max_length=120, blank=True, default="")
	attempts = models.PositiveIntegerField(default=0)
	last_error = models.CharField(max_length=255, blank=True, default="")
	last_status_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"{self.template_key} {self.to_number}"


class SyncSettings(models.Model):
	enabled = models.BooleanField(default=False)
	endpoints_enabled = models.BooleanField(default=False)
	api_token = models.CharField(max_length=120, blank=True, default="")
	cloud_base_url = models.CharField(max_length=255, blank=True, default="")
	interval_seconds = models.PositiveIntegerField(default=120)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return "Sync Settings"


class BankTransferSettings(models.Model):
	enabled = models.BooleanField(default=True)
	bank_name = models.CharField(max_length=120, blank=True, default="")
	account_name = models.CharField(max_length=120, blank=True, default="")
	account_number = models.CharField(max_length=120, blank=True, default="")
	iban = models.CharField(max_length=120, blank=True, default="")
	instructions = models.TextField(blank=True, default="")
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return "Bank Transfer Settings"
