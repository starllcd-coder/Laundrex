import json
from decimal import Decimal
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import Order, OrderStatusLog, Customer
from .sync_utils import apply_customer_payload, apply_order_payload, parse_dt, serialize_customer, serialize_order
from apps.payments.models import Payment
from apps.management.utils import log_audit
from apps.accounts.utils import scope_queryset_to_branch
from apps.management.models import Branch
from apps.settings_app.models import WhatsAppMessageLog, WhatsAppTemplate
from apps.settings_app.utils import send_whatsapp_message, send_whatsapp_message_auto, get_sync_settings
from apps.catalog.models import Service
from .central_connector import verify_central_request


STATUS_FLOW = [
    "RECEIVED",
    "ACCEPTED",
    "PICKUP_ASSIGNED",
    "WASHING",
    "IRONING",
    "READY",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
]
WALKIN_STATUS_FLOW = [
    "RECEIVED",
    "ACCEPTED",
    "WASHING",
    "IRONING",
    "READY",
    "DELIVERED",
]
DELAY_HOURS = 48
DEFAULT_SLOT_TEMPLATES = ["Morning", "Afternoon", "Evening"]


def _status_label(code: str) -> str:
    if code in Order.Status.values:
        return str(Order.Status(code).label)
    return code


def _delivery_status_label(code: str) -> str:
    if code in Order.DeliveryStatus.values:
        return str(Order.DeliveryStatus(code).label)
    return code


def _payment_method_label(code: str) -> str:
    if code in Payment.Method.values:
        return str(Payment.Method(code).label)
    return code


def next_status(current: str) -> str:
    if current == "CANCELLED":
        return "CANCELLED"
    if current not in STATUS_FLOW:
        return "RECEIVED"
    idx = STATUS_FLOW.index(current)
    return STATUS_FLOW[min(idx + 1, len(STATUS_FLOW) - 1)]


def next_status_for_order(order: Order) -> str:
    flow = STATUS_FLOW if order.delivery_required else WALKIN_STATUS_FLOW
    current = order.status
    if current == "CANCELLED":
        return "CANCELLED"
    if current not in flow:
        return flow[0]
    idx = flow.index(current)
    return flow[min(idx + 1, len(flow) - 1)]


def _is_delayed(order: Order, now=None) -> bool:
    if order.status in (Order.Status.DELIVERED, Order.Status.CANCELLED):
        return False
    if not order.created_at:
        return False
    now = now or timezone.now()
    return order.created_at <= (now - timedelta(hours=DELAY_HOURS))


def _parse_slot_templates(raw: str):
    slots = []
    if raw:
        parts = []
        for line in raw.splitlines():
            parts.extend([p.strip() for p in line.split(",")])
        slots = [p for p in parts if p]
    return slots or DEFAULT_SLOT_TEMPLATES


def _get_branch_for_slots(request, branch_code: str = ""):
    code = (branch_code or "").strip()
    if not code:
        code = request.session.get("active_branch", "")
    if not code:
        return None
    return Branch.objects.filter(code=code).first()


def _log_status_change(order: Order, to_status: str, user, note: str = ""):
    if order.status == to_status:
        return
    from_status = order.status
    order.status = to_status
    order.save(update_fields=["status", "updated_at"])
    OrderStatusLog.objects.create(
        order=order,
        from_status=from_status,
        to_status=to_status,
        note=note,
        created_by=user,
    )
    from_label = _status_label(from_status)
    to_label = _status_label(to_status)
    log_audit(
        action="status_change",
        entity_type="order",
        entity_id=order.order_no,
        message=f"{from_label} -> {to_label}",
        user=user,
        branch_code=order.branch,
    )
    _auto_send_whatsapp_for_status(order, to_status, user)
    _create_mobile_status_notification(order, to_status)


def _auto_send_whatsapp_for_status(order: Order, to_status: str, user=None):
    if not order.customer:
        return

    template_key = None
    if to_status == Order.Status.READY:
        template_key = "ready_pickup"
    elif to_status == Order.Status.DELIVERED:
        template_key = "delivered"

    if not template_key:
        return

    branch_name = order.branch
    branch_obj = Branch.objects.filter(code=order.branch).first()
    if branch_obj:
        branch_name = branch_obj.name

    lang = order.customer.preferred_language if order.customer.preferred_language in ("en", "ar") else "en"
    send_whatsapp_message_auto(order, order.customer, branch_name, template_key, lang, user)


def _create_mobile_status_notification(order: Order, to_status: str):
    if not order.customer:
        return
    try:
        from apps.mobile_api.models import MobileNotification
    except Exception:
        return
    MobileNotification.objects.create(
        customer=order.customer,
        order=order,
        title=_("Order update"),
        message=_("Order #%(order)s is now %(status)s.") % {
            "order": order.order_no,
            "status": _status_label(to_status),
        },
        event_code="status_change",
    )


def _recalculate_order_total(order: Order):
    total = order.subtotal - order.discount - order.points_redeemed_value + order.tax + order.delivery_fee
    if total < 0:
        total = 0
    order.total = total
    due = total - order.paid
    order.balance = due if due > 0 else 0


@login_required
def _apply_order_filters(request, qs):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    branch = (request.GET.get("branch") or "").strip()
    date = (request.GET.get("date") or "").strip()
    unpaid = (request.GET.get("unpaid") or "").strip() == "1"
    urgent = (request.GET.get("urgent") or "").strip() == "1"
    mode = (request.GET.get("mode") or "").strip().lower()
    source = (request.GET.get("source") or "").strip().lower()

    if q:
        qs = qs.filter(
            Q(order_no__icontains=q)
            | Q(customer__name__icontains=q)
            | Q(customer__phone__icontains=q)
        )

    if status:
        qs = qs.filter(status=status)

    if branch:
        qs = qs.filter(branch__icontains=branch)

    if date:
        qs = qs.filter(created_at__date=date)

    if unpaid:
        qs = qs.filter(balance__gt=0)

    if urgent:
        qs = qs.filter(urgent=True)
    if mode == "walkin":
        qs = qs.filter(delivery_required=False)
    elif mode == "delivery":
        qs = qs.filter(delivery_required=True)
    if source == "mobile":
        qs = qs.filter(mobile_meta__isnull=False)
    elif source in ("frontdesk", "front_desk"):
        qs = qs.filter(mobile_meta__isnull=True)

    return qs, {
        "q": q,
        "status": status,
        "branch": branch,
        "date": date,
        "unpaid": unpaid,
        "urgent": urgent,
        "mode": mode,
        "source": source,
    }


