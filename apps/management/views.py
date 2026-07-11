from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404

from .models import Branch, AuditLog
from apps.accounts.models import StaffProfile


@login_required
@permission_required("orders.can_manage_staff", raise_exception=True)
def management_home(request):
    branches = Branch.objects.all().order_by("name")[:6]
    users = get_user_model().objects.all().order_by("username")[:6]
    return render(request, "management/home.html", {
        "branches": branches,
        "users": users,
    })


@login_required
@permission_required("orders.can_manage_staff", raise_exception=True)
def audit_logs(request):
    q = (request.GET.get("q") or "").strip()
    action = (request.GET.get("action") or "").strip()
    branch = (request.GET.get("branch") or "").strip()

    qs = AuditLog.objects.select_related("user", "branch").order_by("-created_at")
    if q:
        qs = qs.filter(Q(entity_id__icontains=q) | Q(message__icontains=q) | Q(user__username__icontains=q))
    if action:
        qs = qs.filter(action=action)
    if branch:
        qs = qs.filter(branch__code__icontains=branch)

    return render(request, "management/audit_logs.html", {
        "logs": qs[:500],
        "q": q,
        "action": action,
        "branch": branch,
    })


@login_required
@permission_required("orders.can_manage_staff", raise_exception=True)
def branch_list(request):
    if request.method == "POST":
        code = (request.POST.get("code") or "").strip().lower()
        name = (request.POST.get("name") or "").strip()
        if code and name:
            Branch.objects.get_or_create(code=code, defaults={"name": name})
        return redirect("management:branches")

    branches = Branch.objects.all().order_by("name")
    return render(request, "management/branches_list.html", {"branches": branches})


@login_required
@permission_required("orders.can_manage_staff", raise_exception=True)
def branch_detail(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id)

    if request.method == "POST":
        branch.name = (request.POST.get("name") or "").strip()
        branch.code = (request.POST.get("code") or "").strip().lower()
        branch.active = (request.POST.get("active") or "") == "1"
        branch.address = (request.POST.get("address") or "").strip()
        branch.address_ar = (request.POST.get("address_ar") or "").strip()
        branch.phone = (request.POST.get("phone") or "").strip()
        branch.allow_discounts = (request.POST.get("allow_discounts") or "") == "1"
        branch.receipt_header = (request.POST.get("receipt_header") or "").strip()
        branch.receipt_footer = (request.POST.get("receipt_footer") or "").strip()
        branch.receipt_footer_ar = (request.POST.get("receipt_footer_ar") or "").strip()
        branch.cr_number = (request.POST.get("cr_number") or "").strip()
        branch.vat_number = (request.POST.get("vat_number") or "").strip()
        branch.printer_name = (request.POST.get("printer_name") or "").strip()
        branch.receipt_template = (request.POST.get("receipt_template") or "80mm").strip()
        branch.delivery_slot_templates = (request.POST.get("delivery_slot_templates") or "").strip()
        if request.POST.get("clear_receipt_logo") == "1":
            branch.receipt_logo = None
        elif request.FILES.get("receipt_logo"):
            branch.receipt_logo = request.FILES.get("receipt_logo")
        try:
            branch.tax_rate = request.POST.get("tax_rate") or 0
        except Exception:
            branch.tax_rate = 0
        try:
            branch.max_discount_percent = request.POST.get("max_discount_percent") or 0
        except Exception:
            branch.max_discount_percent = 0

        try:
            branch.receipt_copies = int(request.POST.get("receipt_copies") or 1)
        except Exception:
            branch.receipt_copies = 1
        branch.save()
        return redirect("management:branch_detail", branch_id=branch.id)

    return render(request, "management/branch_detail.html", {"branch": branch})


@login_required
@permission_required("orders.can_manage_staff", raise_exception=True)
def staff_list(request):
    q = (request.GET.get("q") or "").strip()
    branch = (request.GET.get("branch") or "").strip()

    User = get_user_model()
    qs = User.objects.all().order_by("username")
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q))

    profiles = StaffProfile.objects.select_related("branch", "user")
    if branch:
        profiles = profiles.filter(branch__code__icontains=branch)

    profiles_map = {p.user_id: p for p in profiles}
    users = list(qs[:300])
    for u in users:
        u.profile = profiles_map.get(u.id)

    branches = Branch.objects.all().order_by("name")
    return render(request, "management/staff_list.html", {
        "users": users,
        "branches": branches,
        "q": q,
        "branch": branch,
    })


@login_required
@permission_required("orders.can_manage_staff", raise_exception=True)
def staff_create(request):
    User = get_user_model()
    error = ""

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        email = (request.POST.get("email") or "").strip()
        password = (request.POST.get("password") or "").strip()
        branch_id = request.POST.get("branch") or ""
        preferred_language = (request.POST.get("preferred_language") or "en").strip()
        can_override_branch = (request.POST.get("can_override_branch") or "") == "1"
        is_active = (request.POST.get("is_active") or "1") == "1"

        if not username or not password:
            error = "Username and password are required."
        elif User.objects.filter(username__iexact=username).exists():
            error = "Username already exists."
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )
            user.is_staff = True
            user.is_active = is_active
            user.save(update_fields=["is_staff", "is_active", "email"])

            profile, _ = StaffProfile.objects.get_or_create(user=user)
            profile.branch = Branch.objects.filter(id=branch_id).first() if branch_id else None
            profile.can_override_branch = can_override_branch
            profile.preferred_language = preferred_language if preferred_language in ("en", "ar") else "en"
            profile.save()

            groups = request.POST.getlist("groups")
            user.groups.set(groups)
            return redirect("management:staff_detail", user_id=user.id)

    branches = Branch.objects.all().order_by("name")
    groups = Group.objects.all().order_by("name")
    return render(request, "management/staff_create.html", {
        "branches": branches,
        "groups": groups,
        "error": error,
    })


@login_required
@permission_required("orders.can_manage_staff", raise_exception=True)
def staff_detail(request, user_id: int):
    User = get_user_model()
    user = get_object_or_404(User, id=user_id)
    profile, _ = StaffProfile.objects.get_or_create(user=user)

    if request.method == "POST":
        branch_id = request.POST.get("branch") or ""
        profile.branch = Branch.objects.filter(id=branch_id).first() if branch_id else None
        profile.can_override_branch = (request.POST.get("can_override_branch") or "") == "1"
        profile.preferred_language = (request.POST.get("preferred_language") or "en").strip()
        profile.save()

        groups = request.POST.getlist("groups")
        user.groups.set(groups)
        return redirect("management:staff_detail", user_id=user.id)

    branches = Branch.objects.all().order_by("name")
    groups = user.groups.model.objects.all().order_by("name")
    return render(request, "management/staff_detail.html", {
        "staff_user": user,
        "profile": profile,
        "branches": branches,
        "groups": groups,
    })
