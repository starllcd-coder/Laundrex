import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import authenticate
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.catalog.models import BranchItemServicePrice, ItemServicePrice
from apps.management.models import Branch
from apps.orders.models import Customer, Order, OrderItem, OrderStatusLog
from apps.payments.models import Payment
from apps.settings_app.models import BankTransferSettings
from .models import CustomerAccount, SavedAddress, PhoneOTP, DeviceToken, MobileOrderMeta, MobileEvent, MobileNotification
from .serializers import (
    AnalyticsEventSerializer, BranchSerializer, CatalogRowSerializer, ForgotPasswordSerializer, LoginSerializer,
    MobileNotificationSerializer, OtpSendSerializer, OtpVerifySerializer, OrderCreateSerializer, OrderSerializer, OrderTrackingLogSerializer,
    ProfileUpdateSerializer, RegisterSerializer, ResetPasswordSerializer, SavedAddressSerializer, SocialLoginSerializer, UserSerializer,
)


def _get_bank_settings_safe():
    try:
        return BankTransferSettings.objects.first()
    except (OperationalError, ProgrammingError):
        return None


class AllowAnyPost(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method == "POST" or request.user and request.user.is_authenticated


def _tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


def _customer_from_request(request):
    account = getattr(request.user, "customer_account", None)
    return account.customer if account else None


def _notify_customer(customer, title, message, event_code="", order=None):
    if not customer:
        return
    MobileNotification.objects.create(
        customer=customer,
        order=order,
        title=title[:140],
        message=message[:255],
        event_code=(event_code or "")[:40],
    )


def _next_order_no():
    last = Order.objects.order_by("-id").first()
    if not last:
        return "1001"
    try:
        return str(int(last.order_no) + 1)
    except Exception:
        return str(last.id + 1001)


def _paginate_list(data, request):
    raw_page = request.query_params.get("page")
    if not raw_page:
        return data
    try:
        page = max(int(raw_page), 1)
    except Exception:
        page = 1
    try:
        page_size = max(int(request.query_params.get("page_size", 20)), 1)
    except Exception:
        page_size = 20
    page_size = min(page_size, 100)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "count": len(data),
        "page": page,
        "page_size": page_size,
        "results": data[start:end],
    }