@login_required
def order_list(request):
    qs = Order.objects.select_related("customer", "mobile_meta").order_by("-created_at")
    qs = scope_queryset_to_branch(request, qs)
    qs, filters = _apply_order_filters(request, qs)
    orders = list(qs[:300])
    now = timezone.now()
    for o in orders:
        o.next_status = next_status_for_order(o)
        o.is_delayed = _is_delayed(o, now)

    return render(
        request,
        "orders/list.html",
        {
            "orders": orders,
            **filters,
        },
    )

def _live_debug_key(user_id: int) -> str:
    return f"orders_live_debug_{user_id}"


def _push_live_debug(user_id: int, event: str, payload: dict | None = None):
    key = _live_debug_key(user_id)
    rows = cache.get(key) or []
    rows.append(
        {
            "ts": timezone.now().isoformat(),
            "event": event,
            "payload": payload or {},
        }
    )
    cache.set(key, rows[-120:], timeout=60 * 60 * 24)


@login_required
def live_order_check(request):
    qs = scope_queryset_to_branch(request, Order.objects.all())
    # This endpoint powers the "mobile order" toast, so only include
    # orders created via mobile API metadata.
    mobile_qs = qs.filter(mobile_meta__isnull=False).distinct()
    latest = mobile_qs.order_by("-created_at").only("created_at", "order_no").first()

    since_raw = (request.GET.get("since") or "").strip()
    since_dt = parse_datetime(since_raw) if since_raw else None
    if since_dt and timezone.is_naive(since_dt):
        since_dt = timezone.make_aware(since_dt, timezone.get_current_timezone())

    new_count = 0
    newest_order_no = latest.order_no if latest else ""
    newest_created_at = latest.created_at.isoformat() if latest and latest.created_at else ""

    if since_dt:
        new_qs = mobile_qs.filter(created_at__gt=since_dt)
        new_count = new_qs.count()
        newest = new_qs.order_by("-created_at").only("order_no").first()
        if newest:
            newest_order_no = newest.order_no

    _push_live_debug(
        request.user.id,
        "poll_ok",
        {
            "since": since_raw,
            "new_count": new_count,
            "latest_order_no": newest_order_no,
            "latest_created_at": newest_created_at,
        },
    )

    return JsonResponse(
        {
            "ok": True,
            "latest_created_at": newest_created_at,
            "latest_order_no": newest_order_no,
            "new_count": new_count,
            "source": "mobile",
        }
    )

@csrf_exempt
@login_required
@require_http_methods(["GET", "POST"])
def live_order_debug(request):
    key = _live_debug_key(request.user.id)

    if request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8") or "{}")
        except Exception:
            body = {}
        event = (body.get("event") or "client_event").strip()[:60]
        payload = body.get("payload") or {}
        _push_live_debug(request.user.id, event, payload if isinstance(payload, dict) else {"value": str(payload)})
        return JsonResponse({"ok": True})

    if request.GET.get("clear") in ("1", "true", "True"):
        cache.delete(key)
        return JsonResponse({"ok": True, "cleared": True, "events": []})

    return JsonResponse({"ok": True, "events": cache.get(key) or []})

@login_required
def order_detail(request, order_no: str):
    order = get_object_or_404(
        scope_queryset_to_branch(request, Order.objects.select_related("customer", "cashier").prefetch_related("items", "payments", "status_logs")),
        order_no=order_no,
    )
    items = order.items.all().order_by("id")
    status_logs = order.status_logs.all().order_by("-created_at")
    payments = order.payments.all().order_by("-created_at")

    wa_logs = WhatsAppMessageLog.objects.filter(order=order).order_by("-created_at")[:50]
    templates = WhatsAppTemplate.objects.filter(enabled=True).order_by("name")

    next_code = next_status_for_order(order)
    now = timezone.now()
    is_delayed = _is_delayed(order, now)
    last_status_log = status_logs.first()

    timeline = []
    if order.created_at:
        timeline.append({"time": order.created_at, "label": _("Order created")})
    for s in status_logs:
        timeline.append({
            "time": s.created_at,
            "label": _("%(from)s → %(to)s") % {"from": s.from_status_label, "to": s.to_status_label},
            "user": s.created_by.username if s.created_by else "-",
        })
    for p in payments:
        timeline.append({
            "time": p.created_at,
            "label": _("%(method)s payment %(amount)s") % {"method": p.get_method_display(), "amount": p.amount},
            "user": p.created_by.username if p.created_by else "-",
        })
    if order.delivered_at:
        timeline.append({"time": order.delivered_at, "label": _("Delivered")})
    timeline = sorted(timeline, key=lambda x: x.get("time") or now, reverse=True)
    return render(
        request,
        "orders/detail.html",
        {
            "order": order,
            "items": items,
            "next_status": next_code,
            "next_status_label": _status_label(next_code),
            "status_logs": status_logs,
            "payments": payments,
            "wa_logs": wa_logs,
            "wa_templates": templates,
            "is_delayed": is_delayed,
            "delay_hours": DELAY_HOURS,
            "timeline": timeline,
            "last_status_log": last_status_log,
        },
    )


@login_required
def order_advance_status(request, order_no: str):
    if request.method != "POST":
        return HttpResponseBadRequest(_("POST required"))

    if not request.user.has_perm("orders.can_change_status"):
        return HttpResponseBadRequest(_("Not allowed"))

    order = get_object_or_404(scope_queryset_to_branch(request, Order.objects), order_no=order_no)
    _log_status_change(order, next_status_for_order(order), request.user)
    return redirect("orders:detail", order_no=order.order_no)


@login_required
def order_set_status(request, order_no: str):
    if request.method != "POST":
        return HttpResponseBadRequest(_("POST required"))

    if not request.user.has_perm("orders.can_change_status"):
        return HttpResponseBadRequest(_("Not allowed"))

    order = get_object_or_404(scope_queryset_to_branch(request, Order.objects), order_no=order_no)
    target = (request.POST.get("status") or "").strip().upper()
    note = (request.POST.get("note") or "").strip()

    allowed = {code for code, _ in Order.Status.choices}
    if target not in allowed:
        return HttpResponseBadRequest(_("Invalid status"))
    if not order.delivery_required and target in {"PICKUP_ASSIGNED", "OUT_FOR_DELIVERY"}:
        return HttpResponseBadRequest(_("This status is only available for delivery orders"))

    _log_status_change(order, target, request.user, note=note)
    return redirect(request.POST.get("next") or "orders:list")


