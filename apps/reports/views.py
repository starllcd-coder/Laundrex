import csv
import io
import base64
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Sum, Count, Min, Max, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.orders.models import Order, OrderItem
from apps.payments.models import Payment
from apps.accounts.utils import scope_queryset_to_branch
from apps.management.models import Branch

PACK_CHOICES = [
    ("all", "All Reports"),
    ("sales", "Sales & Revenue Reports"),
    ("operations", "Orders & Operations Reports"),
    ("customers", "Customer Reports"),
    ("delivery", "Delivery & Logistics Reports"),
    ("expenses", "Expense & Profit Reports"),
    ("staff", "Staff Performance Reports"),
    ("quality", "Issue & Quality Reports"),
]


def _resolve_active_brand(request):
    business_name = "Laundrex"
    logo_url = ""
    logo_path = ""

    code = (request.session.get("active_branch") or "").strip()
    branch = None
    if code:
        branch = Branch.objects.filter(code__iexact=code).first() or Branch.objects.filter(name__iexact=code).first()
    if not branch:
        branch = Branch.objects.filter(active=True).order_by("name").first()

    logo_bytes = b""
    logo_mime = ""

    if branch:
        business_name = (branch.name or business_name).strip() or business_name
        if getattr(branch, "receipt_logo", None):
            try:
                logo_url = branch.receipt_logo.url
            except Exception:
                logo_url = ""
            try:
                logo_path = branch.receipt_logo.path
            except Exception:
                logo_path = ""
            try:
                logo_name = (branch.receipt_logo.name or "").lower()
                logo_mime = "image/png"
                if logo_name.endswith(".jpg") or logo_name.endswith(".jpeg"):
                    logo_mime = "image/jpeg"
                elif logo_name.endswith(".gif"):
                    logo_mime = "image/gif"
                elif logo_name.endswith(".webp"):
                    logo_mime = "image/webp"
                with branch.receipt_logo.open("rb") as fh:
                    logo_bytes = fh.read() or b""
            except Exception:
                logo_bytes = b""
                logo_mime = ""

    # Desktop local DB can miss `receipt_logo` even if file exists in shared media folder.
    # Fallback to first uploaded branch logo file so reports still show branding.
    if not logo_bytes:
        try:
            logo_dir = Path(settings.MEDIA_ROOT) / "branch_receipt_logos"
            if logo_dir.exists():
                candidates = sorted([p for p in logo_dir.glob("*") if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)
                if candidates:
                    picked = candidates[0]
                    name = picked.name.lower()
                    logo_mime = "image/png"
                    if name.endswith(".jpg") or name.endswith(".jpeg"):
                        logo_mime = "image/jpeg"
                    elif name.endswith(".gif"):
                        logo_mime = "image/gif"
                    elif name.endswith(".webp"):
                        logo_mime = "image/webp"
                    logo_bytes = picked.read_bytes() or b""
                    logo_path = str(picked)
                    logo_url = f"{settings.MEDIA_URL.rstrip('/')}/branch_receipt_logos/{picked.name}"
        except Exception:
            pass

    return {
        "active_business_name": business_name,
        "active_business_logo_url": logo_url,
        "active_business_logo_path": logo_path,
        "active_business_logo_bytes": logo_bytes,
        "active_business_logo_b64": base64.b64encode(logo_bytes).decode("ascii") if logo_bytes else "",
        "active_business_logo_mime": logo_mime,
    }


def _resolve_period(period, start_text, end_text):
    today = timezone.localdate()
    if period == "weekly":
        return today - timedelta(days=6), today
    if period == "monthly":
        return today.replace(day=1), today
    start = parse_date(start_text) if start_text else None
    end = parse_date(end_text) if end_text else None
    return start, end


def _build_export_context(request):
    branch = (request.GET.get("branch") or "").strip()
    mode = (request.GET.get("mode") or "").strip().lower()
    period = (request.GET.get("period") or "custom").strip().lower()
    selected_pack = (request.GET.get("pack") or "all").strip().lower()
    if not any(selected_pack == code for code, _ in PACK_CHOICES):
        selected_pack = "all"
    start_input = (request.GET.get("start") or "").strip()
    end_input = (request.GET.get("end") or "").strip()
    start_date, end_date = _resolve_period(period, start_input, end_input)

    qs = scope_queryset_to_branch(request, Order.objects.all())
    if start_date:
        qs = qs.filter(created_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__date__lte=end_date)
    if branch:
        qs = qs.filter(branch__icontains=branch)
    if mode == "walkin":
        qs = qs.filter(delivery_required=False)
    elif mode == "delivery":
        qs = qs.filter(delivery_required=True)

    totals = qs.aggregate(
        orders=Count("id"),
        revenue=Sum("total"),
        paid=Sum("paid"),
        balance=Sum("balance"),
    )
    top_services = list(
        OrderItem.objects.filter(order__in=qs)
        .values("service_name")
        .annotate(revenue=Sum("line_total"), qty=Sum("qty"), orders=Count("order_id", distinct=True))
        .order_by("-revenue")[:50]
    )
    revenue_by_item = list(
        OrderItem.objects.filter(order__in=qs)
        .values("item_name")
        .annotate(revenue=Sum("line_total"), qty=Sum("qty"), orders=Count("order_id", distinct=True))
        .order_by("-revenue")[:100]
    )
    by_status = list(
        qs.values("status")
        .annotate(c=Count("id"))
        .order_by("status")
    )
    top_customers = list(
        qs.filter(customer__isnull=False)
        .values("customer__name", "customer__phone")
        .annotate(revenue=Sum("total"), orders=Count("id"))
        .order_by("-revenue")[:100]
    )
    delivery_by_status = list(
        qs.filter(delivery_required=True)
        .values("delivery_status")
        .annotate(c=Count("id"))
        .order_by("delivery_status")
    )
    driver_performance = list(
        qs.filter(delivery_required=True)
        .exclude(delivery_driver_name="")
        .values("delivery_driver_name")
        .annotate(
            total_deliveries=Count("id"),
            delivered=Count("id", filter=Q(delivery_status=Order.DeliveryStatus.DELIVERED)),
            failed=Count("id", filter=Q(delivery_status=Order.DeliveryStatus.FAILED)),
        )
        .order_by("-total_deliveries")[:100]
    )
    staff_performance = list(
        qs.filter(cashier__isnull=False)
        .values("cashier__username", "cashier__first_name", "cashier__last_name")
        .annotate(
            orders=Count("id"),
            delivered=Count("id", filter=Q(status=Order.Status.DELIVERED)),
            cancelled=Count("id", filter=Q(status=Order.Status.CANCELLED)),
        )
        .order_by("-orders")[:100]
    )
    today = timezone.localdate()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    base_scope = scope_queryset_to_branch(request, Order.objects.all())
    if branch:
        base_scope = base_scope.filter(branch__icontains=branch)
    if mode == "walkin":
        base_scope = base_scope.filter(delivery_required=False)
    elif mode == "delivery":
        base_scope = base_scope.filter(delivery_required=True)
    context = {
        "selected_pack": selected_pack,
        "mode": mode,
        "period": period,
        "start": start_date.isoformat() if start_date else "",
        "end": end_date.isoformat() if end_date else "",
        "totals": totals,
        "daily_revenue": base_scope.filter(created_at__date=today).aggregate(total=Sum("total"))["total"] or 0,
        "weekly_revenue": base_scope.filter(created_at__date__gte=start_of_week).aggregate(total=Sum("total"))["total"] or 0,
        "monthly_revenue": base_scope.filter(created_at__date__gte=start_of_month).aggregate(total=Sum("total"))["total"] or 0,
        "top_services": top_services,
        "revenue_by_item": revenue_by_item,
        "by_status": [{"label": x["status"], "c": x["c"]} for x in by_status],
        "top_customers": top_customers,
        "delivery_by_status": [{"label": x["delivery_status"], "c": x["c"]} for x in delivery_by_status],
        "driver_performance": driver_performance,
        "staff_performance": staff_performance,
    }
    context.update(_resolve_active_brand(request))
    return context


def _pack_tables(context):
    pack = context.get("selected_pack", "all")
    tables = []
    if pack in ("all", "sales"):
        tables.append(("Sales Summary", ["Metric", "Value"], [
            ["Orders", context["totals"].get("orders") or 0],
            ["Revenue", context["totals"].get("revenue") or 0],
            ["Paid", context["totals"].get("paid") or 0],
            ["Amount Due", context["totals"].get("balance") or 0],
            ["Daily Revenue", context.get("daily_revenue") or 0],
            ["Weekly Revenue", context.get("weekly_revenue") or 0],
            ["Monthly Revenue", context.get("monthly_revenue") or 0],
        ]))
        tables.append(("Revenue by Service", ["Service", "Qty", "Orders", "Revenue"], [
            [x.get("service_name") or "-", x.get("qty") or 0, x.get("orders") or 0, x.get("revenue") or 0]
            for x in context.get("top_services", [])
        ]))
        tables.append(("Revenue by Item", ["Item", "Qty", "Orders", "Revenue"], [
            [x.get("item_name") or "-", x.get("qty") or 0, x.get("orders") or 0, x.get("revenue") or 0]
            for x in context.get("revenue_by_item", [])
        ]))
    if pack in ("all", "operations"):
        tables.append(("Orders by Status", ["Status", "Count"], [
            [x.get("label") or x.get("status") or "-", x.get("c") or 0]
            for x in context.get("by_status", [])
        ]))
    if pack in ("all", "customers"):
        tables.append(("Top Customers", ["Customer", "Phone", "Orders", "Revenue"], [
            [x.get("customer__name") or "Walk-in", x.get("customer__phone") or "-", x.get("orders") or 0, x.get("revenue") or 0]
            for x in context.get("top_customers", [])
        ]))
    if pack in ("all", "delivery"):
        tables.append(("Delivery Status", ["Status", "Count"], [
            [x.get("label") or x.get("status") or "-", x.get("c") or 0]
            for x in context.get("delivery_by_status", [])
        ]))
        tables.append(("Driver Performance", ["Driver", "Orders", "Delivered", "Failed"], [
            [x.get("delivery_driver_name") or "-", x.get("total_deliveries") or 0, x.get("delivered") or 0, x.get("failed") or 0]
            for x in context.get("driver_performance", [])
        ]))
    if pack in ("all", "staff"):
        tables.append(("Staff Performance", ["Staff", "Orders", "Delivered", "Cancelled"], [
            [f"{x.get('cashier__first_name') or x.get('cashier__username') or '-'} {x.get('cashier__last_name') or ''}".strip(),
             x.get("orders") or 0, x.get("delivered") or 0, x.get("cancelled") or 0]
            for x in context.get("staff_performance", [])
        ]))
    if pack in ("expenses", "quality"):
        label = "Expense & Profit Reports" if pack == "expenses" else "Issue & Quality Reports"
        tables.append((label, ["Status"], [["Not available yet. Requires dedicated data tracking models."]]))
    return tables


@login_required
@permission_required("orders.can_view_reports", raise_exception=True)
def reports_home(request):
    branch = (request.GET.get("branch") or "").strip()
    mode = (request.GET.get("mode") or "").strip().lower()
    period = (request.GET.get("period") or "custom").strip().lower()
    selected_pack = (request.GET.get("pack") or "all").strip().lower()
    if not any(selected_pack == code for code, _ in PACK_CHOICES):
        selected_pack = "all"
    start_input = (request.GET.get("start") or "").strip()
    end_input = (request.GET.get("end") or "").strip()
    start_date, end_date = _resolve_period(period, start_input, end_input)
    start = start_date.isoformat() if start_date else ""
    end = end_date.isoformat() if end_date else ""

    base_qs = Order.objects.all().order_by("-created_at")
    base_qs = scope_queryset_to_branch(request, base_qs)

    # Date range filter (by date)
    qs = base_qs
    if start_date:
        qs = qs.filter(created_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__date__lte=end_date)

    # Branch filter
    if branch:
        qs = qs.filter(branch__icontains=branch)
        base_qs = base_qs.filter(branch__icontains=branch)
    if mode == "walkin":
        qs = qs.filter(delivery_required=False)
        base_qs = base_qs.filter(delivery_required=False)
    elif mode == "delivery":
        qs = qs.filter(delivery_required=True)
        base_qs = base_qs.filter(delivery_required=True)

    totals = qs.aggregate(
        orders=Count("id"),
        revenue=Sum("total"),
        paid=Sum("paid"),
        balance=Sum("balance"),
    )

    avg_order_value = None
    if totals.get("orders"):
        try:
            avg_order_value = (totals.get("revenue") or 0) / totals.get("orders")
        except Exception:
            avg_order_value = None

    today = timezone.localdate()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)

    daily_revenue = base_qs.filter(created_at__date=today).aggregate(total=Sum("total"))["total"] or 0
    weekly_revenue = base_qs.filter(created_at__date__gte=start_of_week).aggregate(total=Sum("total"))["total"] or 0
    monthly_revenue = base_qs.filter(created_at__date__gte=start_of_month).aggregate(total=Sum("total"))["total"] or 0

    top_services = list(
        OrderItem.objects.filter(order__in=qs)
        .values("service_name")
        .annotate(revenue=Sum("line_total"), qty=Sum("qty"), orders=Count("order_id", distinct=True))
        .order_by("-revenue")[:8]
    )
    revenue_by_item = list(
        OrderItem.objects.filter(order__in=qs)
        .values("item_name")
        .annotate(revenue=Sum("line_total"), qty=Sum("qty"), orders=Count("order_id", distinct=True))
        .order_by("-revenue")[:12]
    )

    top_customers = list(
        qs.filter(customer__isnull=False)
        .values("customer__name", "customer__phone")
        .annotate(revenue=Sum("total"), orders=Count("id"))
        .order_by("-revenue")[:8]
    )
    customer_rows = list(
        qs.filter(customer__isnull=False)
        .values("customer_id", "customer__name", "customer__phone")
        .annotate(revenue=Sum("total"), orders=Count("id"))
    )
    customer_ids = [x["customer_id"] for x in customer_rows if x.get("customer_id")]
    first_order_map = {
        cid: first_dt for cid, first_dt in
        base_qs.filter(customer_id__in=customer_ids)
        .values("customer_id")
        .annotate(first_dt=Min("created_at"))
        .values_list("customer_id", "first_dt")
    }
    period_start = parse_date(start) if start else None
    period_end = parse_date(end) if end else None
    if period_start is None:
        period_start = qs.aggregate(v=Min("created_at"))["v"]
        period_start = period_start.date() if period_start else None
    if period_end is None:
        period_end = qs.aggregate(v=Max("created_at"))["v"]
        period_end = timezone.localdate() if period_end else None
    new_customers = 0
    returning_customers = 0
    retention_rate = 0
    for row in customer_rows:
        first_dt = first_order_map.get(row["customer_id"])
        first_date = first_dt.date() if first_dt else None
        if first_date and period_start and period_end and period_start <= first_date <= period_end:
            new_customers += 1
        else:
            returning_customers += 1
    total_customer_segments = new_customers + returning_customers
    if total_customer_segments:
        retention_rate = round((returning_customers / total_customer_segments) * 100, 1)

    location_customers = list(
        qs.filter(customer__isnull=False)
        .exclude(delivery_zone="")
        .values("delivery_zone")
        .annotate(customers=Count("customer_id", distinct=True), orders=Count("id"), revenue=Sum("total"))
        .order_by("-customers", "-orders")[:10]
    )
    if not location_customers:
        location_customers = list(
            qs.filter(customer__isnull=False)
            .exclude(customer__address="")
            .values("customer__address")
            .annotate(customers=Count("customer_id", distinct=True), orders=Count("id"), revenue=Sum("total"))
            .order_by("-customers", "-orders")[:10]
        )

    now = timezone.now()
    delay_cutoff = now - timedelta(hours=48)
    delayed_orders = qs.filter(
        created_at__lte=delay_cutoff
    ).exclude(status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED]).count()
    pending_deliveries = qs.filter(
        delivery_required=True,
        delivery_status__in=[Order.DeliveryStatus.PENDING, Order.DeliveryStatus.ASSIGNED, Order.DeliveryStatus.OUT],
    ).count()
    unpaid_orders = qs.filter(balance__gt=0).count()
    cancelled_orders = qs.filter(status=Order.Status.CANCELLED).count()
    express_orders = qs.filter(urgent=True).count()
    normal_orders = qs.filter(urgent=False).count()
    pickup_orders = qs.filter(delivery_required=False).count()
    delivery_orders = qs.filter(delivery_required=True).count()

    delivery_status_label_map = {code: label for code, label in Order.DeliveryStatus.choices}
    delivery_by_status_raw = (
        qs.filter(delivery_required=True)
        .values("delivery_status")
        .annotate(c=Count("id"))
        .order_by("delivery_status")
    )
    delivery_by_status = [
        {
            "status": row["delivery_status"],
            "label": delivery_status_label_map.get(row["delivery_status"], row["delivery_status"]),
            "c": row["c"],
        }
        for row in delivery_by_status_raw
    ]
    delivered_with_eta = qs.filter(
        delivery_required=True,
        delivery_status=Order.DeliveryStatus.DELIVERED,
        estimated_ready_at__isnull=False,
        delivered_at__isnull=False,
    ).values_list("delivered_at", "estimated_ready_at")
    on_time_deliveries = 0
    late_deliveries = 0
    for delivered_at, eta_at in delivered_with_eta:
        if delivered_at <= eta_at:
            on_time_deliveries += 1
        else:
            late_deliveries += 1

    driver_performance = list(
        qs.filter(delivery_required=True)
        .exclude(delivery_driver_name="")
        .values("delivery_driver_name")
        .annotate(
            total_deliveries=Count("id"),
            delivered=Count("id", filter=Q(delivery_status=Order.DeliveryStatus.DELIVERED)),
            failed=Count("id", filter=Q(delivery_status=Order.DeliveryStatus.FAILED)),
            pending=Count("id", filter=Q(delivery_status__in=[
                Order.DeliveryStatus.PENDING,
                Order.DeliveryStatus.ASSIGNED,
                Order.DeliveryStatus.OUT,
            ])),
            revenue=Sum("total"),
        )
        .order_by("-delivered", "-total_deliveries")[:10]
    )
    area_performance = list(
        qs.filter(delivery_required=True)
        .exclude(delivery_zone="")
        .values("delivery_zone")
        .annotate(
            orders=Count("id"),
            delivered=Count("id", filter=Q(delivery_status=Order.DeliveryStatus.DELIVERED)),
            failed=Count("id", filter=Q(delivery_status=Order.DeliveryStatus.FAILED)),
            pending=Count("id", filter=Q(delivery_status__in=[
                Order.DeliveryStatus.PENDING,
                Order.DeliveryStatus.ASSIGNED,
                Order.DeliveryStatus.OUT,
            ])),
            revenue=Sum("total"),
        )
        .order_by("-orders", "-revenue")[:10]
    )
    staff_performance = list(
        qs.filter(cashier__isnull=False)
        .values("cashier__username", "cashier__first_name", "cashier__last_name")
        .annotate(
            orders=Count("id"),
            delivered=Count("id", filter=Q(status=Order.Status.DELIVERED)),
            cancelled=Count("id", filter=Q(status=Order.Status.CANCELLED)),
            revenue=Sum("total"),
        )
        .order_by("-orders", "-revenue")[:10]
    )

    # last 7 days trend
    trend = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_qs = base_qs.filter(created_at__date=day)
        day_total = day_qs.aggregate(total=Sum("total"))["total"] or 0
        day_orders = day_qs.aggregate(count=Count("id"))["count"] or 0
        trend.append({"date": day, "revenue": day_total, "orders": day_orders})
    max_rev = max([t["revenue"] for t in trend]) if trend else 0
    max_orders = max([t["orders"] for t in trend]) if trend else 0
    for t in trend:
        t["rev_pct"] = int((t["revenue"] / max_rev) * 100) if max_rev else 0
        t["order_pct"] = int((t["orders"] / max_orders) * 100) if max_orders else 0

    # weekly trend (last 8 weeks)
    weekly = []
    week_start = today - timedelta(days=today.weekday())
    for i in range(7, -1, -1):
        week_from = week_start - timedelta(days=7 * i)
        week_to = week_from + timedelta(days=6)
        w_qs = base_qs.filter(created_at__date__gte=week_from, created_at__date__lte=week_to)
        w_total = w_qs.aggregate(total=Sum("total"))["total"] or 0
        w_orders = w_qs.aggregate(count=Count("id"))["count"] or 0
        weekly.append({"start": week_from, "revenue": w_total, "orders": w_orders})
    max_w_rev = max([t["revenue"] for t in weekly]) if weekly else 0
    max_w_orders = max([t["orders"] for t in weekly]) if weekly else 0
    for t in weekly:
        t["rev_pct"] = int((t["revenue"] / max_w_rev) * 100) if max_w_rev else 0
        t["order_pct"] = int((t["orders"] / max_w_orders) * 100) if max_w_orders else 0

    # monthly trend (last 6 months)
    monthly = []
    year = today.year
    month = today.month
    for i in range(5, -1, -1):
        m = month - i
        y = year
        while m <= 0:
            m += 12
            y -= 1
        month_from = today.replace(year=y, month=m, day=1)
        month_to = (month_from + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        m_qs = base_qs.filter(created_at__date__gte=month_from, created_at__date__lte=month_to)
        m_total = m_qs.aggregate(total=Sum("total"))["total"] or 0
        m_orders = m_qs.aggregate(count=Count("id"))["count"] or 0
        monthly.append({"start": month_from, "revenue": m_total, "orders": m_orders})
    max_m_rev = max([t["revenue"] for t in monthly]) if monthly else 0
    max_m_orders = max([t["orders"] for t in monthly]) if monthly else 0
    for t in monthly:
        t["rev_pct"] = int((t["revenue"] / max_m_rev) * 100) if max_m_rev else 0
        t["order_pct"] = int((t["orders"] / max_m_orders) * 100) if max_m_orders else 0

    status_label_map = {code: label for code, label in Order.Status.choices}
    by_status_raw = qs.values("status").annotate(c=Count("id")).order_by("status")
    by_status = [
        {
            "status": row["status"],
            "label": status_label_map.get(row["status"], row["status"]),
            "c": row["c"],
        }
        for row in by_status_raw
    ]

    # Recent orders preview (top 30)
    recent = qs.select_related("customer", "cashier")[:30]

    context = {
        "branch": branch,
        "mode": mode,
        "start": start,
        "end": end,
        "period": period,
        "selected_pack": selected_pack,
        "pack_choices": PACK_CHOICES,
        "totals": totals,
        "avg_order_value": avg_order_value,
        "daily_revenue": daily_revenue,
        "weekly_revenue": weekly_revenue,
        "monthly_revenue": monthly_revenue,
        "top_services": top_services,
        "top_customers": top_customers,
        "delayed_orders": delayed_orders,
        "pending_deliveries": pending_deliveries,
        "unpaid_orders": unpaid_orders,
        "cancelled_orders": cancelled_orders,
        "express_orders": express_orders,
        "normal_orders": normal_orders,
        "pickup_orders": pickup_orders,
        "delivery_orders": delivery_orders,
        "delivery_by_status": delivery_by_status,
        "on_time_deliveries": on_time_deliveries,
        "late_deliveries": late_deliveries,
        "trend": trend,
        "weekly_trend": weekly,
        "monthly_trend": monthly,
        "by_status": by_status,
        "revenue_by_item": revenue_by_item,
        "new_customers": new_customers,
        "returning_customers": returning_customers,
        "retention_rate": retention_rate,
        "location_customers": location_customers,
        "driver_performance": driver_performance,
        "area_performance": area_performance,
        "staff_performance": staff_performance,
        "recent": recent,
        "generated_at": timezone.localtime(),
        "auto_print": bool(request.GET.get("autoprint")),
    }
    context.update(_resolve_active_brand(request))
    return render(request, "reports/home.html", context)


@login_required
@permission_required("orders.can_view_reports", raise_exception=True)
def z_report(request):
    date = (request.GET.get("date") or "").strip()
    branch = (request.GET.get("branch") or "").strip()

    if not date:
        date = timezone.localdate().isoformat()

    orders = scope_queryset_to_branch(request, Order.objects.filter(created_at__date=date))
    payments = scope_queryset_to_branch(request, Payment.objects.filter(created_at__date=date), field_name="order__branch")

    if branch:
        orders = orders.filter(branch__icontains=branch)
        payments = payments.filter(order__branch__icontains=branch)

    order_totals = orders.aggregate(
        orders=Count("id"),
        revenue=Sum("total"),
        paid=Sum("paid"),
        balance=Sum("balance"),
    )

    method_label_map = {code: label for code, label in Payment.Method.choices}
    by_method_raw = payments.values("method").annotate(total=Sum("amount"), count=Count("id")).order_by("method")
    by_method = [
        {
            "method": row["method"],
            "label": method_label_map.get(row["method"], row["method"]),
            "total": row["total"],
            "count": row["count"],
        }
        for row in by_method_raw
    ]
    payment_total = payments.aggregate(total=Sum("amount"))

    context = {
        "date": date,
        "branch": branch,
        "order_totals": order_totals,
        "by_method": by_method,
        "payment_total": payment_total,
        "payments": payments.select_related("order").order_by("-created_at")[:200],
        "generated_at": timezone.localtime(),
    }
    context.update(_resolve_active_brand(request))
    return render(request, "reports/z_report.html", context)


@login_required
@permission_required("orders.can_view_reports", raise_exception=True)
def export_z_report_pdf(request):
    date = (request.GET.get("date") or "").strip()
    branch = (request.GET.get("branch") or "").strip()
    if not date:
        date = timezone.localdate().isoformat()

    orders = scope_queryset_to_branch(request, Order.objects.filter(created_at__date=date))
    payments = scope_queryset_to_branch(request, Payment.objects.filter(created_at__date=date), field_name="order__branch")
    if branch:
        orders = orders.filter(branch__icontains=branch)
        payments = payments.filter(order__branch__icontains=branch)

    order_totals = orders.aggregate(
        orders=Count("id"),
        revenue=Sum("total"),
        paid=Sum("paid"),
        balance=Sum("balance"),
    )
    method_label_map = {code: label for code, label in Payment.Method.choices}
    by_method_raw = payments.values("method").annotate(total=Sum("amount"), count=Count("id")).order_by("method")
    by_method = [
        {
            "method": row["method"],
            "label": method_label_map.get(row["method"], row["method"]),
            "total": row["total"] or 0,
            "count": row["count"] or 0,
        }
        for row in by_method_raw
    ]
    payment_total = payments.aggregate(total=Sum("amount"))
    brand = _resolve_active_brand(request)

    filename = f"z_report_{date}_{branch or 'all'}.pdf"
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Image as RLImage
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception:
        params = request.GET.copy()
        params["autoprint"] = "1"
        url = f"{reverse('reports:z_report')}?{params.urlencode()}"
        return redirect(url)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )
    styles = getSampleStyleSheet()
    elements = []

    logo_added = False
    logo_bytes = brand.get("active_business_logo_bytes") or b""
    if logo_bytes:
        try:
            logo = RLImage(io.BytesIO(logo_bytes), width=28 * mm, height=28 * mm)
            elements.append(logo)
            elements.append(Spacer(1, 6))
            logo_added = True
        except Exception:
            try:
                from PIL import Image as PILImage

                with PILImage.open(io.BytesIO(logo_bytes)) as img:
                    converted = io.BytesIO()
                    img.convert("RGBA").save(converted, format="PNG")
                    converted.seek(0)
                    logo = RLImage(converted, width=28 * mm, height=28 * mm)
                    elements.append(logo)
                    elements.append(Spacer(1, 6))
                    logo_added = True
            except Exception:
                logo_added = False

    if not logo_added:
        logo_path = brand.get("active_business_logo_path") or ""
        if logo_path:
            try:
                logo = RLImage(logo_path, width=28 * mm, height=28 * mm)
                elements.append(logo)
                elements.append(Spacer(1, 6))
            except Exception:
                pass

    elements.append(Paragraph(f"{brand.get('active_business_name', 'Laundrex')} Z Report", styles["Title"]))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"Date: {date}", styles["Normal"]))
    elements.append(Paragraph(f"Branch: {branch or 'All'}", styles["Normal"]))
    elements.append(Paragraph(f"Generated at: {timezone.localtime().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 10))

    summary = [
        ["Metric", "Value"],
        ["Orders", order_totals.get("orders") or 0],
        ["Revenue", order_totals.get("revenue") or 0],
        ["Paid", order_totals.get("paid") or 0],
        ["Outstanding", order_totals.get("balance") or 0],
        ["Payments Total", payment_total.get("total") or 0],
    ]
    table = Table(summary, colWidths=[doc.width / 2, doc.width / 2], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf1fb")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#163f73")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd9ec")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fbff")]),
            ]
        )
    )
    elements.append(Paragraph("Summary", styles["Heading3"]))
    elements.append(table)
    elements.append(Spacer(1, 10))

    by_method_rows = [["Method", "Count", "Total"]]
    if by_method:
        by_method_rows += [[row["label"], row["count"], row["total"]] for row in by_method]
    else:
        by_method_rows += [["No payments found.", "", ""]]
    method_table = Table(by_method_rows, colWidths=[doc.width * 0.45, doc.width * 0.2, doc.width * 0.35], repeatRows=1)
    method_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf1fb")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#163f73")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd9ec")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fbff")]),
            ]
        )
    )
    elements.append(Paragraph("Payments by Method", styles["Heading3"]))
    elements.append(method_table)

    doc.build(elements)
    pdf_data = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_data, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@permission_required("orders.can_view_reports", raise_exception=True)
