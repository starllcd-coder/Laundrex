from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import serializers

from apps.catalog.models import BranchItemServicePrice
from apps.management.models import Branch
from apps.orders.models import Customer, Order, OrderItem, OrderStatusLog
from apps.payments.models import Payment
from .models import CustomerAccount, SavedAddress, MobileOrderMeta, MobileEvent, MobileNotification


class BranchSerializer(serializers.ModelSerializer):
    city = serializers.SerializerMethodField()
    area = serializers.SerializerMethodField()
    address = serializers.CharField()
    supports_urgent = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = ["id", "code", "name", "name_ar", "phone", "address", "city", "area", "tax_rate", "supports_urgent"]

    def get_city(self, obj):
        # Keep city stable even if branch display name changes (e.g. branding rename).
        code_city_map = {
            "SLL": "Salalah",
            "MCT": "Muscat",
            "SEB": "Seeb",
            "SOH": "Sohar",
            "NZW": "Nizwa",
            "SR": "Sur",
            "BRK": "Barka",
            "RUS": "Rustaq",
            "IBR": "Ibri",
            "KHS": "Khasab",
            "BRM": "Buraimi",
            "DQM": "Duqm",
            "ADM": "Adam",
            "THM": "Thumrait",
            "HMA": "Haima",
        }
        code = (obj.code or "").strip().upper()
        if code in code_city_map:
            return code_city_map[code]
        return (obj.name or "").strip() or "Oman"

    def get_area(self, obj):
        return (obj.address or "").strip() or "Oman"

    def get_supports_urgent(self, obj):
        return True


class CatalogRowSerializer(serializers.ModelSerializer):
    item_id = serializers.IntegerField(source="item.id")
    item_name = serializers.SerializerMethodField()
    item_name_ar = serializers.CharField(source="item.name_ar")
    service_id = serializers.IntegerField(source="service.id")
    service_name = serializers.SerializerMethodField()
    service_name_ar = serializers.CharField(source="service.name_ar")

    class Meta:
        model = BranchItemServicePrice
        fields = ["id", "item_id", "item_name", "item_name_ar", "service_id", "service_name", "service_name_ar", "price"]

    def _is_ar(self):
        request = self.context.get("request")
        lang = getattr(request, "LANGUAGE_CODE", "") if request else ""
        return str(lang).lower().startswith("ar")

    def get_item_name(self, obj):
        if self._is_ar() and obj.item.name_ar:
            return obj.item.name_ar
        return obj.item.name

    def get_service_name(self, obj):
        if self._is_ar() and obj.service.name_ar:
            return obj.service.name_ar
        return obj.service.name


class SavedAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedAddress
        fields = [
            "id", "label", "city", "area", "address_line_1", "address_line_2", "building", "is_default",
            "latitude", "longitude",
            "created_at", "updated_at",
        ]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email"]


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "name", "phone", "vip", "points", "preferred_language"]


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["id", "item_name", "service_name", "qty", "price", "line_total"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    promo_code = serializers.SerializerMethodField()
    promo_discount = serializers.SerializerMethodField()
    points_used = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    transfer_reference = serializers.SerializerMethodField()
    receipt_name = serializers.SerializerMethodField()
    fulfillment_mode = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id", "order_no", "branch", "status", "urgent", "subtotal", "discount", "tax", "total",
            "paid", "balance", "delivery_required", "delivery_status", "delivery_address", "delivery_phone",
            "delivery_slot", "delivery_fee", "delivery_driver_name", "delivery_driver_phone", "delivery_notes",
            "notes", "created_at", "updated_at", "items",
            "promo_code", "promo_discount", "points_used", "payment_method", "transfer_reference", "receipt_name", "fulfillment_mode",
        ]

    def _meta(self, obj):
        return getattr(obj, "mobile_meta", None)

    def get_promo_code(self, obj):
        meta = self._meta(obj)
        return meta.promo_code if meta else ""

    def get_promo_discount(self, obj):
        meta = self._meta(obj)
        return meta.promo_discount if meta else 0

    def get_points_used(self, obj):
        meta = self._meta(obj)
        return meta.points_used if meta else 0

    def get_payment_method(self, obj):
        meta = self._meta(obj)
        return meta.payment_method if meta else ""

    def get_transfer_reference(self, obj):
        meta = self._meta(obj)
        return meta.transfer_reference if meta else ""

    def get_receipt_name(self, obj):
        meta = self._meta(obj)
        return meta.receipt_name if meta else ""

    def get_fulfillment_mode(self, obj):
        meta = self._meta(obj)
        return meta.fulfillment_mode if meta else "DELIVERY"


class OrderTrackingLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusLog
        fields = ["id", "from_status", "to_status", "note", "created_at"]


class RegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=40)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(min_length=6)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class ProfileUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=40)
    preferred_language = serializers.ChoiceField(choices=["en", "ar"], required=False)


class ForgotPasswordSerializer(serializers.Serializer):
    phone = serializers.CharField(required=False, allow_blank=True)
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, data):
        if not (data.get("phone") or data.get("username") or data.get("email")):
            raise serializers.ValidationError("Provide phone, username, or email.")
        return data


class ResetPasswordSerializer(serializers.Serializer):
    phone = serializers.CharField()
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(min_length=6)


class OtpSendSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=40)
    purpose = serializers.ChoiceField(choices=["login", "register", "reset"], default="login")


class OtpVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=40)
    code = serializers.CharField(max_length=6)
    purpose = serializers.ChoiceField(choices=["login", "register", "reset"], default="login")


class SocialLoginSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=["google", "apple"])
    id_token = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    full_name = serializers.CharField(required=False, allow_blank=True)


class AnalyticsEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = MobileEvent
        fields = ["name", "payload"]


class MobileNotificationSerializer(serializers.ModelSerializer):
    order_no = serializers.SerializerMethodField()

    class Meta:
        model = MobileNotification
        fields = ["id", "title", "message", "event_code", "is_read", "created_at", "read_at", "order_no"]

    def get_order_no(self, obj):
        return obj.order.order_no if obj.order else ""


class OrderCreateLineSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    service_id = serializers.IntegerField()
    qty = serializers.IntegerField(min_value=1)


class OrderCreateSerializer(serializers.Serializer):
    laundry_id = serializers.IntegerField(required=False)
    laundry_shop_id = serializers.IntegerField(required=False)
    items = OrderCreateLineSerializer(many=True, required=False)
    lines = OrderCreateLineSerializer(many=True, required=False)
    urgent = serializers.BooleanField(default=False)
    speed = serializers.CharField(required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(choices=["COD", "BANK", "BANK_TRANSFER", "CARD", "APPLE_PAY", "GOOGLE_PAY"], default="COD")
    address_id = serializers.IntegerField(required=False, allow_null=True)
    delivery_slot = serializers.CharField(required=False, allow_blank=True)
    pickup_time_slot = serializers.CharField(required=False, allow_blank=True)
    fulfillment_mode = serializers.ChoiceField(choices=["DELIVERY", "PICKUP"], required=False, default="DELIVERY")
    notes = serializers.CharField(required=False, allow_blank=True)
    customer_notes = serializers.CharField(required=False, allow_blank=True)
    promo_code = serializers.CharField(required=False, allow_blank=True)
    promo_discount = serializers.DecimalField(required=False, max_digits=10, decimal_places=3)
    points_used = serializers.IntegerField(required=False)
    transfer_reference = serializers.CharField(required=False, allow_blank=True)
    receipt_name = serializers.CharField(required=False, allow_blank=True)

    def validate_laundry_id(self, value):
        if not Branch.objects.filter(id=value, active=True).exists():
            raise serializers.ValidationError("Invalid laundry branch.")
        return value

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required.")
        return value

    def validate(self, data):
        laundry_id = data.get("laundry_id") or data.get("laundry_shop_id")
        items = data.get("items") or data.get("lines")
        if not laundry_id:
            raise serializers.ValidationError("Laundry ID is required.")
        if not items:
            raise serializers.ValidationError("At least one item is required.")
        return data