@login_required
def order_mark_collected(request, order_no: str):
    if request.method != "POST":
        return HttpResponseBadRequest(_("POST required"))
    if not request.user.has_perm("orders.can_change_status"):
        return HttpResponseBadRequest(_("Not allowed"))

    order = get_object_or_404(scope_queryset_to_branch(request, Order.objects), order_no=order_no)
    if order.delivery_required:
        return HttpResponseBadRequest(_("Use delivery workflow for delivery orders"))
    if order.status != Order.Status.READY:
        return HttpResponseBadRequest(_("Only READY orders can be marked collected"))

    _log_status_change(order, Order.Status.DELIVERED, request.user, note=_("Collected at front desk"))
    return redirect("orders:detail", order_no=order.order_no)


@login_required
def order_undo_last_status(request, order_no: str):
    if request.method != "POST":
        return HttpResponseBadRequest(_("POST required"))
    if not request.user.has_perm("orders.can_change_status"):
        return HttpResponseBadRequest(_("Not allowed"))

    order = get_object_or_404(scope_queryset_to_branch(request, Order.objects), order_no=order_no)
    last_log = OrderStatusLog.objects.filter(order=order).order_by("-created_at").first()
    if not last_log:
        return HttpResponseBadRequest(_("No status history to undo"))

    target = last_log.from_status or Order.Status.RECEIVED
    allowed = {code for code, _ in Order.Status.choices}
    if target not in allowed:
        return HttpResponseBadRequest(_("Invalid status"))

    if order.status != target:
        _log_status_change(order, target, request.user, note=_("Undo last status change"))

    return redirect("orders:detail", order_no=order.order_no)


@login_required
def order_cancel(request, order_no: str):
    if request.method != "POST":
        return HttpResponseBadRequest(_("POST required"))

    if not request.user.has_perm("orders.can_refund"):
        return HttpResponseBadRequest(_("Not allowed"))

    order = get_object_or_404(scope_queryset_to_branch(request, Order.objects), order_no=order_no)
    _log_status_change(order, "CANCELLED", request.user, note=_("Cancelled"))
    return redirect("orders:detail", order_no=order.order_no)


@login_required
def order_set_urgent(request, order_no: str):
    if request.method != "POST":
        return HttpResponseBadRequest(_("POST required"))
    if not request.user.has_perm("orders.can_change_status"):
        return HttpResponseBadRequest(_("Not allowed"))

    order = get_object_or_404(scope_queryset_to_branch(request, Order.objects), order_no=order_no)
    urgent = (request.POST.get("urgent") or "").strip() == "1"
    order.urgent = urgent
    order.save(update_fields=["urgent", "updated_at"])
    next_url = (request.POST.get("next") or "").strip()
    if next_url:
        return redirect(next_url)
    return redirect("orders:detail", order_no=order.order_no)


@login_required
def order_pickup_update(request, order_no: str):
    if request.method != "POST":
        return HttpResponseBadRequest(_("POST required"))
    if not request.user.has_perm("orders.can_change_status"):
        return HttpResponseBadRequest(_("Not allowed"))

    order = get_object_or_404(scope_queryset_to_branch(request, Order.objects), order_no=order_no)
    pickup_date = (request.POST.get("pickup_date") or "").strip()
    pickup_slot = (request.POST.get("pickup_slot") or "").strip()
    pickup_notes = (request.POST.get("pickup_notes") or "").strip()

    if pickup_date:
        try:
            order.pickup_date = timezone.datetime.fromisoformat(pickup_date).date()
        except Exception:
            order.pickup_date = None
    else:
        order.pickup_date = None

    order.pickup_slot = pickup_slot
    order.pickup_notes = pickup_notes
    order.save(update_fields=["pickup_date", "pickup_slot", "pickup_notes", "updated_at"])
    log_audit(
        action="pickup_update",
        entity_type="order",
        entity_id=order.order_no,
        message=f"pickup {pickup_date} {pickup_slot}",
        user=request.user,
        branch_code=order.branch,
    )
    return redirect("orders:detail", order_no=order.order_no)


@login_required
def pickup_counter(request):
    order = None
    error = None
    info = None
    code = ""

    if request.method == "POST":
        if "lookup_code" in request.POST:
            code = (request.POST.get("lookup_code") or "").strip()
            order_no = code
            if code.upper().startswith("LAUNDREX:"):
                order_no = code.split(":", 1)[1].strip()
            elif "/p/" in code:
                token = code.split("/p/", 1)[1].strip().strip("/")
                order = scope_queryset_to_branch(
                    request,
                    Order.objects.select_related("customer", "cashier").prefetch_related("items")
                ).filter(pickup_token=token).first()
                if not order:
                    error = _("Order not found")
                order_no = ""

            if not order_no and not order:
                error = _("Please enter a valid order number")
            elif order_no:
                order = scope_queryset_to_branch(
                    request,
                    Order.objects.select_related("customer", "cashier").prefetch_related("items")
                ).filter(order_no=order_no).first()
                if not order:
                    error = _("Order #%(order_no)s not found") % {"order_no": order_no}

        if "action" in request.POST:
            order_no = (request.POST.get("order_no") or "").strip()
            action = (request.POST.get("action") or "").strip()
            order = get_object_or_404(
                scope_queryset_to_branch(request, Order.objects.select_related("customer", "cashier")),
                order_no=order_no,
            )

            if action == "mark_ready":
                if not request.user.has_perm("orders.can_change_status"):
                    return HttpResponseBadRequest(_("Not allowed"))
                _log_status_change(order, "READY", request.user)
                info = _("Order marked Ready")
            elif action == "mark_delivered":
                if not request.user.has_perm("orders.can_change_status"):
                    return HttpResponseBadRequest(_("Not allowed"))
                _log_status_change(order, "DELIVERED", request.user)
                info = _("Order marked Delivered")
            elif action == "collect_payment":
                if not request.user.has_perm("orders.can_discount"):
                    return HttpResponseBadRequest(_("Not allowed"))
                amount = Decimal(str(request.POST.get("amount") or "0"))
                method = (request.POST.get("method") or "CASH").upper()
                reference = (request.POST.get("reference") or "").strip()
                note = (request.POST.get("note") or "").strip()
                proof = request.FILES.get("proof")

                if proof:
                    if proof.size > 2 * 1024 * 1024:
                        error = _("Proof file too large (max 2MB)")
                    elif not proof.name.lower().endswith((".png", ".jpg", ".jpeg", ".pdf")):
                        error = _("Proof must be PNG, JPG, or PDF")

                if not error and amount <= 0:
                    error = _("Enter a payment amount")
                elif not error:
                    Payment.objects.create(
                        order=order,
                        method=method if method in Payment.Method.values else Payment.Method.CASH,
                        amount=amount,
                        reference=reference,
                        note=note,
                        proof=proof,
                        created_by=request.user,
                    )
                    order.refresh_payment_totals()
                    method_label = _payment_method_label(method)
                    log_audit(
                        action="payment_add",
                        entity_type="order",
                        entity_id=order.order_no,
                        message=f"{method_label} {amount}",
                        user=request.user,
                        branch_code=order.branch,
                    )
                    info = _("Payment added")

            order = scope_queryset_to_branch(
                request,
                Order.objects.select_related("customer", "cashier").prefetch_related("items", "payments")
            ).filter(order_no=order_no).first()

    return render(
        request,
        "orders/pickup_counter.html",
        {
            "order": order,
            "error": error,
            "info": info,
            "code": code,
            "method_choices": Payment.Method.choices,
        },
    )