def export_reports_csv(request):
    context = _build_export_context(request)
    tables = _pack_tables(context)
    filename = f"reports_{context.get('selected_pack', 'all')}_{context.get('start') or 'from'}_{context.get('end') or 'to'}.csv"
    csv_response = HttpResponse(content_type="text/csv; charset=utf-8")
    csv_response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(csv_response)
    writer.writerow([f"{context.get('active_business_name', 'Laundrex')} Reports Export"])
    writer.writerow(["Report Pack", context.get("selected_pack", "all")])
    writer.writerow(["Mode", context.get("mode", "") or "all"])
    writer.writerow(["Period", context.get("period", "custom")])
    writer.writerow(["Start", context.get("start", "")])
    writer.writerow(["End", context.get("end", "")])
    writer.writerow([])
    for title, headers, rows in tables:
        writer.writerow([title])
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
        writer.writerow([])
    return csv_response


@login_required
@permission_required("orders.can_view_reports", raise_exception=True)
def export_reports_excel(request):
    context = _build_export_context(request)
    tables = _pack_tables(context)
    filename = f"reports_{context.get('selected_pack', 'all')}_{context.get('start') or 'from'}_{context.get('end') or 'to'}.xlsx"

    try:
        import tempfile
        from openpyxl import Workbook
        from openpyxl.styles import Font
        from openpyxl.drawing.image import Image as XLImage
    except Exception:
        # Fallback to HTML-based Excel without logo to avoid broken linked-image placeholders.
        fallback_name = filename.replace(".xlsx", ".xls")
        xls_response = HttpResponse(content_type="application/vnd.ms-excel; charset=utf-8")
        xls_response["Content-Disposition"] = f'attachment; filename="{fallback_name}"'
        html = [
            "<html><head><meta charset='utf-8'></head><body>",
            f"<h2>{context.get('active_business_name', 'Laundrex')} Reports Export</h2>",
            f"<p><b>Report Pack:</b> {context.get('selected_pack','all')}<br>",
            f"<b>Mode:</b> {context.get('mode','') or 'all'}<br>",
            f"<b>Period:</b> {context.get('period','custom')}<br>",
            f"<b>Start:</b> {context.get('start','')}<br>",
            f"<b>End:</b> {context.get('end','')}</p>",
        ]
        for title, headers, rows in tables:
            html.append(f"<h3>{title}</h3>")
            html.append("<table border='1' cellspacing='0' cellpadding='4'>")
            html.append("<tr>" + "".join([f"<th>{h}</th>" for h in headers]) + "</tr>")
            for row in rows:
                html.append("<tr>" + "".join([f"<td>{v}</td>" for v in row]) + "</tr>")
            html.append("</table><br>")
        html.append("</body></html>")
        xls_response.write("".join(html))
        return xls_response

    wb = Workbook()
    ws = wb.active
    ws.title = "Reports"

    row_idx = 1
    temp_logo = None
    has_pillow = True
    try:
        from PIL import Image as PILImage
    except Exception:
        has_pillow = False

    logo_bytes = context.get("active_business_logo_bytes") or b""
    if logo_bytes and has_pillow:
        try:
            converted = io.BytesIO()
            with PILImage.open(io.BytesIO(logo_bytes)) as img:
                img.convert("RGBA").save(converted, format="PNG")
            converted.seek(0)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp.write(converted.getvalue())
            tmp.close()
            temp_logo = tmp.name
            logo = XLImage(temp_logo)
            logo.width = 96
            logo.height = 96
            ws.add_image(logo, "A1")
            row_idx = 7
        except Exception:
            row_idx = 1

    ws.cell(row=row_idx, column=1, value=f"{context.get('active_business_name', 'Laundrex')} Reports Export")
    ws.cell(row=row_idx, column=1).font = Font(bold=True, size=16)
    row_idx += 2

    meta_rows = [
        ("Report Pack", context.get("selected_pack", "all")),
        ("Mode", context.get("mode", "") or "all"),
        ("Period", context.get("period", "custom")),
        ("Start", context.get("start", "")),
        ("End", context.get("end", "")),
    ]
    for k, v in meta_rows:
        ws.cell(row=row_idx, column=1, value=k).font = Font(bold=True)
        ws.cell(row=row_idx, column=2, value=str(v))
        row_idx += 1
    row_idx += 1

    for title, headers, rows in tables:
        ws.cell(row=row_idx, column=1, value=str(title)).font = Font(bold=True, size=13)
        row_idx += 1

        for col, h in enumerate(headers, start=1):
            ws.cell(row=row_idx, column=col, value=str(h)).font = Font(bold=True)
        row_idx += 1

        for data_row in (rows or []):
            for col, v in enumerate(data_row, start=1):
                ws.cell(row=row_idx, column=col, value=v)
            row_idx += 1
        row_idx += 2

    # Light auto-width.
    for col in ws.columns:
        letter = col[0].column_letter
        max_len = 0
        for c in col:
            text = "" if c.value is None else str(c.value)
            if len(text) > max_len:
                max_len = len(text)
        ws.column_dimensions[letter].width = min(max(12, max_len + 2), 48)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    response = HttpResponse(
        stream.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    if temp_logo:
        try:
            Path(temp_logo).unlink(missing_ok=True)
        except Exception:
            pass

    return response


@login_required
@permission_required("orders.can_view_reports", raise_exception=True)
def export_reports_pdf(request):
    context = _build_export_context(request)
    tables = _pack_tables(context)
    filename = f"reports_{context.get('selected_pack', 'all')}_{context.get('start') or 'from'}_{context.get('end') or 'to'}.pdf"

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Image as RLImage
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception:
        params = request.GET.copy()
        params["autoprint"] = "1"
        url = f"{reverse('reports:home')}?{params.urlencode()}"
        return redirect(url)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )
    styles = getSampleStyleSheet()
    elements = []

    logo_bytes = context.get("active_business_logo_bytes") or b""
    logo_added = False
    if logo_bytes:
        try:
            logo = RLImage(io.BytesIO(logo_bytes), width=28 * mm, height=28 * mm)
            elements.append(logo)
            elements.append(Spacer(1, 6))
            logo_added = True
        except Exception:
            # Some JPEG variants fail direct decode; convert to PNG via Pillow if available.
            try:
                from PIL import Image as PILImage

                with PILImage.open(io.BytesIO(logo_bytes)) as img:
                    converted = io.BytesIO()
                    img.convert("RGBA").save(converted, format="PNG")
                    converted.seek(0)
                    logo = RLImage(converted, width=28 * mm, height=28 * mm)
                    elements.append(logo)
                    elements.append(Spacer(1, 6))
                    logo_added = True
            except Exception:
                logo_added = False

    if not logo_added:
        logo_path = context.get("active_business_logo_path") or ""
        if logo_path:
            try:
                logo = RLImage(logo_path, width=28 * mm, height=28 * mm)
                elements.append(logo)
                elements.append(Spacer(1, 6))
            except Exception:
                pass
    elements.append(Paragraph(f"{context.get('active_business_name', 'Laundrex')} Reports Export", styles["Title"]))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"Report Pack: {context.get('selected_pack', 'all')}", styles["Normal"]))
    elements.append(Paragraph(f"Mode: {context.get('mode', '') or 'all'}", styles["Normal"]))
    elements.append(Paragraph(f"Period: {context.get('period', 'custom')}", styles["Normal"]))
    elements.append(Paragraph(f"Start: {context.get('start', '')}", styles["Normal"]))
    elements.append(Paragraph(f"End: {context.get('end', '')}", styles["Normal"]))
    elements.append(Spacer(1, 10))

    for title, headers, rows in tables:
        elements.append(Paragraph(str(title), styles["Heading3"]))

        safe_rows = rows or [["-", "-", "-", "-"][: len(headers)]]
        table_data = [headers] + [[str(v) for v in row] for row in safe_rows]
        col_width = (doc.width / max(1, len(headers)))
        table = Table(table_data, colWidths=[col_width] * len(headers), repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf1fb")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#163f73")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd9ec")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fbff")]),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 10))

    doc.build(elements)
    pdf_data = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_data, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
