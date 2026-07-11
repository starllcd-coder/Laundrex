from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.utils import translation

from apps.management.models import Branch
from .utils import branch_display_label
from .models import StaffProfile
from .utils import user_can_view_all_branches

@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    error = None
    profile = None
    if request.user.is_authenticated:
        profile = StaffProfile.objects.select_related("branch").filter(user=request.user).first()

    if request.method == "POST":
        lang = (request.POST.get("lang") or "").strip()
        if lang in ("en", "ar"):
            request.session["django_language"] = lang
            translation.activate(lang)

        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        branch = request.POST.get("branch", "")
        remember = request.POST.get("remember") == "on"
        user = authenticate(request, username=username, password=password)
        if user is None:
            error = "Invalid username or password"
        else:
            login(request, user)
            profile = StaffProfile.objects.select_related("branch").filter(user=user).first()
            if profile and profile.branch and not profile.can_override_branch and not user_can_view_all_branches(user):
                branch = profile.branch.code

            if lang in ("en", "ar") and profile and profile.preferred_language != lang:
                profile.preferred_language = lang
                profile.save(update_fields=["preferred_language"])

            if not branch:
                error = "Please select a branch"
                logout(request)
                return render(request, "accounts/login.html", {
                    "error": error,
                    "branches": _load_branches(profile, user),
                    "branch_locked": bool(profile and profile.branch and not profile.can_override_branch),
                })

            if not remember:
                # Expire session when the browser closes if not remembered.
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(settings.SESSION_COOKIE_AGE)
            request.session["active_branch"] = branch
            final_lang = None
            if profile and profile.preferred_language:
                final_lang = profile.preferred_language
            elif lang in ("en", "ar"):
                final_lang = lang

            if final_lang:
                request.session["django_language"] = final_lang
                translation.activate(final_lang)

            response = redirect("core:home")
            if final_lang:
                response.set_cookie(settings.LANGUAGE_COOKIE_NAME, final_lang)
            return response

    return render(request, "accounts/login.html", {
        "error": error,
        "branches": _load_branches(profile, request.user),
        "branch_locked": bool(profile and profile.branch and not profile.can_override_branch),
    })


@require_http_methods(["POST"])
def set_language(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")

    lang = (request.POST.get("lang") or "en").strip()
    if lang not in ("en", "ar"):
        lang = "en"

    profile, _ = StaffProfile.objects.get_or_create(user=request.user)
    profile.preferred_language = lang
    profile.save(update_fields=["preferred_language"])

    request.session["django_language"] = lang
    translation.activate(lang)

    response = redirect(request.POST.get("next") or "core:home")
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang)
    return response


def _branch_label(branch, lang):
    return branch_display_label(branch, lang)


def _load_branches(profile, user):
    lang = (translation.get_language() or "en").split("-")[0]
    qs = Branch.objects.filter(active=True).order_by("name")
    if profile and profile.branch and not profile.can_override_branch and not user_can_view_all_branches(user):
        return [(profile.branch.code, _branch_label(profile.branch, lang))]
    return [(b.code, _branch_label(b, lang)) for b in qs]

def logout_view(request):
    logout(request)
    return redirect("accounts:login")