@login_required
def order_kanban(request):
    qs = Order.objects.select_related("customer", "mobile_meta").order_by("created_at")
    qs = scope_queryset_to_branch(request, qs)
    qs, filters = _apply_order_filters(request, qs)
    columns = {code: [] for code, _ in Order.Status.choices}
    now = timezone.now()

    for o in qs[:600]:
        o.next_status = next_status_for_order(o)
        o.is_delayed = _is_delayed(o, now)
        columns.setdefault(o.status, []).append(o)

    column_list = [
        {"code": code, "label": label, "orders": columns.get(code, [])}
        for code, label in Order.Status.choices
    ]

    return render(
        request,
        "orders/kanban.html",
        {
            "columns": column_list,
            "status_choices": Order.Status.choices,
            **filters,
        },
    )


@login_required
def delivery_list(request):
    if not request.user.has_perm("orders.can_manage_delivery"):
        return HttpResponseBadRequest(_("Not allowed"))
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    branch = (request.GET.get("branch") or "").strip()
    date = (request.GET.get("date") or "").strip()
    driver = (request.GET.get("driver") or "").strip()
    zone = (request.GET.get("zone") or "").strip()

    qs = Order.objects.select_related("customer").filter(delivery_required=True).order_by("-created_at")
    qs = scope_queryset_to_branch(request, qs)

    if q:
        qs = qs.filter(
            Q(order_no__icontains=q)
            | Q(customer__name__icontains=q)
            | Q(customer__phone__icontains=q)
        )
    if status:
        qs = qs.filter(delivery_status=status)
    if branch:
        qs = qs.filter(branch__icontains=branch)
    if date:
        qs = qs.filter(created_at__date=date)
    if driver:
        qs = qs.filter(delivery_driver_name__icontains=driver)
    if zone:
        qs = qs.filter(delivery_zone__icontains=zone)

    orders = list(qs[:300])
    now = timezone.now()
    for o in orders:
        o.is_delayed = _is_delayed(o, now)

    return render(
        request,
        "orders/delivery_list.html",
        {
            "orders": orders,
            "q": q,
            "status": status,
            "branch": branch,
            "date": date,
            "driver": driver,
            "zone": zone,
            "status_choices": Order.DeliveryStatus.choices,
        },
    )


@login_required
def delivery_export_csv(request):
    if not request.user.has_perm("orders.can_manage_delivery"):
        return HttpResponseBadRequest(_("Not allowed"))
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    branch = (request.GET.get("branch") or "").strip()
    date = (request.GET.get("date") or "").strip()
    driver = (request.GET.get("driver") or "").strip()
    zone = (request.GET.get("zone") or "").strip()

    qs = Order.objects.select_related("customer").filter(delivery_required=True).order_by("-created_at")
    qs = scope_queryset_to_branch(request, qs)

    if q:
        qs = qs.filter(
            Q(order_no__icontains=q)
            | Q(customer__name__icontains=q)
            | Q(customer__phone__icontains=q)
        )
    if status:
        qs = qs.filter(delivery_status=status)
    if branch:
        qs = qs.filter(branch__icontains=branch)
    if date:
        qs = qs.filter(created_at__date=date)
    if driver:
        qs = qs.filter(delivery_driver_name__icontains=driver)
    if zone:
        qs = qs.filter(delivery_zone__icontains=zone)

    rows = ["order_no,customer,phone,branch,status,driver,driver_phone,zone,slot,lat,lng,fee,created_at"]
    for o in qs[:1000]:
        rows.append(
            f"{o.order_no},"
            f"\"{(o.customer.name if o.customer else '')}\","
            f"\"{(o.customer.phone if o.customer else '')}\","
            f"\"{o.branch}\","
            f"\"{o.get_delivery_status_display()}\","
            f"\"{o.delivery_driver_name}\","
            f"\"{o.delivery_driver_phone}\","
            f"\"{o.delivery_zone}\","
            f"\"{o.delivery_slot}\","
            f"\"{o.delivery_lat or ''}\","
            f"\"{o.delivery_lng or ''}\","
            f"{o.delivery_fee},"
            f"\"{o.created_at}\""
        )

    from django.http import HttpResponse
    resp = HttpResponse("\n".join(rows), content_type="text/csv")
    resp["Content-Disposition"] = "attachment; filename=delivery_export.csv"
    return resp


@login_required
def delivery_route_link(request):
    if not request.user.has_perm("orders.can_manage_delivery"):
        return HttpResponseBadRequest(_("Not allowed"))
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    branch = (request.GET.get("branch") or "").strip()
    date = (request.GET.get("date") or "").strip()
    driver = (request.GET.get("driver") or "").strip()
    zone = (request.GET.get("zone") or "").strip()

    qs = Order.objects.select_related("customer").filter(delivery_required=True).order_by("created_at")
    qs = scope_queryset_to_branch(request, qs)

    if q:
        qs = qs.filter(
            Q(order_no__icontains=q)
            | Q(customer__name__icontains=q)
            | Q(customer__phone__icontains=q)
        )
    if status:
        qs = qs.filter(delivery_status=status)
    if branch:
        qs = qs.filter(branch__icontains=branch)
    if date:
        qs = qs.filter(created_at__date=date)
    if driver:
        qs = qs.filter(delivery_driver_name__icontains=driver)
    if zone:
        qs = qs.filter(delivery_zone__icontains=zone)

    orders = list(qs[:25])
    if len(orders) < 2:
        return HttpResponseBadRequest(_("Need at least 2 deliveries to build a route"))

    def _loc(o):
        if o.delivery_lat is not None and o.delivery_lng is not None:
            return f"{o.delivery_lat},{o.delivery_lng}"
        return (o.delivery_address or o.customer.phone or o.order_no)

    origin = _loc(orders[0])
    destination = _loc(orders[-1])
    waypoints = "|".join([_loc(o) for o in orders[1:-1]])

    from urllib.parse import quote
    url = (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={quote(origin)}"
        f"&destination={quote(destination)}"
        f"&travelmode=driving"
    )
    if waypoints:
        url += f"&waypoints={quote('optimize:true|' + waypoints)}"

    return redirect(url)


