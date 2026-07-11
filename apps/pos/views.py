import json
import logging
from decimal import Decimal, InvalidOperation
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import IntegrityError
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.utils import translation
from django.utils import timezone

from apps.orders.models import Customer, Order, OrderItem
from apps.payments.models import Payment
from apps.management.models import Branch
from apps.management.utils import log_audit
from apps.accounts.utils import get_effective_branch
from apps.settings_app.utils import send_whatsapp_message_auto
from apps.catalog.models import Item, Service

logger = logging.getLogger(__name__)

def _safe_decimal(value, default="0"):
    try:
        d = Decimal(str(value if value is not None else default))
        if d.is_nan() or d.is_infinite():
            return Decimal(str(default))
        return d
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(str(default))


@login_required
def new_order(request):
    return render(request, "pos/new_order.html", {
        "default_vip_discount": getattr(settings, "DEFAULT_VIP_DISCOUNT_PERCENT", 0),
        "redeem_value_per_point": getattr(settings, "LOYALTY_REDEEM_VALUE_PER_POINT", 0),
    })


def _next_order_no() -> str:
    last = Order.objects.order_by("-id").first()
    if not last:
        return "1001"
    try:
        return str(int(last.order_no) + 1)
    except Exception:
        return str(last.id + 1001)


@require_POST
@login_required
def _create_order_api_impl(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    branch = get_effective_branch(request) or request.session.get("active_branch", "muscat")
    branch_obj = Branch.objects.filter(code=branch).first()
    if not branch_obj:
        return JsonResponse({"ok": False, "error": "Invalid branch"}, status=400)

    cust = data.get("customer") or {}
    cust_name = (cust.get("name") or "").strip()
    cust_phone = (cust.get("phone") or "").strip()
    cust_vip = bool(cust.get("vip", False))
    apply_vip_discount = bool(data.get("apply_vip_discount", False))

    items = data.get("items") or []
    if not items:
        return JsonResponse({"ok": False, "error": "No items"}, status=400)

    discount = _safe_decimal(data.get("discount", "0"), "0")
    tax = _safe_decimal(data.get("tax", "0"), "0")
    paid = _safe_decimal(data.get("paid", "0"), "0")
    try:
        redeem_points = int(data.get("redeem_points", 0) or 0)
    except Exception:
        redeem_points = 0
    pay_method = (data.get("pay_method") or "CASH").upper()
    pay_note = (data.get("pay_note") or "").strip()
    notes = (data.get("notes") or "").strip()

    customer = None
    if cust_name or cust_phone:
        customer, _ = Customer.objects.get_or_create(
            phone=cust_phone,
            defaults={"name": cust_name, "vip": cust_vip},
        )
        if cust_name:
            customer.name = cust_name
        customer.vip = cust_vip
        if customer.vip and customer.vip_discount_percent == 0:
            customer.vip_discount_percent = getattr(settings, "DEFAULT_VIP_DISCOUNT_PERCENT", 0)
        customer.save()

    subtotal = Decimal("0")
    total_qty = 0
    for it in items:
        try:
            qty = int(it.get("qty", 1) or 1)
        except Exception:
            qty = 1
        if qty <= 0:
            return JsonResponse({"ok": False, "error": "Invalid quantity"}, status=400)
        try:
            price = Decimal(str(it.get("price", "0") or "0"))
        except Exception:
            price = Decimal("0")
        if price < 0:
            return JsonResponse({"ok": False, "error": "Invalid price"}, status=400)
        item_name = (it.get("item") or "").strip()
        service_name = (it.get("service") or "").strip()
        if not item_name or not service_name:
            return JsonResponse({"ok": False, "error": "Missing item or service"}, status=400)
        subtotal += Decimal(qty) * price
        total_qty += qty

    if customer and customer.vip and apply_vip_discount and discount == 0:
        discount = (subtotal * Decimal(str(customer.vip_discount_percent or 0)) / Decimal("100"))

    if (discount > 0 or apply_vip_discount) and not request.user.has_perm("orders.can_discount"):
        return JsonResponse({"ok": False, "error": "Discount not permitted"}, status=403)

    if discount > 0 and not branch_obj.allow_discounts:
        return JsonResponse({"ok": False, "error": "Discounts disabled for this branch"}, status=400)

    if discount > 0:
        max_percent = Decimal(str(branch_obj.max_discount_percent or 0))
        max_value = (subtotal * max_percent) / Decimal("100")
        if discount > max_value:
            return JsonResponse({"ok": False, "error": "Discount exceeds branch limit"}, status=400)

    redeem_value = Decimal("0")
    if customer and redeem_points > 0:
        available = int(customer.points or 0)
        redeem_points = min(redeem_points, available)
        redeem_rate = Decimal(str(getattr(settings, "LOYALTY_REDEEM_VALUE_PER_POINT", 0)))
        redeem_value = Decimal(redeem_points) * redeem_rate
        if redeem_value > subtotal:
            redeem_value = subtotal

    total = max(Decimal("0"), subtotal - discount - redeem_value + tax)
    balance = total - paid
    if balance < 0:
        balance = Decimal("0")

    order_no = _next_order_no()
    ready_hours = getattr(settings, "DEFAULT_READY_HOURS", 24)
    per_item_minutes = getattr(settings, "READY_MINUTES_PER_ITEM", 10)

    service_names = list({(it.get("service") or "").strip() for it in items if it.get("service")})
    service_avgs = {}
    if service_names:
        recent_items = (
            OrderItem.objects.select_related("order")
            .filter(order__branch=branch, order__delivered_at__isnull=False, service_name__in=service_names)
            .order_by("-order__delivered_at")[:400]
        )
        for it in recent_items:
            if not it.order or not it.order.created_at or not it.order.delivered_at:
                continue
            hours = (it.order.delivered_at - it.order.created_at).total_seconds() / 3600.0
            if hours <= 0:
                continue
            service_avgs.setdefault(it.service_name, []).append(hours)

    weighted_hours = []
    for it in items:
        svc = (it.get("service") or "").strip()
        qty = int(it.get("qty", 1) or 1)
        hours_list = service_avgs.get(svc) or []
        if hours_list:
            avg_h = sum(hours_list) / len(hours_list)
            weighted_hours.extend([avg_h] * qty)

    if weighted_hours:
        ready_hours = sum(weighted_hours) / len(weighted_hours)
    else:
        avg_hours = (
            Order.objects.filter(branch=branch, delivered_at__isnull=False)
            .values_list("delivered_at", "created_at")[:200]
        )
        hist_hours = []
        for delivered_at, created_at in avg_hours:
            if delivered_at and created_at:
                hist_hours.append((delivered_at - created_at).total_seconds() / 3600.0)
        if hist_hours:
            ready_hours = sum(hist_hours) / len(hist_hours)

    eta = timezone.now() + timedelta(hours=ready_hours, minutes=(per_item_minutes * total_qty))

    order = None
    for _ in range(3):
        try:
            order_no = _next_order_no()
            order = Order.objects.create(
                branch=branch,
                order_no=order_no,
                status=Order.Status.RECEIVED,
                delivery_required=False,
                customer=customer,
                cashier=request.user,
                subtotal=subtotal,
                discount=discount,
                tax=tax,
                delivery_fee=Decimal("0"),
                total=total,
                paid=paid,
                balance=balance,
                points_redeemed=redeem_points,
                points_redeemed_value=redeem_value,
                notes=notes,
                estimated_ready_at=eta,
            )
            break
        except IntegrityError:
            order = None
            continue
    if not order:
        return JsonResponse({"ok": False, "error": "Could not generate unique order number"}, status=500)
    log_audit(
        action="order_create",
        entity_type="order",
        entity_id=order.order_no,
        message=f"total {order.total} discount {discount} redeem {redeem_value}",
        user=request.user,
        branch_code=order.branch,
    )

    for it in items:
        item_name = (it.get("item") or "").strip()
        service_name = (it.get("service") or "").strip()
        qty = int(it.get("qty", 1) or 1)
        price = Decimal(str(it.get("price", "0") or "0"))
        line_total = Decimal(qty) * price

        OrderItem.objects.create(
            order=order,
            item_name=item_name,
            service_name=service_name,
            qty=qty,
            price=price,
            line_total=line_total,
        )

    if customer and redeem_points > 0:
        customer.points = max(0, int(customer.points or 0) - redeem_points)
        customer.save(update_fields=["points"])

    if paid > 0:
        Payment.objects.create(
            order=order,
            method=pay_method if pay_method in Payment.Method.values else Payment.Method.CASH,
            amount=paid,
            note=pay_note,
            created_by=request.user,
        )
        order.refresh_payment_totals()
    elif order.balance == 0:
        order.award_loyalty_points()

    if paid > 0:
        log_audit(
            action="payment_add",
            entity_type="order",
            entity_id=order.order_no,
            message=f"{pay_method} {paid}",
            user=request.user,
            branch_code=order.branch,
        )

    if customer:
        branch_name = branch_obj.name if branch_obj else order.branch
        lang = customer.preferred_language if customer.preferred_language in ("en", "ar") else "en"
        try:
            send_whatsapp_message_auto(order, customer, branch_name, "receipt", lang, request.user)
        except Exception:
            # Notifications are optional for POS sync; do not fail order creation on messaging errors.
            logger.exception("POS order %s created but WhatsApp receipt sending failed", order.order_no)

    return JsonResponse({"ok": True, "order_no": order.order_no})


@require_POST
@login_required
def create_order_api(request):
    try:
        return _create_order_api_impl(request)
    except Exception as exc:
        logger.exception("POS create_order_api failed")
        return JsonResponse({"ok": False, "error": f"Server error: {exc.__class__.__name__}: {exc}"}, status=500)


@login_required
def receipt_80mm(request):
    """
    - /pos/receipt/80mm/?order=1001    -> receipt for DB order + QR
    """
    order_no = (request.GET.get("order") or "").strip()

    def _build_qr_data_uri(payload: str):
        try:
            import base64
            from io import BytesIO
            import qrcode

            # PNG first (best printer compatibility)
            try:
                img = qrcode.make(payload)
                bio = BytesIO()
                img.save(bio, format="PNG")
                return "data:image/png;base64," + base64.b64encode(bio.getvalue()).decode("utf-8")
            except Exception:
                # Fallback to SVG if PNG backend (Pillow) is unavailable.
                from qrcode.image.svg import SvgPathImage

                qr = qrcode.QRCode(border=2, box_size=6)
                qr.add_data(payload)
                qr.make(fit=True)
                img = qr.make_image(image_factory=SvgPathImage)
                bio = BytesIO()
                img.save(bio)
                return "data:image/svg+xml;base64," + base64.b64encode(bio.getvalue()).decode("utf-8")
        except Exception:
            return None

    def _estimated_pickup_text(order_obj):
        if getattr(order_obj, "estimated_ready_at", None):
            dt = timezone.localtime(order_obj.estimated_ready_at)
            return dt.strftime("%b %d, %Y %I:%M %p")
        pickup_date = getattr(order_obj, "pickup_date", None)
        pickup_slot = (getattr(order_obj, "pickup_slot", "") or "").strip()
        if pickup_date and pickup_slot:
            return f"{pickup_date} {pickup_slot}"
        if pickup_date:
            return str(pickup_date)
        return "-"

    def _translated_receipt_items(order_obj, is_ar: bool):
        if not order_obj:
            return []
        rows = list(order_obj.items.all())
        if not is_ar:
            return rows

        item_map = {}
        service_map = {}
        try:
            item_map = {
                (it.name or "").strip().lower(): (it.name_ar or "").strip()
                for it in Item.objects.all().only("name", "name_ar")
                if (it.name or "").strip()
            }
            service_map = {
                (sv.name or "").strip().lower(): (sv.name_ar or "").strip()
                for sv in Service.objects.all().only("name", "name_ar")
                if (sv.name or "").strip()
            }
        except Exception:
            item_map = {}
            service_map = {}

        translated = []
        for row in rows:
            item_key = (row.item_name or "").strip().lower()
            service_key = (row.service_name or "").strip().lower()
            row.item_display = item_map.get(item_key) or row.item_name
            row.service_display = service_map.get(service_key) or row.service_name
            translated.append(row)
        return translated

    if order_no:
        order = get_object_or_404(
            Order.objects.select_related("customer", "cashier").prefetch_related("items"),
            order_no=order_no
        )

        token = order.ensure_pickup_token()
        payload = f"{settings.SITE_BASE_URL}/p/{token}/"
        qr_data_uri = _build_qr_data_uri(payload)

        lang = translation.get_language() or "en"
        is_ar = str(lang).lower().startswith("ar")
        branch_obj = Branch.objects.filter(code=order.branch).first()
        pickup_brand = (branch_obj.name if branch_obj and branch_obj.name else "Laundrex").strip()
        receipt_logo_url = branch_obj.receipt_logo.url if branch_obj and branch_obj.receipt_logo else ""
        receipt_address = ""
        if branch_obj:
            receipt_address = (
                branch_obj.address_ar.strip()
                if is_ar and (branch_obj.address_ar or "").strip()
                else (branch_obj.address or "").strip()
            )
        receipt_footer = ""
        if branch_obj:
            receipt_footer = (
                branch_obj.receipt_footer_ar.strip()
                if is_ar and (branch_obj.receipt_footer_ar or "").strip()
                else (branch_obj.receipt_footer or "").strip()
            )
        copies = branch_obj.receipt_copies if branch_obj and branch_obj.receipt_copies else 1
        template = branch_obj.receipt_template if branch_obj and branch_obj.receipt_template else "80mm"

        receipt_items = _translated_receipt_items(order, is_ar)
        ctx = {
            "db_order": order,
            "receipt_items": receipt_items,
            "branch": order.branch,
            "branch_name": branch_obj.name if branch_obj else order.branch,
            "date": order.created_at.strftime("%b %d, %Y %I:%M %p"),
            "cashier": order.cashier.username if order.cashier else "-",
            "order_no": order.order_no,
            "order_status_label": order.get_status_display(),
            "order_status_label_title": "الحالة" if is_ar else "Status",
            "estimated_pickup_label_title": "الاستلام المتوقع" if is_ar else "Est. Pickup",
            "estimated_pickup": _estimated_pickup_text(order),
            "customer": (order.customer.name if order.customer else "Walk-in"),
            "phone": (order.customer.phone if order.customer else ""),
            "qr_data_uri": qr_data_uri,
            "pickup_code": f"{pickup_brand}:{order.order_no}",
            "pickup_link": payload,
            "receipt_logo_url": receipt_logo_url,
            "receipt_header": branch_obj.receipt_header if branch_obj else "",
            "receipt_footer": receipt_footer,
            "receipt_address": receipt_address,
            "cr_number": branch_obj.cr_number if branch_obj else "",
            "vat_number": branch_obj.vat_number if branch_obj else "",
            "receipt_phone": branch_obj.phone if branch_obj else "",
            "printer_name": branch_obj.printer_name if branch_obj else "",
            "copies": copies,
            "copies_range": range(copies),
            "lang": lang,
        }
        if template == "a4":
            return render(request, "pos/receipt_a4.html", ctx)
        return render(request, "pos/receipt_80mm.html", ctx)

    return HttpResponseBadRequest("A valid order is required to generate a receipt.")