def _compute_order_totals(branch, lines, urgent_flag, speed, promo_discount, points_used):
    subtotal = Decimal("0")
    priced_lines = []
    for line in lines:
        price_row = BranchItemServicePrice.objects.filter(
            branch=branch, item_id=line["item_id"], service_id=line["service_id"]
        ).select_related("item", "service").first()
        if not price_row:
            # Fallback to global price map when branch-specific rows are not synced yet.
            price_row = ItemServicePrice.objects.filter(
                item_id=line["item_id"], service_id=line["service_id"]
            ).select_related("item", "service").first()
        if not price_row:
            raise ValueError("One or more selected items are not available for this branch.")
        qty = int(line["qty"])
        line_total = Decimal(qty) * price_row.price
        subtotal += line_total
        priced_lines.append((price_row, qty, line_total))

    if speed == "URGENT":
        urgent_flag = True
    urgent_fee = Decimal("0")
    if urgent_flag:
        urgent_fee = (subtotal * Decimal("0.30")).quantize(Decimal("0.001"))

    promo_discount = Decimal(str(promo_discount or "0"))
    if promo_discount < 0:
        promo_discount = Decimal("0")
    if promo_discount > subtotal:
        promo_discount = subtotal

    points_used = int(points_used or 0)
    points_value = Decimal(points_used) * Decimal("0.01") if points_used > 0 else Decimal("0")
    if points_value > (subtotal + urgent_fee - promo_discount):
        points_value = subtotal + urgent_fee - promo_discount
        points_used = int((points_value / Decimal("0.01")).to_integral_value())

    tax_rate = Decimal(str(branch.tax_rate or 0))
    tax = (subtotal * tax_rate / Decimal("100")).quantize(Decimal("0.001")) if tax_rate > 0 else Decimal("0")
    total = subtotal + urgent_fee + tax - promo_discount - points_value
    if total < 0:
        total = Decimal("0")

    return {
        "subtotal": subtotal,
        "urgent_fee": urgent_fee,
        "promo_discount": promo_discount,
        "points_used": points_used,
        "points_value": points_value,
        "tax": tax,
        "total": total,
        "priced_lines": priced_lines,
        "urgent_flag": bool(urgent_flag),
    }


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        phone = data["phone"].strip()
        email = data.get("email", "").strip()
        full_name = data["full_name"].strip()

        if CustomerAccount.objects.filter(phone=phone).exists():
            return Response({"detail": "An account with this phone already exists."}, status=400)

        username_base = phone.replace("+", "").replace(" ", "") or f"cust{random.randint(1000,9999)}"
        username = username_base
        idx = 1
        while User.objects.filter(username=username).exists():
            idx += 1
            username = f"{username_base}{idx}"

        with transaction.atomic():
            customer, _ = Customer.objects.get_or_create(phone=phone, defaults={"name": full_name})
            customer.name = full_name or customer.name
            customer.save(update_fields=["name"])

            user = User.objects.create_user(
                username=username,
                email=email,
                password=data["password"],
                first_name=full_name,
            )
            CustomerAccount.objects.create(user=user, customer=customer, phone=phone)

        return Response({
            "user": UserSerializer(user).data,
            "tokens": _tokens_for_user(user),
        }, status=201)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"].strip()
        password = serializer.validated_data["password"]

        user = authenticate(request, username=username, password=password)
        if user is None:
            account = CustomerAccount.objects.filter(phone=username).select_related("user").first()
            if account:
                user = authenticate(request, username=account.user.username, password=password)

        if user is None or not hasattr(user, "customer_account"):
            return Response({"detail": "Invalid credentials."}, status=400)

        return Response({
            "user": UserSerializer(user).data,
            "tokens": _tokens_for_user(user),
        })


class AppConfigView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        bank_settings = _get_bank_settings_safe()
        return Response({
            "google_enabled": bool(getattr(settings, "SOCIAL_GOOGLE_ENABLED", False)),
            "apple_enabled": bool(getattr(settings, "SOCIAL_APPLE_ENABLED", False)),
            "analytics_enabled": bool(getattr(settings, "ANALYTICS_ENABLED", False)),
            "bank_transfer_enabled": (
                bank_settings.enabled if bank_settings else bool(getattr(settings, "BANK_TRANSFER_ENABLED", True))
            ),
            "bank_transfer_bank_name": (
                bank_settings.bank_name if bank_settings else getattr(settings, "BANK_TRANSFER_BANK_NAME", "")
            ),
            "bank_transfer_account_name": (
                bank_settings.account_name if bank_settings else getattr(settings, "BANK_TRANSFER_ACCOUNT_NAME", "")
            ),
            "bank_transfer_account_number": (
                bank_settings.account_number if bank_settings else getattr(settings, "BANK_TRANSFER_ACCOUNT_NUMBER", "")
            ),
            "bank_transfer_iban": (
                bank_settings.iban if bank_settings else getattr(settings, "BANK_TRANSFER_IBAN", "")
            ),
            "bank_transfer_instructions": (
                bank_settings.instructions
                if bank_settings
                else getattr(
                    settings,
                    "BANK_TRANSFER_INSTRUCTIONS",
                    "Use your order number as reference and upload transfer proof if available.",
                )
            ),
        })


class SocialLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    provider = None

    def post(self, request):
        try:
            payload = request.data.copy()
        except Exception:
            payload = dict(request.data)
        if self.provider:
            payload["provider"] = self.provider
        serializer = SocialLoginSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        provider = data["provider"]
        enabled = settings.SOCIAL_GOOGLE_ENABLED if provider == "google" else settings.SOCIAL_APPLE_ENABLED
        if not enabled:
            return Response({"detail": f"{provider.title()} login is disabled."}, status=400)
        if not settings.SOCIAL_ALLOW_UNVERIFIED:
            return Response({"detail": "Social login requires server verification configuration."}, status=400)

        email = (data.get("email") or "").strip()
        full_name = (data.get("full_name") or "").strip()
        if not email:
            return Response({"detail": "Email is required for social login."}, status=400)

        user = User.objects.filter(Q(username=email) | Q(email=email)).first()
        if not user:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=User.objects.make_random_password(),
                first_name=full_name or "Customer",
            )

        account = getattr(user, "customer_account", None)
        if not account:
            customer, _ = Customer.objects.get_or_create(phone=email, defaults={"name": full_name or email})
            CustomerAccount.objects.create(user=user, customer=customer, phone=customer.phone or email)

        return Response({
            "user": UserSerializer(user).data,
            "tokens": _tokens_for_user(user),
        })