@login_required
def delivery_board(request):
    if not request.user.has_perm("orders.can_manage_delivery"):
        return HttpResponseBadRequest(_("Not allowed"))
    q = (request.GET.get("q") or "").strip()
    branch = (request.GET.get("branch") or "").strip()
    date = (request.GET.get("date") or "").strip()
    driver = (request.GET.get("driver") or "").strip()
    zone = (request.GET.get("zone") or "").strip()

    qs = Order.objects.select_related("customer").filter(delivery_required=True).order_by("created_at")
    qs = scope_queryset_to_branch(request, qs)

    if q:
        qs = qs.filter(
            Q(order_no__icontains=q)
            | Q(customer__name__icontains=q)
            | Q(customer__phone__icontains=q)
        )
    if branch:
        qs = qs.filter(branch__icontains=branch)
    if date:
        qs = qs.filter(created_at__date=date)
    if driver:
        qs = qs.filter(delivery_driver_name__icontains=driver)
    if zone:
        qs = qs.filter(delivery_zone__icontains=zone)

    columns = {code: [] for code, _ in Order.DeliveryStatus.choices}
    now = timezone.now()
    for o in qs[:600]:
        o.is_delayed = _is_delayed(o, now)
        columns.setdefault(o.delivery_status, []).append(o)

    column_list = [
        {"code": code, "label": label, "orders": columns.get(code, [])}
        for code, label in Order.DeliveryStatus.choices
    ]

    return render(
        request,
        "orders/delivery_board.html",
        {
            "columns": column_list,
            "q": q,
            "branch": branch,
            "date": date,
            "driver": driver,
            "zone": zone,
            "status_choices": Order.DeliveryStatus.choices,
        },
    )


@login_required
def delivery_calendar(request):
    if not request.user.has_perm("orders.can_manage_delivery"):
        return HttpResponseBadRequest(_("Not allowed"))
    q = (request.GET.get("q") or "").strip()
    branch = (request.GET.get("branch") or "").strip()
    date = (request.GET.get("date") or "").strip()
    driver = (request.GET.get("driver") or "").strip()
    status = (request.GET.get("status") or "").strip()
    zone = (request.GET.get("zone") or "").strip()

    if not date:
        date = timezone.localdate().isoformat()

    qs = Order.objects.select_related("customer").filter(delivery_required=True).order_by("created_at")
    qs = scope_queryset_to_branch(request, qs)

    if q:
        qs = qs.filter(
            Q(order_no__icontains=q)
            | Q(customer__name__icontains=q)
            | Q(customer__phone__icontains=q)
        )
    if branch:
        qs = qs.filter(branch__icontains=branch)
    if date:
        qs = qs.filter(created_at__date=date)
    if driver:
        qs = qs.filter(delivery_driver_name__icontains=driver)
    if status:
        qs = qs.filter(delivery_status=status)
    if zone:
        qs = qs.filter(delivery_zone__icontains=zone)

    orders = list(qs[:600])
    now = timezone.now()
    for o in orders:
        o.is_delayed = _is_delayed(o, now)

    branch_obj = _get_branch_for_slots(request, branch)
    slot_templates = _parse_slot_templates(branch_obj.delivery_slot_templates if branch_obj else "")

    groups = {slot: [] for slot in slot_templates}
    groups[_("Unscheduled")] = []

    for o in orders:
        slot = (o.delivery_slot or "").strip()
        if not slot:
            slot = _("Unscheduled")
        if slot not in groups:
            groups[slot] = []
        groups[slot].append(o)

    group_list = []
    for slot in slot_templates:
        group_list.append({"slot": slot, "slot_value": slot, "orders": groups.get(slot, [])})
    if groups.get(_("Unscheduled")):
        group_list.append({"slot": _("Unscheduled"), "slot_value": "", "orders": groups.get(_("Unscheduled"), [])})

    return render(
        request,
        "orders/delivery_calendar.html",
        {
            "groups": group_list,
            "q": q,
            "branch": branch,
            "date": date,
            "driver": driver,
            "status": status,
            "zone": zone,
            "status_choices": Order.DeliveryStatus.choices,
            "slot_templates": slot_templates,
        },
    )


@login_required
def delivery_quick_update(request, order_no: str):
    if request.method != "POST":
        return HttpResponseBadRequest(_("POST required"))
    if not request.user.has_perm("orders.can_manage_delivery"):
        return HttpResponseBadRequest(_("Not allowed"))

    order = get_object_or_404(
        scope_queryset_to_branch(request, Order.objects.select_related("customer")),
        order_no=order_no,
    )

    delivery_status = (request.POST.get("delivery_status") or "").strip()
    driver_name = (request.POST.get("delivery_driver_name") or "").strip()
    driver_phone = (request.POST.get("delivery_driver_phone") or "").strip()
    zone = (request.POST.get("delivery_zone") or "").strip()

    fields = []
    if delivery_status and delivery_status in Order.DeliveryStatus.values:
        order.delivery_status = delivery_status
        fields.append("delivery_status")
        if delivery_status == Order.DeliveryStatus.DELIVERED and not order.delivered_at:
            order.delivered_at = timezone.now()
            fields.append("delivered_at")

    if driver_name:
        order.delivery_driver_name = driver_name
        fields.append("delivery_driver_name")
    if driver_phone:
        order.delivery_driver_phone = driver_phone
        fields.append("delivery_driver_phone")
    if zone:
        order.delivery_zone = zone
        fields.append("delivery_zone")

    if fields:
        order.save(update_fields=list(set(fields + ["updated_at"])))
        delivery_label = _delivery_status_label(order.delivery_status)
        log_audit(
            action="delivery_update_quick",
            entity_type="order",
            entity_id=order.order_no,
            message=_("%(status)s driver %(driver)s") % {"status": delivery_label, "driver": order.delivery_driver_name or "-"},
            user=request.user,
            branch_code=order.branch,
        )

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url:
        return redirect(next_url)
    return redirect("orders:delivery_list")


