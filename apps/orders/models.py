import secrets
import uuid
from django.db import models
from django.db.models import Sum
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class Customer(models.Model):
    sync_uid = models.CharField(max_length=36, unique=True, default=uuid.uuid4)
    name = models.CharField(max_length=120, blank=True, default="")
    phone = models.CharField(max_length=40, blank=True, default="", db_index=True)
    vip = models.BooleanField(default=False)
    notes = models.CharField(max_length=255, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    address2 = models.CharField(max_length=255, blank=True, default="")
    points = models.PositiveIntegerField(default=0)
    vip_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    preferred_language = models.CharField(max_length=2, default="en")
    whatsapp_opt_in = models.BooleanField(default=False)
    whatsapp_number = models.CharField(max_length=40, blank=True, default="")
    whatsapp_opt_in_at = models.DateTimeField(null=True, blank=True)
    cloud_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name or self.phone or f"Customer {self.pk}"


class Order(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", _("Received")
        ACCEPTED = "ACCEPTED", _("Accepted")
        PICKUP_ASSIGNED = "PICKUP_ASSIGNED", _("Pickup assigned")
        WASHING = "WASHING", _("Washing")
        IRONING = "IRONING", _("Ironing")
        READY = "READY", _("Ready")
        OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY", _("Out for delivery")
        DELIVERED = "DELIVERED", _("Delivered")
        CANCELLED = "CANCELLED", _("Cancelled")

    class DeliveryStatus(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        ASSIGNED = "ASSIGNED", _("Assigned")
        OUT = "OUT", _("Out for delivery")
        DELIVERED = "DELIVERED", _("Delivered")
        FAILED = "FAILED", _("Failed")
        CANCELLED = "CANCELLED", _("Cancelled")

    branch = models.CharField(max_length=80, db_index=True, default="muscat")
    order_no = models.CharField(max_length=20, unique=True, db_index=True)
    pickup_token = models.CharField(max_length=64, unique=True, blank=True, null=False, db_index=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.RECEIVED)
    urgent = models.BooleanField(default=False, db_index=True)

    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    cashier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=3, default=0)

    paid = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=3, default=0)

    points_awarded = models.BooleanField(default=False)
    loyalty_points_awarded = models.PositiveIntegerField(default=0)
    points_redeemed = models.PositiveIntegerField(default=0)
    points_redeemed_value = models.DecimalField(max_digits=10, decimal_places=3, default=0)

    delivery_required = models.BooleanField(default=False, db_index=True)
    delivery_status = models.CharField(max_length=12, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING)
    delivery_address = models.CharField(max_length=255, blank=True, default="")
    delivery_zone = models.CharField(max_length=120, blank=True, default="")
    delivery_phone = models.CharField(max_length=40, blank=True, default="")
    delivery_lat = models.FloatField(null=True, blank=True)
    delivery_lng = models.FloatField(null=True, blank=True)
    delivery_slot = models.CharField(max_length=120, blank=True, default="")
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    delivery_driver_name = models.CharField(max_length=120, blank=True, default="")
    delivery_driver_phone = models.CharField(max_length=40, blank=True, default="")
    delivery_notes = models.CharField(max_length=255, blank=True, default="")
    delivered_at = models.DateTimeField(null=True, blank=True)
    estimated_ready_at = models.DateTimeField(null=True, blank=True)
    pickup_date = models.DateField(null=True, blank=True)
    pickup_slot = models.CharField(max_length=120, blank=True, default="")
    pickup_notes = models.CharField(max_length=255, blank=True, default="")
    cloud_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        permissions = [
            ("view_all_branches", _("Can view all branches")),
            ("can_discount", _("Can apply discount")),
            ("can_refund", _("Can cancel or refund orders")),
            ("can_change_status", _("Can change order status")),
            ("can_manage_delivery", _("Can manage delivery")),
            ("can_view_reports", _("Can view reports")),
            ("can_manage_staff", _("Can manage staff")),
            ("can_edit_catalog", _("Can edit catalog")),
        ]

    notes = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"#{self.order_no} ({self.branch})"

    def ensure_pickup_token(self):
        if self.pickup_token:
            return self.pickup_token
        token = secrets.token_urlsafe(18)
        while Order.objects.filter(pickup_token=token).exists():
            token = secrets.token_urlsafe(18)
        self.pickup_token = token
        self.save(update_fields=["pickup_token"])
        return token

    def save(self, *args, **kwargs):
        if not self.pickup_token:
            token = secrets.token_urlsafe(18)
            while Order.objects.filter(pickup_token=token).exists():
                token = secrets.token_urlsafe(18)
            self.pickup_token = token
        super().save(*args, **kwargs)

    def refresh_payment_totals(self):
        totals = self.payments.aggregate(amount=Sum("amount"))
        paid = totals["amount"] or 0
        self.paid = paid
        due = self.total - paid
        self.balance = due if due > 0 else 0
        self.save(update_fields=["paid", "balance", "updated_at"])

        if self.balance == 0 and not self.points_awarded:
            self.award_loyalty_points()

    def award_loyalty_points(self):
        if not self.customer or self.total <= 0:
            return
        rate = getattr(settings, "LOYALTY_POINTS_PER_OMR", 0)
        if not rate:
            return
        points = int(self.total * rate)
        if points <= 0:
            return
        self.customer.points += points
        self.customer.save(update_fields=["points"])
        self.points_awarded = True
        self.loyalty_points_awarded = points
        self.save(update_fields=["points_awarded", "loyalty_points_awarded", "updated_at"])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    item_name = models.CharField(max_length=120)
    service_name = models.CharField(max_length=120)
    qty = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    line_total = models.DecimalField(max_digits=10, decimal_places=3, default=0)

    def __str__(self):
        return f"{self.item_name} x{self.qty}"


class OrderStatusLog(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_logs")
    from_status = models.CharField(max_length=24, blank=True, default="")
    to_status = models.CharField(max_length=24, blank=True, default="")
    note = models.CharField(max_length=255, blank=True, default="")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"#{self.order.order_no}: {self.from_status} -> {self.to_status}"

    @property
    def from_status_label(self):
        if self.from_status in Order.Status.values:
            return Order.Status(self.from_status).label
        return self.from_status

    @property
    def to_status_label(self):
        if self.to_status in Order.Status.values:
            return Order.Status(self.to_status).label
        return self.to_status
