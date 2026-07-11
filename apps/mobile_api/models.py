from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.orders.models import Customer


class CustomerAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_account")
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name="account")
    phone = models.CharField(max_length=40, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.customer.name or self.phone or self.user.username


class SavedAddress(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="saved_addresses")
    label = models.CharField(max_length=80, default="Home")
    city = models.CharField(max_length=120, blank=True, default="")
    area = models.CharField(max_length=120, blank=True, default="")
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, default="")
    building = models.CharField(max_length=120, blank=True, default="")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-updated_at"]

    def __str__(self):
        return f"{self.label} - {self.customer}"


class PhoneOTP(models.Model):
    PURPOSE_CHOICES = (
        ("login", "Login"),
        ("register", "Register"),
        ("reset", "Reset Password"),
    )

    phone = models.CharField(max_length=40, db_index=True)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default="login")
    code = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.phone} {self.purpose}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at


class DeviceToken(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="device_tokens")
    token = models.CharField(max_length=255)
    platform = models.CharField(max_length=40, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("customer", "token")


class MobileOrderMeta(models.Model):
    order = models.OneToOneField("orders.Order", on_delete=models.CASCADE, related_name="mobile_meta")
    payment_method = models.CharField(max_length=20, blank=True, default="")
    fulfillment_mode = models.CharField(max_length=20, blank=True, default="DELIVERY")
    transfer_reference = models.CharField(max_length=120, blank=True, default="")
    receipt_name = models.CharField(max_length=255, blank=True, default="")
    promo_code = models.CharField(max_length=40, blank=True, default="")
    promo_discount = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    points_used = models.PositiveIntegerField(default=0)
    customer_notes = models.CharField(max_length=255, blank=True, default="")
    pickup_time_slot = models.CharField(max_length=120, blank=True, default="")
    speed = models.CharField(max_length=12, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)


class MobileEvent(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="mobile_events")
    name = models.CharField(max_length=120, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class MobileNotification(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="mobile_notifications")
    order = models.ForeignKey("orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="mobile_notifications")
    title = models.CharField(max_length=140)
    message = models.CharField(max_length=255)
    event_code = models.CharField(max_length=40, blank=True, default="")
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