@login_required
def delivery_slot_update(request, order_no: str):
    if request.method != "POST":
        return HttpResponseBadRequest(_("POST required"))
    if not request.user.has_perm("orders.can_manage_delivery"):
        return HttpResponseBadRequest(_("Not allowed"))

    order = get_object_or_404(
        scope_queryset_to_branch(request, Order.objects.select_related("customer")),
        order_no=order_no,
    )
    slot = (request.POST.get("delivery_slot") or "").strip()
    order.delivery_slot = slot
    order.save(update_fields=["delivery_slot", "updated_at"])
    log_audit(
        action="delivery_slot_update",
        entity_type="order",
        entity_id=order.order_no,
        message=f"slot {slot}",
        user=request.user,
        branch_code=order.branch,
    )
    return JsonResponse({"ok": True})


@login_required
def delivery_week(request):
    if not request.user.has_perm("orders.can_manage_delivery"):
        return HttpResponseBadRequest(_("Not allowed"))
    q = (request.GET.get("q") or "").strip()
    branch = (request.GET.get("branch") or "").strip()
    date = (request.GET.get("date") or "").strip()
    driver = (request.GET.get("driver") or "").strip()
    status = (request.GET.get("status") or "").strip()
    zone = (request.GET.get("zone") or "").strip()

    if date:
        try:
            base_date = timezone.datetime.fromisoformat(date).date()
        except Exception:
            base_date = timezone.localdate()
    else:
        base_date = timezone.localdate()

    start_of_week = base_date - timedelta(days=base_date.weekday())
    days = [start_of_week + timedelta(days=i) for i in range(7)]

    qs = Order.objects.select_related("customer").filter(
        delivery_required=True,
        created_at__date__gte=days[0],
        created_at__date__lte=days[-1],
    ).order_by("created_at")
    qs = scope_queryset_to_branch(request, qs)

    if q:
        qs = qs.filter(
            Q(order_no__icontains=q)
            | Q(customer__name__icontains=q)
            | Q(customer__phone__icontains=q)
        )
    if branch:
        qs = qs.filter(branch__icontains=branch)
    if driver:
        qs = qs.filter(delivery_driver_name__icontains=driver)
    if status:
        qs = qs.filter(delivery_status=status)
    if zone:
        qs = qs.filter(delivery_zone__icontains=zone)

    orders = list(qs[:900])
    now = timezone.now()
    for o in orders:
        o.is_delayed = _is_delayed(o, now)

    branch_obj = _get_branch_for_slots(request, branch)
    slot_templates = _parse_slot_templates(branch_obj.delivery_slot_templates if branch_obj else "")

    day_groups = []
    for d in days:
        slot_map = {slot: [] for slot in slot_templates}
        slot_map[_("Unscheduled")] = []
        for o in orders:
            if o.created_at.date() != d:
                continue
            slot = (o.delivery_slot or "").strip()
            if not slot:
                slot = _("Unscheduled")
            if slot not in slot_map:
                slot_map[slot] = []
            slot_map[slot].append(o)
        slots = [{"slot": s, "slot_value": s, "orders": slot_map.get(s, [])} for s in slot_templates]
        if slot_map.get(_("Unscheduled")):
            slots.append({"slot": _("Unscheduled"), "slot_value": "", "orders": slot_map.get(_("Unscheduled"), [])})
        day_groups.append({"date": d, "slots": slots})

    return render(
        request,
        "orders/delivery_week.html",
        {
            "days": day_groups,
            "q": q,
            "branch": branch,
            "date": base_date.isoformat(),
            "driver": driver,
            "status": status,
            "zone": zone,
            "status_choices": Order.DeliveryStatus.choices,
            "slot_templates": slot_templates,
        },
    )


@login_required
def delivery_detail(request, order_no: str):
    if not request.user.has_perm("orders.can_manage_delivery"):
        return HttpResponseBadRequest(_("Not allowed"))

    order = get_object_or_404(
        scope_queryset_to_branch(request, Order.objects.select_related("customer", "cashier")),
        order_no=order_no,
    )
    info = None

    if request.method == "POST":
        order.delivery_required = (request.POST.get("delivery_required") or "") == "1"
        order.delivery_status = (request.POST.get("delivery_status") or Order.DeliveryStatus.PENDING)
        order.delivery_address = (request.POST.get("delivery_address") or "").strip()
        order.delivery_zone = (request.POST.get("delivery_zone") or "").strip()
        order.delivery_phone = (request.POST.get("delivery_phone") or "").strip()
        try:
            order.delivery_lat = float(request.POST.get("delivery_lat") or "")
        except Exception:
            order.delivery_lat = None
        try:
            order.delivery_lng = float(request.POST.get("delivery_lng") or "")
        except Exception:
            order.delivery_lng = None
        order.delivery_slot = (request.POST.get("delivery_slot") or "").strip()
        order.delivery_driver_name = (request.POST.get("delivery_driver_name") or "").strip()
        order.delivery_driver_phone = (request.POST.get("delivery_driver_phone") or "").strip()
        order.delivery_notes = (request.POST.get("delivery_notes") or "").strip()

        try:
            order.delivery_fee = Decimal(str(request.POST.get("delivery_fee") or "0"))
        except Exception:
            order.delivery_fee = Decimal("0")
        if order.delivery_fee < 0:
            order.delivery_fee = Decimal("0")

        if order.delivery_status == Order.DeliveryStatus.DELIVERED and not order.delivered_at:
            order.delivered_at = timezone.now()

        _recalculate_order_total(order)
        order.save(update_fields=[
            "delivery_required",
            "delivery_status",
            "delivery_address",
            "delivery_zone",
            "delivery_phone",
            "delivery_lat",
            "delivery_lng",
            "delivery_slot",
            "delivery_driver_name",
            "delivery_driver_phone",
            "delivery_notes",
            "delivery_fee",
            "delivered_at",
            "total",
            "balance",
            "updated_at",
        ])
        delivery_label = _delivery_status_label(order.delivery_status)
        log_audit(
            action="delivery_update",
            entity_type="order",
            entity_id=order.order_no,
            message=_("%(status)s fee %(fee)s") % {"status": delivery_label, "fee": order.delivery_fee},
            user=request.user,
            branch_code=order.branch,
        )

        if order.delivery_status == Order.DeliveryStatus.OUT and order.customer:
            branch_name = order.branch
            branch_obj = Branch.objects.filter(code=order.branch).first()
            if branch_obj:
                branch_name = branch_obj.name
            lang = order.customer.preferred_language if order.customer.preferred_language in ("en", "ar") else "en"
            send_whatsapp_message_auto(order, order.customer, branch_name, "out_for_delivery", lang, request.user)

        info = _("Delivery updated")

    return render(
        request,
        "orders/delivery_detail.html",
        {
            "order": order,
            "info": info,
            "status_choices": Order.DeliveryStatus.choices,
        },
    )


