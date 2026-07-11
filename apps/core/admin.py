from django.contrib import admin, messages
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import path
from django.utils import timezone

from apps.management.models import AuditLog, Branch
from apps.mobile_api.models import MobileEvent, MobileNotification, MobileOrderMeta, PhoneOTP
from apps.orders.models import Customer, Order, OrderItem, OrderStatusLog
from apps.payments.models import Payment
from apps.settings_app.models import WhatsAppMessageLog
from .models import ErrorLog, ResetAuditLog, SyncState


def _today_str():
    return timezone.localdate().isoformat()


def _expected_phrase(scope, branch_code=""):
    if scope == "branch" and branch_code:
        return f"RESET {branch_code} {_today_str()}"
    return f"RESET ALL {_today_str()}"


def _delete_queryset(label, qs, deleted_counts):
    count = qs.count()
    if count:
        qs.delete()
    deleted_counts[label] = count


def reset_app_data_view(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Superuser access required.")

    branches = Branch.objects.all().order_by("name")
    default_scope = "all"
    default_branch_code = (request.session.get("active_branch") or "").strip().upper()

    if request.method == "POST":
        scope = (request.POST.get("scope") or "all").strip().lower()
        scope = "branch" if scope == "branch" else "all"
        branch_code = (request.POST.get("branch_code") or "").strip().upper()
        confirm_text = (request.POST.get("confirm_text") or "").strip()
        confirm_check = request.POST.get("confirm") == "on"

        selected_branch = None
        if scope == "branch":
            selected_branch = Branch.objects.filter(code__iexact=branch_code).first()
            if not selected_branch:
                messages.error(request, "Select a valid branch for branch-only reset.")
                return render(
                    request,
                    "admin/reset_data.html",
                    {
                        "title": "Reset App Data",
                        "branches": branches,
                        "scope": scope,
                        "branch_code": branch_code,
                        "today_str": _today_str(),
                        "expected_all": _expected_phrase("all"),
                        "expected_branch": _expected_phrase("branch", branch_code or "SLL"),
                        "models": _preview_counts(scope=scope, branch_code=branch_code),
                    },
                )

        expected = _expected_phrase(scope, branch_code if scope == "branch" else "")
        if confirm_text != expected or not confirm_check:
            messages.error(
                request,
                f"Confirmation required: type exactly '{expected}' and check the confirmation box.",
            )
        else:
            deleted_counts = {}
            with transaction.atomic():
                if scope == "all":
                    _delete_queryset("WhatsApp message logs", WhatsAppMessageLog.objects.all(), deleted_counts)
                    _delete_queryset("Payments", Payment.objects.all(), deleted_counts)
                    _delete_queryset("Order status logs", OrderStatusLog.objects.all(), deleted_counts)
                    _delete_queryset("Order items", OrderItem.objects.all(), deleted_counts)
                    _delete_queryset("Mobile notifications", MobileNotification.objects.all(), deleted_counts)
                    _delete_queryset("Mobile order meta", MobileOrderMeta.objects.all(), deleted_counts)
                    _delete_queryset("Orders", Order.objects.all(), deleted_counts)
                    _delete_queryset("Customers", Customer.objects.all(), deleted_counts)
                    _delete_queryset("Mobile events", MobileEvent.objects.all(), deleted_counts)
                    _delete_queryset("Phone OTP", PhoneOTP.objects.all(), deleted_counts)
                    _delete_queryset("Audit logs", AuditLog.objects.all(), deleted_counts)
                    summary = "All transactional data has been removed."
                else:
                    code = selected_branch.code
                    _delete_queryset(
                        "WhatsApp message logs",
                        WhatsAppMessageLog.objects.filter(order__branch__iexact=code),
                        deleted_counts,
                    )
                    _delete_queryset(
                        "Payments",
                        Payment.objects.filter(order__branch__iexact=code),
                        deleted_counts,
                    )
                    _delete_queryset(
                        "Order status logs",
                        OrderStatusLog.objects.filter(order__branch__iexact=code),
                        deleted_counts,
                    )
                    _delete_queryset(
                        "Order items",
                        OrderItem.objects.filter(order__branch__iexact=code),
                        deleted_counts,
                    )
                    _delete_queryset(
                        "Mobile notifications",
                        MobileNotification.objects.filter(order__branch__iexact=code),
                        deleted_counts,
                    )
                    _delete_queryset(
                        "Mobile order meta",
                        MobileOrderMeta.objects.filter(order__branch__iexact=code),
                        deleted_counts,
                    )
                    _delete_queryset(
                        "Orders",
                        Order.objects.filter(branch__iexact=code),
                        deleted_counts,
                    )
                    _delete_queryset(
                        "Branch audit logs",
                        AuditLog.objects.filter(branch__code__iexact=code),
                        deleted_counts,
                    )
                    # Safe cleanup: only customers no longer linked to any orders.
                    _delete_queryset(
                        "Orphan customers",
                        Customer.objects.filter(order__isnull=True),
                        deleted_counts,
                    )
                    summary = f"Branch transactional data removed for {code}."

                ResetAuditLog.objects.create(
                    scope=scope,
                    branch_code=(selected_branch.code if selected_branch else ""),
                    triggered_by=request.user,
                    confirmation_text=confirm_text,
                    deleted_counts=deleted_counts,
                    message=summary,
                )
            messages.success(request, summary)
            return redirect("admin:index")

    scope = (request.GET.get("scope") or default_scope).strip().lower()
    scope = "branch" if scope == "branch" else "all"
    branch_code = (request.GET.get("branch_code") or default_branch_code).strip().upper()
    context = {
        "title": "Reset App Data",
        "branches": branches,
        "scope": scope,
        "branch_code": branch_code,
        "today_str": _today_str(),
        "expected_all": _expected_phrase("all"),
        "expected_branch": _expected_phrase("branch", branch_code or "SLL"),
        "models": _preview_counts(scope=scope, branch_code=branch_code),
    }
    return render(request, "admin/reset_data.html", context)


def _preview_counts(scope="all", branch_code=""):
    if scope == "branch" and branch_code:
        return [
            {"label": "WhatsApp message logs", "count": WhatsAppMessageLog.objects.filter(order__branch__iexact=branch_code).count()},
            {"label": "Payments", "count": Payment.objects.filter(order__branch__iexact=branch_code).count()},
            {"label": "Order status logs", "count": OrderStatusLog.objects.filter(order__branch__iexact=branch_code).count()},
            {"label": "Order items", "count": OrderItem.objects.filter(order__branch__iexact=branch_code).count()},
            {"label": "Mobile notifications", "count": MobileNotification.objects.filter(order__branch__iexact=branch_code).count()},
            {"label": "Mobile order meta", "count": MobileOrderMeta.objects.filter(order__branch__iexact=branch_code).count()},
            {"label": "Orders", "count": Order.objects.filter(branch__iexact=branch_code).count()},
            {"label": "Branch audit logs", "count": AuditLog.objects.filter(branch__code__iexact=branch_code).count()},
            {"label": "Orphan customers (after reset)", "count": Customer.objects.filter(order__isnull=True).count()},
            {"label": "Phone OTP", "count": 0},
            {"label": "Mobile events", "count": 0},
        ]

    return [
        {"label": "WhatsApp message logs", "count": WhatsAppMessageLog.objects.count()},
        {"label": "Payments", "count": Payment.objects.count()},
        {"label": "Order status logs", "count": OrderStatusLog.objects.count()},
        {"label": "Order items", "count": OrderItem.objects.count()},
        {"label": "Mobile notifications", "count": MobileNotification.objects.count()},
        {"label": "Mobile order meta", "count": MobileOrderMeta.objects.count()},
        {"label": "Orders", "count": Order.objects.count()},
        {"label": "Customers", "count": Customer.objects.count()},
        {"label": "Phone OTP", "count": PhoneOTP.objects.count()},
        {"label": "Mobile events", "count": MobileEvent.objects.count()},
        {"label": "Audit logs", "count": AuditLog.objects.count()},
    ]


def sync_status_view(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Superuser access required.")

    state = SyncState.objects.filter(key="cloud").first()
    last_synced_at = state.last_synced_at if state else None

    recent_logs = ErrorLog.objects.filter(path__startswith="sync/").order_by("-created_at")[:50]

    context = {
        "title": "Sync Status",
        "last_synced_at": last_synced_at,
        "logs": recent_logs,
    }
    return render(request, "admin/sync_status.html", context)


_original_get_urls = admin.site.get_urls


def _get_urls():
    urls = _original_get_urls()
    custom_urls = [
        path("sync-status/", admin.site.admin_view(sync_status_view), name="sync_status"),
        path("reset-data/", admin.site.admin_view(reset_app_data_view), name="reset_app_data"),
    ]
    return custom_urls + urls


admin.site.get_urls = _get_urls


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "level", "path", "method", "branch_code", "user")
    list_filter = ("level", "branch_code")
    search_fields = ("message", "path", "traceback")


@admin.register(SyncState)
class SyncStateAdmin(admin.ModelAdmin):
    list_display = ("key", "last_synced_at", "updated_at")
    search_fields = ("key",)


@admin.register(ResetAuditLog)
class ResetAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "scope", "branch_code", "triggered_by", "message")
    list_filter = ("scope", "branch_code")
    search_fields = ("branch_code", "message", "triggered_by__username")
    readonly_fields = (
        "created_at",
        "scope",
        "branch_code",
        "triggered_by",
        "confirmation_text",
        "deleted_counts",
        "message",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