class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        phone = (data.get("phone") or "").strip()
        username = (data.get("username") or "").strip()
        email = (data.get("email") or "").strip()

        account = None
        if phone:
            account = CustomerAccount.objects.filter(phone=phone).select_related("user").first()
        if not account and username:
            user = User.objects.filter(Q(username=username) | Q(email=username)).first()
            account = getattr(user, "customer_account", None) if user else None
        if not account and email:
            user = User.objects.filter(Q(email=email) | Q(username=email)).first()
            account = getattr(user, "customer_account", None) if user else None

        generic_response = {"ok": True, "expires_in": 300}
        if not account:
            return Response(generic_response)

        code = f"{random.randint(0, 999999):06d}"
        otp = PhoneOTP.objects.create(
            phone=account.phone,
            purpose="reset",
            code=code,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        if settings.OTP_DEBUG_RETURN_CODE:
            generic_response["debug_code"] = otp.code
        return Response(generic_response)


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        phone = data["phone"].strip()
        code = data["code"]

        otp = PhoneOTP.objects.filter(
            phone=phone, purpose="reset", is_used=False
        ).order_by("-created_at").first()
        if not otp or otp.is_expired or otp.code != code:
            return Response({"detail": "Invalid or expired code."}, status=400)

        account = CustomerAccount.objects.filter(phone=phone).select_related("user").first()
        if not account:
            return Response({"detail": "Account not found."}, status=404)

        account.user.set_password(data["new_password"])
        account.user.save(update_fields=["password"])
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        return Response({"ok": True})


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        return Response({"ok": True})


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        account = getattr(request.user, "customer_account", None)
        if not account:
            return Response({"detail": "Unauthorized"}, status=401)
        customer = account.customer
        return Response({
            "user": UserSerializer(request.user).data,
            "customer": {
                "id": customer.id,
                "name": customer.name,
                "phone": customer.phone,
                "preferred_language": customer.preferred_language,
                "vip": customer.vip,
                "points": customer.points,
            },
            "account": {
                "phone": account.phone,
            },
        })

    def put(self, request):
        account = getattr(request.user, "customer_account", None)
        if not account:
            return Response({"detail": "Unauthorized"}, status=401)
        customer = account.customer
        serializer = ProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        full_name = (data.get("full_name") or "").strip()
        email = (data.get("email") or "").strip()
        phone = (data.get("phone") or "").strip()
        preferred_language = (data.get("preferred_language") or "").strip()

        with transaction.atomic():
            if full_name:
                customer.name = full_name
                request.user.first_name = full_name

            if phone and phone != account.phone:
                if CustomerAccount.objects.filter(phone=phone).exclude(pk=account.pk).exists():
                    return Response({"detail": "Phone already used by another account."}, status=400)
                account.phone = phone
                customer.phone = phone

            if preferred_language in ("en", "ar"):
                customer.preferred_language = preferred_language

            request.user.email = email
            request.user.save(update_fields=["first_name", "email"])
            customer.save(update_fields=["name", "phone", "preferred_language"])
            account.save(update_fields=["phone"])

        return self.get(request)

    def delete(self, request):
        account = getattr(request.user, "customer_account", None)
        user = request.user
        if not account:
            user.delete()
            return Response(status=204)

        customer = account.customer
        with transaction.atomic():
            # Remove customer-scoped data first, then account/user.
            SavedAddress.objects.filter(customer=customer).delete()
            DeviceToken.objects.filter(customer=customer).delete()
            MobileEvent.objects.filter(customer=customer).delete()
            MobileNotification.objects.filter(customer=customer).delete()
            Order.objects.filter(customer=customer).update(customer=None)
            account.delete()
            customer.delete()
            user.delete()
        return Response(status=204)


class OtpSendView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = OtpSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        code = f"{random.randint(0, 999999):06d}"
        otp = PhoneOTP.objects.create(
            phone=data["phone"].strip(),
            purpose=data["purpose"],
            code=code,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        payload = {"ok": True, "expires_in": 300}
        if settings.OTP_DEBUG_RETURN_CODE:
            payload["debug_code"] = otp.code
        return Response(payload)


class OtpVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = OtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        otp = PhoneOTP.objects.filter(
            phone=data["phone"].strip(), purpose=data["purpose"], is_used=False
        ).order_by("-created_at").first()

        if not otp or otp.is_expired or otp.code != data["code"]:
            return Response({"detail": "Invalid or expired code."}, status=400)

        otp.is_used = True
        otp.save(update_fields=["is_used"])

        if data["purpose"] == "reset":
            return Response({"ok": True})

        account = CustomerAccount.objects.filter(phone=data["phone"].strip()).select_related("user", "customer").first()
        if not account:
            customer, _ = Customer.objects.get_or_create(phone=data["phone"].strip(), defaults={"name": data["phone"].strip()})
            username_base = data["phone"].replace("+", "").replace(" ", "")
            username = username_base
            idx = 1
            while User.objects.filter(username=username).exists():
                idx += 1
                username = f"{username_base}{idx}"
            user = User.objects.create_user(username=username, password=User.objects.make_random_password(), first_name=customer.name or "Customer")
            account = CustomerAccount.objects.create(user=user, customer=customer, phone=data["phone"].strip())

        return Response({
            "user": UserSerializer(account.user).data,
            "tokens": _tokens_for_user(account.user),
        })


class LaundryListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = BranchSerializer

    def get_queryset(self):
        qs = Branch.objects.filter(active=True).order_by("name")
        if qs.exists():
            return qs
        # Fallback for deployments where branch records exist but `active` was not toggled yet.
        return Branch.objects.all().order_by("name")

    def list(self, request, *args, **kwargs):
        cache_key = "mobile_api_laundries_v1"
        cached = cache.get(cache_key)
        if cached is not None and not request.query_params.get("page"):
            return Response(cached)
        data = BranchSerializer(self.get_queryset(), many=True).data
        response_data = _paginate_list(list(data), request)
        if not request.query_params.get("page"):
            cache.set(cache_key, response_data, 60)
        return Response(response_data)


class LaundryCatalogView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        branch = Branch.objects.filter(pk=pk, active=True).first() or Branch.objects.filter(pk=pk).first()
        if not branch:
            return Response({"detail": "Laundry not found."}, status=404)
        cache_key = f"mobile_api_catalog_{branch.id}"
        cached = cache.get(cache_key)
        if cached is None or request.query_params.get("page"):
            qs = BranchItemServicePrice.objects.filter(branch=branch).select_related("item", "service").order_by("service__sort_order", "item__sort_order", "item__name")
            if qs.exists():
                cached = CatalogRowSerializer(qs, many=True).data
            else:
                # Fallback: some deployments keep pricing in ItemServicePrice only.
                # This keeps mobile catalog aligned with web catalog until branch pricing is synced.
                global_qs = ItemServicePrice.objects.select_related("item", "service").order_by(
                    "service__sort_order", "item__sort_order", "item__name"
                )
                is_ar = str(getattr(request, "LANGUAGE_CODE", "")).lower().startswith("ar")
                cached = []
                for row in global_qs:
                    item_name = row.item.name_ar if is_ar and row.item.name_ar else row.item.name
                    service_name = row.service.name_ar if is_ar and row.service.name_ar else row.service.name
                    cached.append(
                        {
                            "id": row.id,
                            "item_id": row.item_id,
                            "item_name": item_name,
                            "item_name_ar": row.item.name_ar,
                            "service_id": row.service_id,
                            "service_name": service_name,
                            "service_name_ar": row.service.name_ar,
                            "price": row.price,
                        }
                    )
            cache.set(cache_key, list(cached), 60)
        data = _paginate_list(list(cached), request)
        return Response(data)


class LaundryDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        branch = Branch.objects.filter(pk=pk, active=True).first() or Branch.objects.filter(pk=pk).first()
        if not branch:
            return Response({"detail": "Laundry not found."}, status=404)
        return Response(BranchSerializer(branch).data)


class AddressListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        customer = _customer_from_request(request)
        qs = SavedAddress.objects.filter(customer=customer)
        return Response(SavedAddressSerializer(qs, many=True).data)

    def post(self, request):
        customer = _customer_from_request(request)
        serializer = SavedAddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            if serializer.validated_data.get("is_default"):
                SavedAddress.objects.filter(customer=customer, is_default=True).update(is_default=False)
            instance = serializer.save(customer=customer)
        return Response(SavedAddressSerializer(instance).data, status=201)


class AddressDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, request, pk):
        customer = _customer_from_request(request)
        return SavedAddress.objects.filter(customer=customer, pk=pk).first()

    def put(self, request, pk):
        instance = self.get_object(request, pk)
        if not instance:
            return Response({"detail": "Address not found."}, status=404)
        serializer = SavedAddressSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            if serializer.validated_data.get("is_default"):
                SavedAddress.objects.filter(customer=instance.customer, is_default=True).exclude(pk=instance.pk).update(is_default=False)
            instance = serializer.save()
        return Response(SavedAddressSerializer(instance).data)

    def delete(self, request, pk):
        instance = self.get_object(request, pk)
        if not instance:
            return Response(status=204)
        instance.delete()
        return Response(status=204)


class DeviceTokenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        customer = _customer_from_request(request)
        if not customer:
            return Response({"detail": "Unauthorized"}, status=401)
        token = (request.data.get("token") or "").strip()
        platform = (request.data.get("platform") or "").strip()
        if not token:
            return Response({"detail": "Token required."}, status=400)
        DeviceToken.objects.get_or_create(customer=customer, token=token, defaults={"platform": platform})
        return Response({"ok": True})


class OrderListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        customer = _customer_from_request(request)
        if not customer:
            return Response({"detail": "Unauthorized"}, status=401)
        qs = Order.objects.filter(customer=customer).prefetch_related("items").order_by("-created_at")
        data = OrderSerializer(qs, many=True).data
        return Response(_paginate_list(list(data), request))

    def post(self, request):
        customer = _customer_from_request(request)
        if not customer:
            return Response({"detail": "Unauthorized"}, status=401)
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        branch_id = data.get("laundry_id") or data.get("laundry_shop_id")
        branch = Branch.objects.get(pk=branch_id)
        lines = data.get("items") or data.get("lines") or []
        urgent_flag = data.get("urgent")
        speed = (data.get("speed") or "").upper()

        try:
            totals = _compute_order_totals(
                branch=branch,
                lines=lines,
                urgent_flag=urgent_flag,
                speed=speed,
                promo_discount=data.get("promo_discount"),
                points_used=data.get("points_used"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        subtotal = totals["subtotal"]
        urgent_fee = totals["urgent_fee"]
        promo_discount = totals["promo_discount"]
        points_used = totals["points_used"]
        tax = totals["tax"]
        total = totals["total"]
        priced_lines = totals["priced_lines"]
        urgent_flag = totals["urgent_flag"]

        address = None
        if data.get("address_id"):
            address = SavedAddress.objects.filter(customer=customer, pk=data["address_id"]).first()
        fulfillment_mode = (data.get("fulfillment_mode") or "DELIVERY").upper()
        delivery_required = fulfillment_mode == "DELIVERY"
        initial_status = Order.Status.RECEIVED

        with transaction.atomic():
            order = Order.objects.create(
                branch=branch.code,
                order_no=_next_order_no(),
                status=initial_status,
                urgent=bool(urgent_flag),
                customer=customer,
                subtotal=subtotal,
                discount=Decimal("0"),
                tax=tax,
                total=total,
                paid=Decimal("0"),
                balance=total,
                delivery_required=delivery_required,
                delivery_status=Order.DeliveryStatus.PENDING,
                delivery_address=(f"{address.address_line_1}, {address.area}, {address.city}" if address else ""),
                delivery_phone=customer.phone,
                delivery_slot=data.get("pickup_time_slot") or data.get("delivery_slot", ""),
                delivery_fee=Decimal("0"),
                notes=data.get("notes", ""),
            )
            MobileOrderMeta.objects.create(
                order=order,
                payment_method=data.get("payment_method", ""),
                transfer_reference=data.get("transfer_reference", ""),
                receipt_name=data.get("receipt_name", ""),
                promo_code=data.get("promo_code", ""),
                promo_discount=promo_discount,
                points_used=points_used,
                customer_notes=data.get("customer_notes", ""),
                pickup_time_slot=data.get("pickup_time_slot", ""),
                fulfillment_mode=fulfillment_mode,
                speed=speed or ("URGENT" if urgent_flag else "NORMAL"),
            )
            for price_row, qty, line_total in priced_lines:
                OrderItem.objects.create(
                    order=order,
                    item_name=price_row.item.name,
                    service_name=price_row.service.name,
                    qty=qty,
                    price=price_row.price,
                    line_total=line_total,
                )
            OrderStatusLog.objects.create(order=order, from_status="", to_status=initial_status, note="Order placed")
            payment_method = (data.get("payment_method") or "").upper()
            if payment_method in ["BANK", "BANK_TRANSFER"]:
                Payment.objects.create(order=order, method=Payment.Method.BANK, amount=Decimal("0"), note="Awaiting transfer")
            elif payment_method in ["CARD", "APPLE_PAY", "GOOGLE_PAY"]:
                note = f"{payment_method} pending"
                Payment.objects.create(order=order, method=Payment.Method.CARD, amount=Decimal("0"), note=note)
            if points_used > 0 and customer.points:
                customer.points = max(0, int(customer.points) - points_used)
                customer.save(update_fields=["points"])
            _notify_customer(
                customer=customer,
                order=order,
                title="Order placed",
                message=f"Your order #{order.order_no} has been placed successfully.",
                event_code="order_placed",
            )

        return Response(OrderSerializer(order).data, status=201)


class OrderDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        customer = _customer_from_request(request)
        order = Order.objects.filter(pk=pk, customer=customer).prefetch_related("items").first()
        if not order:
            return Response({"detail": "Order not found."}, status=404)
        return Response(OrderSerializer(order).data)


class OrderCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        customer = _customer_from_request(request)
        order = Order.objects.filter(pk=pk, customer=customer).first()
        if not order:
            return Response({"detail": "Order not found."}, status=404)
        if order.status in [Order.Status.DELIVERED, Order.Status.CANCELLED]:
            return Response({"detail": "Order cannot be cancelled."}, status=400)
        previous = order.status
        order.status = Order.Status.CANCELLED
        order.delivery_status = Order.DeliveryStatus.CANCELLED
        order.save(update_fields=["status", "delivery_status", "updated_at"])
        OrderStatusLog.objects.create(order=order, from_status=previous, to_status=Order.Status.CANCELLED, note="Cancelled by customer")
        _notify_customer(
            customer=customer,
            order=order,
            title="Order cancelled",
            message=f"Your order #{order.order_no} was cancelled.",
            event_code="order_cancelled",
        )
        return Response({"ok": True})


class OrderPricePreviewView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        branch_id = data.get("laundry_id") or data.get("laundry_shop_id")
        branch = Branch.objects.get(pk=branch_id)
        lines = data.get("items") or data.get("lines") or []
        urgent_flag = data.get("urgent")
        speed = (data.get("speed") or "").upper()
        try:
            totals = _compute_order_totals(
                branch=branch,
                lines=lines,
                urgent_flag=urgent_flag,
                speed=speed,
                promo_discount=data.get("promo_discount"),
                points_used=data.get("points_used"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response({
            "subtotal": totals["subtotal"],
            "urgent_fee": totals["urgent_fee"],
            "promo_discount": totals["promo_discount"],
            "points_used": totals["points_used"],
            "points_value": totals["points_value"],
            "tax": totals["tax"],
            "total": totals["total"],
        })


class OrderTrackingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        customer = _customer_from_request(request)
        order = Order.objects.filter(pk=pk, customer=customer).first()
        if not order:
            return Response({"detail": "Order not found."}, status=404)
        logs = order.status_logs.all().order_by("created_at")
        return Response({
            "order_no": order.order_no,
            "status": order.status,
            "delivery_status": order.delivery_status,
            "timeline": OrderTrackingLogSerializer(logs, many=True).data,
            "eta": order.estimated_ready_at.isoformat() if order.estimated_ready_at else "",
        })


class BankTransferProofView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        customer = _customer_from_request(request)
        order = Order.objects.filter(pk=pk, customer=customer).first()
        if not order:
            return Response({"detail": "Order not found."}, status=404)
        meta = getattr(order, "mobile_meta", None)
        if not meta:
            meta = MobileOrderMeta.objects.create(order=order)
        meta.transfer_reference = (request.data.get("transfer_reference") or "").strip()
        meta.receipt_name = (request.data.get("receipt_name") or "").strip()
        meta.payment_method = "BANK"
        meta.save(update_fields=["transfer_reference", "receipt_name", "payment_method"])
        return Response({"ok": True})


class AnalyticsEventView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AnalyticsEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = _customer_from_request(request)
        if not customer:
            return Response({"detail": "Unauthorized"}, status=401)
        MobileEvent.objects.create(customer=customer, **serializer.validated_data)
        return Response({"ok": True})


class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        customer = _customer_from_request(request)
        if not customer:
            return Response({"detail": "Unauthorized"}, status=401)
        qs = MobileNotification.objects.filter(customer=customer).order_by("-created_at")
        data = MobileNotificationSerializer(qs, many=True).data
        unread = qs.filter(is_read=False).count()
        paged = _paginate_list(list(data), request)
        if isinstance(paged, dict):
            return Response({
                "unread_count": unread,
                "count": paged.get("count", len(data)),
                "page": paged.get("page", 1),
                "page_size": paged.get("page_size", len(paged.get("results", []))),
                "results": paged.get("results", []),
            })
        return Response({"unread_count": unread, "count": len(data), "results": paged})


class NotificationReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        customer = _customer_from_request(request)
        if not customer:
            return Response({"detail": "Unauthorized"}, status=401)
        notification_id = request.data.get("id")
        mark_all = request.data.get("all") in (True, "1", "true", "True")
        qs = MobileNotification.objects.filter(customer=customer, is_read=False)
        if mark_all:
            qs.update(is_read=True, read_at=timezone.now())
            return Response({"ok": True})
        if notification_id:
            qs.filter(pk=notification_id).update(is_read=True, read_at=timezone.now())
            return Response({"ok": True})
        return Response({"detail": "Provide id or all=true."}, status=400)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def payment_methods_view(request):
    bank_settings = _get_bank_settings_safe()
    bank_enabled = bank_settings.enabled if bank_settings else settings.BANK_TRANSFER_ENABLED
    methods = [
        {"code": "COD", "label": "Cash on delivery"},
    ]
    if bank_enabled:
        methods.append({"code": "BANK", "label": "Bank transfer"})
    if settings.CARD_PAY_ENABLED:
        methods.append({"code": "CARD", "label": "Card payment"})
    if settings.APPLE_PAY_ENABLED:
        methods.append({"code": "APPLE_PAY", "label": "Apple Pay"})
    if settings.GOOGLE_PAY_ENABLED:
        methods.append({"code": "GOOGLE_PAY", "label": "Google Pay"})
    return Response(methods)