@login_required
def whatsapp_send(request, order_no: str):
    if request.method != "POST":
        return HttpResponseBadRequest(_("POST required"))

    order = get_object_or_404(
        scope_queryset_to_branch(request, Order.objects.select_related("customer")),
        order_no=order_no,
    )
    if not order.customer:
        return HttpResponseBadRequest(_("No customer"))

    template_key = (request.POST.get("template_key") or "").strip()
    lang = (request.POST.get("lang") or "en").strip()
    if lang not in ("en", "ar"):
        lang = "en"

    branch_name = order.branch
    branch_obj = Branch.objects.filter(code=order.branch).first()
    if branch_obj:
        branch_name = branch_obj.name

    ok, msg = send_whatsapp_message(order, order.customer, branch_name, template_key, lang, request.user)
    if not ok:
        return HttpResponseBadRequest(msg)
    return redirect("orders:detail", order_no=order.order_no)


@login_required
def whatsapp_retry(request, log_id: int):
    if request.method != "POST":
        return HttpResponseBadRequest(_("POST required"))

    log = WhatsAppMessageLog.objects.select_related("order", "customer").filter(id=log_id).first()
    if not log or not log.order or not log.customer:
        return HttpResponseBadRequest(_("Invalid log"))

    scoped = scope_queryset_to_branch(request, Order.objects.filter(id=log.order_id))
    if not scoped.exists():
        return HttpResponseBadRequest(_("Invalid log"))

    if log.attempts >= 3:
        return HttpResponseBadRequest(_("Retry limit reached"))

    branch_name = log.order.branch
    branch_obj = Branch.objects.filter(code=log.order.branch).first()
    if branch_obj:
        branch_name = branch_obj.name

    ok, msg = send_whatsapp_message(log.order, log.customer, branch_name, log.template_key, log.language, request.user)
    if not ok:
        return HttpResponseBadRequest(msg)
    return redirect("orders:detail", order_no=log.order.order_no)


def pickup_public(request, token: str):
    order = Order.objects.select_related("customer").filter(pickup_token=token).first()
    if not order:
        return render(request, "orders/pickup_public.html", {"not_found": True})

    branch_name = order.branch
    branch_obj = Branch.objects.filter(code=order.branch).first()
    if branch_obj:
        branch_name = branch_obj.name

    return render(request, "orders/pickup_public.html", {
        "order": order,
        "branch_name": branch_name,
    })


@login_required
def customer_list(request):
    q = (request.GET.get("q") or "").strip()
    vip = (request.GET.get("vip") or "").strip()

    qs = Customer.objects.all().order_by("-id")
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(phone__icontains=q)
        )
    if vip:
        qs = qs.filter(vip=True)

    return render(
        request,
        "orders/customers_list.html",
        {
            "customers": qs[:500],
            "q": q,
            "vip": vip,
        },
    )


@login_required
def customer_detail(request, customer_id: int):
    customer = get_object_or_404(Customer, id=customer_id)

    if request.method == "POST":
        if not request.user.has_perm("orders.can_discount"):
            return HttpResponseBadRequest(_("Not allowed"))
        customer.name = (request.POST.get("name") or "").strip()
        customer.phone = (request.POST.get("phone") or "").strip()
        customer.vip = (request.POST.get("vip") or "") == "1"
        customer.notes = (request.POST.get("notes") or "").strip()
        customer.address = (request.POST.get("address") or "").strip()
        customer.address2 = (request.POST.get("address2") or "").strip()
        customer.preferred_language = (request.POST.get("preferred_language") or "en").strip()
        customer.whatsapp_opt_in = (request.POST.get("whatsapp_opt_in") or "") == "1"
        customer.whatsapp_number = (request.POST.get("whatsapp_number") or "").strip()
        if customer.whatsapp_opt_in and not customer.whatsapp_opt_in_at:
            customer.whatsapp_opt_in_at = timezone.now()
        if not customer.whatsapp_opt_in:
            customer.whatsapp_opt_in_at = None
        try:
            customer.points = int(request.POST.get("points") or customer.points or 0)
        except Exception:
            customer.points = customer.points
        customer.vip_discount_percent = Decimal(str(request.POST.get("vip_discount_percent") or "0"))
        customer.save()
        return redirect("orders:customer_detail", customer_id=customer.id)

    orders = Order.objects.filter(customer=customer).order_by("-created_at")[:100]
    return render(
        request,
        "orders/customer_detail.html",
        {
            "customer": customer,
            "orders": orders,
        },
    )


@login_required
def customer_lookup(request):
    phone = (request.GET.get("phone") or "").strip()
    if not phone:
        return JsonResponse({"ok": False, "error": "Phone required"}, status=400)

    customer = Customer.objects.filter(phone__icontains=phone).order_by("-id").first()
    if not customer:
        return JsonResponse({"ok": False, "found": False})

    return JsonResponse({
        "ok": True,
        "found": True,
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "vip": customer.vip,
            "notes": customer.notes,
            "address": customer.address,
            "address2": customer.address2,
            "points": customer.points,
            "vip_discount_percent": float(customer.vip_discount_percent),
        }
    })


@login_required
def customer_get(request):
    customer_id = (request.GET.get("id") or "").strip()
    if not customer_id:
        return JsonResponse({"ok": False, "error": "ID required"}, status=400)

    customer = Customer.objects.filter(id=customer_id).first()
    if not customer:
        return JsonResponse({"ok": False, "found": False})

    return JsonResponse({
        "ok": True,
        "found": True,
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "vip": customer.vip,
            "notes": customer.notes,
            "address": customer.address,
            "address2": customer.address2,
            "points": customer.points,
            "vip_discount_percent": float(customer.vip_discount_percent),
        }
    })


@login_required
def customer_search(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"ok": True, "results": []})

    qs = Customer.objects.filter(
        Q(name__icontains=q) | Q(phone__icontains=q)
    ).order_by("-id")[:8]

    results = []
    for c in qs:
        results.append({
            "id": c.id,
            "name": c.name,
            "phone": c.phone,
            "vip": c.vip,
            "points": c.points,
            "vip_discount_percent": float(c.vip_discount_percent),
        })

    return JsonResponse({"ok": True, "results": results})


@login_required
def customer_last_order(request):
    customer_id = (request.GET.get("customer_id") or "").strip()
    phone = (request.GET.get("phone") or "").strip()

    customer = None
    if customer_id:
        customer = Customer.objects.filter(id=customer_id).first()
    elif phone:
        customer = Customer.objects.filter(phone__icontains=phone).order_by("-id").first()

    if not customer:
        return JsonResponse({"ok": False, "found": False})

    order = (
        Order.objects.filter(customer=customer)
        .prefetch_related("items")
        .order_by("-created_at")
        .first()
    )
    if not order:
        return JsonResponse({"ok": True, "found": False})

    items = []
    for it in order.items.all().order_by("id"):
        items.append({
            "item": it.item_name,
            "service": it.service_name,
            "qty": it.qty,
            "price": float(it.price),
        })

    return JsonResponse({
        "ok": True,
        "found": True,
        "order": {
            "order_no": order.order_no,
            "created_at": order.created_at.isoformat(),
            "items": items,
        }
    })


