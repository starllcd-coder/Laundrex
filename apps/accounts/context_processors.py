from django.utils import translation
from django.utils.translation import gettext as _

from apps.accounts.models import StaffProfile
from apps.accounts.utils import branch_display_label
from apps.management.models import Branch


def active_branch_label(request):
    """Add `active_branch_label` to template context."""
    code = (request.session.get("active_branch") or "").strip()
    lang = (translation.get_language() or "en").split("-")[0]
    label = None
    business_name = None
    branch = None

    try:
        if code:
            branch = Branch.objects.filter(code__iexact=code).first() or Branch.objects.filter(name__iexact=code).first()

        # If session value is stale after branch rename, recover from profile.
        if not branch and request.user.is_authenticated:
            profile = StaffProfile.objects.select_related("branch").filter(user=request.user).first()
            if profile and profile.branch:
                branch = profile.branch
                request.session["active_branch"] = branch.code

        # Last fallback for admins/superusers with no profile branch.
        if not branch:
            branch = Branch.objects.filter(active=True).order_by("name").first()
            if branch:
                request.session["active_branch"] = branch.code

        if branch:
            label = branch_display_label(branch, lang)
            business_name = branch.name
    except Exception:
        label = code or None

    if not label:
        label = _("Branch")

    return {
        "active_branch_label": label,
        "active_business_name": business_name or "Laundrex",
        "active_user_role": _resolve_user_role(request),
    }


def _resolve_user_role(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return _("Guest")
    if user.is_superuser:
        return _("Admin")
    if user.has_perm("orders.can_manage_staff"):
        return _("Manager")
    if user.has_perm("orders.can_manage_delivery"):
        return _("Delivery")
    if user.has_perm("orders.can_view_reports"):
        return _("Supervisor")
    return _("Staff")
