from apps.accounts.models import StaffProfile

_BRANCH_CITY_BY_CODE = {
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

_BRANCH_CITY_AR_BY_CODE = {
    "SLL": "صلالة",
    "MCT": "مسقط",
    "SEB": "السيب",
    "SOH": "صحار",
    "NZW": "نزوى",
    "SR": "صور",
    "BRK": "بركاء",
    "RUS": "الرستاق",
    "IBR": "عبري",
    "KHS": "خصب",
    "BRM": "البريمي",
    "DQM": "الدقم",
    "ADM": "آدم",
    "THM": "ثمريت",
    "HMA": "هيماء",
}


def user_can_view_all_branches(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.has_perm("orders.view_all_branches")


def get_effective_branch(request):
    profile = None
    if request.user.is_authenticated:
        profile = StaffProfile.objects.select_related("branch").filter(user=request.user).first()

    if profile and profile.branch:
        if not profile.can_override_branch and not user_can_view_all_branches(request.user):
            return profile.branch.code

    return (request.session.get("active_branch") or "").strip()


def scope_queryset_to_branch(request, qs, field_name="branch"):
    if user_can_view_all_branches(request.user):
        return qs

    branch = get_effective_branch(request)
    if not branch:
        return qs.none()

    return qs.filter(**{field_name: branch})


def branch_display_label(branch, lang="en"):
    code = (getattr(branch, "code", "") or "").strip().upper()
    if str(lang).lower().startswith("ar"):
        if getattr(branch, "name_ar", ""):
            return branch.name_ar
        return _BRANCH_CITY_AR_BY_CODE.get(code) or getattr(branch, "name", "") or code
    return _BRANCH_CITY_BY_CODE.get(code) or getattr(branch, "name", "") or code