@login_required
def customer_duplicate_check(request):
    phone = (request.GET.get("phone") or "").strip()
    if not phone:
        return JsonResponse({"ok": False, "error": "Phone required"}, status=400)

    customer = Customer.objects.filter(phone__icontains=phone).order_by("-id").first()
    if not customer:
        return JsonResponse({"ok": True, "duplicate": False})

    since_hours = request.GET.get("hours")
    try:
        since_hours = int(since_hours) if since_hours is not None else 6
    except Exception:
        since_hours = 6

    since = timezone.now() - timedelta(hours=since_hours)
    recent = Order.objects.filter(customer=customer, created_at__gte=since).order_by("-created_at")
    last = recent.first()

    if not last:
        return JsonResponse({"ok": True, "duplicate": False})

    return JsonResponse({
        "ok": True,
        "duplicate": True,
        "count": recent.count(),
        "last_order_no": last.order_no,
        "last_created_at": last.created_at.isoformat(),
    })


def _sync_authorized(request) -> bool:
    sync_settings = get_sync_settings()
    endpoints_enabled = settings.SYNC_ENDPOINTS_ENABLED
    api_token = settings.SYNC_API_TOKEN
    if sync_settings:
        endpoints_enabled = sync_settings.endpoints_enabled
        api_token = sync_settings.api_token or api_token

    if not endpoints_enabled:
        return False
    token = request.headers.get("X-Sync-Token") or request.META.get("HTTP_X_SYNC_TOKEN")
    if not api_token:
        return False
    return token == api_token


@csrf_exempt
@require_http_methods(["POST"])
def sync_push(request):
    if not _sync_authorized(request):
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    customers = payload.get("customers") or []
    orders = payload.get("orders") or []
    applied_customers = 0
    applied_orders = 0

    if isinstance(customers, list):
        for customer_payload in customers:
            if not isinstance(customer_payload, dict):
                continue
            _, updated = apply_customer_payload(customer_payload)
            if updated:
                applied_customers += 1

    if isinstance(orders, list):
        for order_payload in orders:
            if not isinstance(order_payload, dict):
                continue
            _, updated = apply_order_payload(order_payload)
            if updated:
                applied_orders += 1

    return JsonResponse({"ok": True, "applied": {"customers": applied_customers, "orders": applied_orders}})


@require_http_methods(["GET"])
def sync_pull(request):
    if not _sync_authorized(request):
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=403)

    since = parse_dt((request.GET.get("since") or "").strip())
    branch = (request.GET.get("branch") or "").strip()

    customers_qs = Customer.objects.all().order_by("updated_at")
    if since:
        customers_qs = customers_qs.filter(updated_at__gt=since)

    orders_qs = Order.objects.select_related("customer").prefetch_related("items").order_by("updated_at")
    if since:
        orders_qs = orders_qs.filter(updated_at__gt=since)
    if branch:
        orders_qs = orders_qs.filter(branch__icontains=branch)

    customers = [serialize_customer(c) for c in customers_qs[:1000]]
    orders = [serialize_order(o) for o in orders_qs[:1000]]

    return JsonResponse({
        "ok": True,
        "customers": customers,
        "orders": orders,
        "server_time": timezone.now().isoformat(),
    })


@csrf_exempt
@require_http_methods(["POST"])
def central_order_webhook(request):
    authorized, auth_error = verify_central_request(request)
    if not authorized:
        return JsonResponse({"ok": False, "error": auth_error}, status=403)
    try:
        envelope = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    order_no = (envelope.get("booking_id") or "").strip()
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    if not order_no:
        return JsonResponse({"ok": False, "error": "booking_id is required"}, status=400)

    existing = Order.objects.filter(order_no=order_no).first()
    if existing:
        return JsonResponse({"ok": True, "duplicate": True, "order_no": existing.order_no})

    customer_payload = {
        "name": payload.get("fullName") or payload.get("customer_name") or "Nexivo Customer",
        "phone": payload.get("phone") or payload.get("customer_phone") or "",
        "notes": f"Created from Nexivo order {order_no}",
    }
    customer, _ = apply_customer_payload(customer_payload)
    total = Decimal(str(envelope.get("total_amount") or payload.get("estimatedTotal") or payload.get("total") or "0"))
    if total <= 0:
        return JsonResponse({"ok": False, "error": "A positive order total is required"}, status=422)
    pickup_date = payload.get("pickupDate") or payload.get("pickup_date")
    if not pickup_date:
        return JsonResponse({"ok": False, "error": "pickupDate is required"}, status=422)
    resource_id = str(envelope.get("provider_resource_id") or payload.get("serviceId") or "").strip()
    service = Service.objects.filter(pk=int(resource_id), is_active=True).first() if resource_id.isdigit() else Service.objects.filter(code__iexact=resource_id, is_active=True).first()
    if not service:
        return JsonResponse({"ok": False, "error": "Requested laundry service was not found"}, status=409)
    quantity = max(int(payload.get("quantity") or 1), 1)
    item_name = str(payload.get("itemName") or payload.get("serviceName") or service.name).strip()
    order_payload = {
        "order_no": order_no,
        "branch": payload.get("branch") or "muscat",
        "status": Order.Status.RECEIVED,
        "customer": serialize_customer(customer),
        "subtotal": str(total),
        "total": str(total),
        "balance": str(total),
        "delivery_required": bool(payload.get("deliveryAddress") or payload.get("delivery_address")),
        "delivery_address": payload.get("deliveryAddress") or payload.get("delivery_address") or "",
        "delivery_phone": customer.phone,
        "pickup_date": pickup_date,
        "pickup_slot": payload.get("pickupSlot") or payload.get("pickup_slot") or "",
        "pickup_notes": payload.get("pickupAddress") or payload.get("pickup_address") or "",
        "notes": f"Nexivo marketplace order {order_no}",
        "items": [
            {
                "item_name": item_name,
                "service_name": service.name,
                "qty": quantity,
                "price": str(total / quantity),
                "line_total": str(total),
            }
        ],
    }
    order, _ = apply_order_payload(order_payload)
    return JsonResponse({"ok": True, "order_no": order.order_no if order else order_no})
