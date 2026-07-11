from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.translation import gettext as _

from apps.orders.models import Order
from apps.accounts.utils import scope_queryset_to_branch
from apps.management.utils import log_audit
from .models import Payment


@login_required
def payments_list(request):
    q = (request.GET.get("q") or "").strip()
    branch = (request.GET.get("branch") or "").strip()
    status = (request.GET.get("status") or "").strip()

    qs = Order.objects.select_related("customer", "cashier").order_by("-created_at")
    qs = scope_queryset_to_branch(request, qs)

    if q:
        qs = qs.filter(
            Q(order_no__icontains=q)
            | Q(customer__phone__icontains=q)
            | Q(customer__name__icontains=q)
        )

    if branch:
        qs = qs.filter(branch__icontains=branch)

    if status:
        qs = qs.filter(status=status)

    # show only "real orders"
    qs = qs.filter(total__gt=0)

    return render(request, "payments/list.html", {
        "orders": qs[:500],
        "q": q,
        "branch": branch,
        "status": status,
        "status_choices": Order.Status.choices,
    })


@login_required
def payment_detail(request, order_no: str):
    order = get_object_or_404(
        scope_queryset_to_branch(request, Order.objects.select_related("customer", "cashier").prefetch_related("items", "payments")),
        order_no=order_no
    )
    error = None

    if request.method == "POST":
        if not request.user.has_perm("orders.can_discount"):
            return HttpResponseForbidden(_("Not allowed"))
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
            error = _("Enter a valid payment amount")
        elif not error:
            method_label = method
            if method in Payment.Method.values:
                method_label = str(Payment.Method(method).label)
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
            log_audit(
                action="payment_add",
                entity_type="order",
                entity_id=order.order_no,
                message=f"{method_label} {amount}",
                user=request.user,
                branch_code=order.branch,
            )
            return redirect("payments:detail", order_no=order.order_no)

    payments = order.payments.all().order_by("-created_at")

    return render(
        request,
        "payments/detail.html",
        {
            "order": order,
            "payments": payments,
            "method_choices": Payment.Method.choices,
            "error": error,
        },
    )
