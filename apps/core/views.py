from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.db.models.functions import ExtractHour

from apps.accounts.utils import scope_queryset_to_branch
from apps.management.models import Branch
from apps.orders.models import Order, OrderItem, OrderStatusLog
from apps.payments.models import Payment


@login_required
def home(request):
    today = timezone.localdate()
    now_dt = timezone.localtime()
    is_ar = str(getattr(request, "LANGUAGE_CODE", "")).lower().startswith("ar")

    orders_qs = scope_queryset_to_branch(request, Order.objects.select_related("customer"))

    today_orders = orders_qs.filter(created_at__date=today).count()
    today_revenue = (
        orders_qs.filter(created_at__date=today)
        .aggregate(total=Sum("total"))
        .get("total")
        or Decimal("0.000")
    )
    pending_orders = orders_qs.exclude(
        status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED]
    ).count()
    ready_orders = orders_qs.filter(status=Order.Status.READY).count()

    today_sales = (
        scope_queryset_to_branch(
            request, Payment.objects.select_related("order"), field_name="order__branch"
        )
        .filter(created_at__date=today)
        .aggregate(total=Sum("amount"))
        .get("total")
        or Decimal("0.000")
    )
    avg_ticket_today = (today_revenue / Decimal(today_orders)) if today_orders else Decimal("0.000")
    delivery_due_today = orders_qs.filter(delivery_required=True).exclude(
        status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED]
    ).count()
    unpaid_orders = orders_qs.filter(balance__gt=0).count()

    active_branch_code = (request.session.get("active_branch") or "").strip()
    branch_obj = Branch.objects.filter(code__iexact=active_branch_code).first() if active_branch_code else None
    branch_code = (branch_obj.code if branch_obj else active_branch_code or "").strip().upper() or _("Branch")

    stats = {
        "today_orders": today_orders,
        "pending_orders": pending_orders,
        "ready_orders": ready_orders,
        "today_sales": f"{today_revenue:.3f}",
        "collected_today": f"{today_sales:.3f}",
        "avg_ticket_today": f"{avg_ticket_today:.3f}",
        "delivery_due_today": delivery_due_today,
        "unpaid_orders": unpaid_orders,
        "branch": branch_code,
        "date": today,
    }

    status = [
        {"label": _("Received"), "count": orders_qs.filter(status=Order.Status.RECEIVED).count()},
        {"label": _("Washing"), "count": orders_qs.filter(status=Order.Status.WASHING).count()},
        {"label": _("Ironing"), "count": orders_qs.filter(status=Order.Status.IRONING).count()},
        {"label": _("Ready"), "count": orders_qs.filter(status=Order.Status.READY).count()},
    ]

    hourly_rows = (
        orders_qs.filter(created_at__date=today)
        .annotate(hour=ExtractHour("created_at"))
        .values("hour")
        .annotate(orders=Count("id"), revenue=Sum("total"))
        .order_by("hour")
    )
    hourly_map = {
        int(row["hour"]): {
            "orders": int(row["orders"] or 0),
            "revenue": float(row["revenue"] or 0),
        }
        for row in hourly_rows
        if row.get("hour") is not None
    }
    hour_slots = []
    for back in range(7, -1, -1):
        h = (now_dt.hour - back) % 24
        slot = hourly_map.get(h, {"orders": 0, "revenue": 0.0})
        hour_slots.append(
            {
                "label": f"{h:02d}:00",
                "orders": slot["orders"],
                "revenue": slot["revenue"],
            }
        )
    max_hour_orders = max((s["orders"] for s in hour_slots), default=0)
    for slot in hour_slots:
        slot["bar_pct"] = 0 if max_hour_orders == 0 else int((slot["orders"] * 100) / max_hour_orders)

    service_rows = (
        scope_queryset_to_branch(
            request,
            OrderItem.objects.filter(order__created_at__date=today),
            field_name="order__branch",
        )
        .values("service_name")
        .annotate(qty=Sum("qty"))
        .order_by("-qty")[:5]
    )
    total_service_qty = sum(int(row["qty"] or 0) for row in service_rows)
    mix_colors = ["#1E6CCB", "#19B6B6", "#7C3AED", "#F59E0B", "#10B981"]
    service_mix = []
    donut_parts = []
    progress = 0
    for idx, row in enumerate(service_rows):
        qty = int(row["qty"] or 0)
        pct = 0 if total_service_qty == 0 else round((qty * 100) / total_service_qty, 1)
        color = mix_colors[idx % len(mix_colors)]
        service_mix.append(
            {
                "name": row["service_name"] or _("Unknown"),
                "qty": qty,
                "pct": pct,
                "color": color,
            }
        )
        next_progress = min(100, progress + pct)
        donut_parts.append(f"{color} {progress}% {next_progress}%")
        progress = next_progress
    if progress < 100:
        donut_parts.append(f"#E7EEF7 {progress}% 100%")
    service_mix_gradient = f"conic-gradient({', '.join(donut_parts)})" if donut_parts else "conic-gradient(#E7EEF7 0% 100%)"

    open_orders_qs = orders_qs.exclude(status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED])
    aging_buckets = {
        "lt2h": 0,
        "h2_6": 0,
        "h6_24": 0,
        "gt24": 0,
    }
    for created_at in open_orders_qs.values_list("created_at", flat=True):
        if not created_at:
            continue
        age_hours = (now_dt - timezone.localtime(created_at)).total_seconds() / 3600
        if age_hours < 2:
            aging_buckets["lt2h"] += 1
        elif age_hours < 6:
            aging_buckets["h2_6"] += 1
        elif age_hours < 24:
            aging_buckets["h6_24"] += 1
        else:
            aging_buckets["gt24"] += 1
    aging_total = sum(aging_buckets.values())
    aging_data = [
        {
            "label": ("< ساعتين" if is_ar else "< 2h"),
            "count": aging_buckets["lt2h"],
            "pct": 0 if aging_total == 0 else int((aging_buckets["lt2h"] * 100) / aging_total),
            "tone": "ok",
        },
        {
            "label": ("2-6 ساعات" if is_ar else "2-6h"),
            "count": aging_buckets["h2_6"],
            "pct": 0 if aging_total == 0 else int((aging_buckets["h2_6"] * 100) / aging_total),
            "tone": "mid",
        },
        {
            "label": ("6-24 ساعة" if is_ar else "6-24h"),
            "count": aging_buckets["h6_24"],
            "pct": 0 if aging_total == 0 else int((aging_buckets["h6_24"] * 100) / aging_total),
            "tone": "warn",
        },
        {
            "label": ("> 24 ساعة" if is_ar else "> 24h"),
            "count": aging_buckets["gt24"],
            "pct": 0 if aging_total == 0 else int((aging_buckets["gt24"] * 100) / aging_total),
            "tone": "danger",
        },
    ]

    recent_activity = []

    for order in orders_qs.order_by("-created_at")[:10]:
        customer_name = (order.customer.name if order.customer else "") or "-"
        title = (
            f"تم إنشاء الطلب #{order.order_no}"
            if is_ar
            else _("Order #%(order)s created") % {"order": order.order_no}
        )
        sub = (
            f"العميل: {customer_name}"
            if is_ar
            else _("Customer: %(customer)s") % {"customer": customer_name}
        )
        recent_activity.append(
            {
                "ts": order.created_at,
                "title": title,
                "sub": sub,
            }
        )

    payment_qs = scope_queryset_to_branch(
        request, Payment.objects.select_related("order"), field_name="order__branch"
    ).order_by("-created_at")[:10]
    for pay in payment_qs:
        order_no = pay.order.order_no if pay.order_id else "-"
        method = pay.get_method_display()
        amount = f"{pay.amount:.3f}"
        title = "تم استلام الدفع" if is_ar else _("Payment received")
        sub = (
            f"الطلب #{order_no} - {method} {amount}"
            if is_ar
            else _("Order #%(order)s - %(method)s %(amount)s")
            % {"order": order_no, "method": method, "amount": amount}
        )
        recent_activity.append(
            {
                "ts": pay.created_at,
                "title": title,
                "sub": sub,
            }
        )

    status_logs_qs = scope_queryset_to_branch(
        request,
        OrderStatusLog.objects.select_related("order", "order__customer"),
        field_name="order__branch",
    ).order_by("-created_at")[:10]
    for log in status_logs_qs:
        order_no = log.order.order_no if log.order_id else "-"
        from_label = log.from_status_label or "-"
        to_label = log.to_status_label or "-"
        title = "تم تحديث حالة الطلب" if is_ar else _("Order status updated")
        sub = (
            f"الطلب #{order_no}: {from_label} ← {to_label}"
            if is_ar
            else _("Order #%(order)s: %(from)s -> %(to)s")
            % {"order": order_no, "from": from_label, "to": to_label}
        )
        recent_activity.append(
            {
                "ts": log.created_at,
                "title": title,
                "sub": sub,
            }
        )

    recent_activity.sort(key=lambda x: x["ts"] or timezone.now(), reverse=True)
    recent_activity = recent_activity[:10]

    return render(
        request,
        "core/home.html",
        {
            "stats": stats,
            "status": status,
            "recent_activity": recent_activity,
            "hour_slots": hour_slots,
            "service_mix": service_mix,
            "service_mix_gradient": service_mix_gradient,
            "aging_data": aging_data,
            "aging_total": aging_total,
        },
    )
