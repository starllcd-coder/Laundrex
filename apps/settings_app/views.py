import hashlib
import hmac
import json
import os
from types import SimpleNamespace
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.db.utils import OperationalError, ProgrammingError
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from .models import WhatsAppSettings, WhatsAppTemplate, BankTransferSettings, SyncSettings
from apps.core.models import SyncState
from .utils import update_message_status


@login_required
@permission_required("orders.can_manage_staff", raise_exception=True)
def settings_home(request):
    defaults = {
        "enabled": bool(getattr(settings, "BANK_TRANSFER_ENABLED", True)),
        "bank_name": getattr(settings, "BANK_TRANSFER_BANK_NAME", ""),
        "account_name": getattr(settings, "BANK_TRANSFER_ACCOUNT_NAME", ""),
        "account_number": getattr(settings, "BANK_TRANSFER_ACCOUNT_NUMBER", ""),
        "iban": getattr(settings, "BANK_TRANSFER_IBAN", ""),
        "instructions": getattr(settings, "BANK_TRANSFER_INSTRUCTIONS", ""),
    }
    try:
        bank_settings, _ = BankTransferSettings.objects.get_or_create(id=1, defaults=defaults)

        if request.method == "POST" and request.POST.get("form_type") == "bank_transfer":
            bank_settings.enabled = (request.POST.get("enabled") or "") == "1"
            bank_settings.bank_name = (request.POST.get("bank_name") or "").strip()
            bank_settings.account_name = (request.POST.get("account_name") or "").strip()
            bank_settings.account_number = (request.POST.get("account_number") or "").strip()
            bank_settings.iban = (request.POST.get("iban") or "").strip()
            bank_settings.instructions = (request.POST.get("instructions") or "").strip()
            bank_settings.save()
            return redirect("settings_app:home")
    except (OperationalError, ProgrammingError):
        bank_settings = SimpleNamespace(**defaults)

    settings_module = os.getenv("DJANGO_SETTINGS_MODULE") or getattr(settings, "SETTINGS_MODULE", "")
    db_name = str((settings.DATABASES.get("default", {}) or {}).get("NAME", ""))
    is_desktop_backend = settings_module.endswith("settings_desktop") or "desktop_app" in db_name.replace("\\", "/")

    sync_settings = None
    cloud_last_synced_at = None
    try:
        sync_settings = SyncSettings.objects.first()
        cloud_state = SyncState.objects.filter(key="cloud").first()
        cloud_last_synced_at = cloud_state.last_synced_at if cloud_state else None
    except (OperationalError, ProgrammingError):
        sync_settings = None
        cloud_last_synced_at = None

    desktop_backend = {
        "mode": "desktop_local" if is_desktop_backend else "shared_web",
        "settings_module": settings_module or "laundrex.settings",
        "db_path": db_name,
        "sync_enabled": bool(sync_settings.enabled) if sync_settings else False,
        "endpoints_enabled": bool(sync_settings.endpoints_enabled) if sync_settings else False,
        "cloud_base_url": (sync_settings.cloud_base_url if sync_settings else "") or "",
        "interval_seconds": int(sync_settings.interval_seconds) if sync_settings else 0,
        "last_synced_at": cloud_last_synced_at,
    }

    return render(
        request,
        "settings/home.html",
        {"bank_settings": bank_settings, "desktop_backend": desktop_backend},
    )


@login_required
@permission_required("orders.can_manage_staff", raise_exception=True)
def whatsapp_settings(request):
    settings_obj, _ = WhatsAppSettings.objects.get_or_create(id=1)
    templates = WhatsAppTemplate.objects.all().order_by("name")

    if request.method == "POST":
        settings_obj.enabled = (request.POST.get("enabled") or "") == "1"
        settings_obj.allow_manual_send = (request.POST.get("allow_manual_send") or "") == "1"
        settings_obj.allow_auto_send = (request.POST.get("allow_auto_send") or "") == "1"
        settings_obj.sender_name = (request.POST.get("sender_name") or "").strip()
        settings_obj.save()

        for t in templates:
            prefix = f"tpl_{t.id}_"
            t.enabled = (request.POST.get(prefix + "enabled") or "") == "1"
            t.template_name_en = (request.POST.get(prefix + "template_name_en") or "").strip()
            t.template_name_ar = (request.POST.get(prefix + "template_name_ar") or "").strip()
            t.body_en = (request.POST.get(prefix + "body_en") or "").strip()
            t.body_ar = (request.POST.get(prefix + "body_ar") or "").strip()
            t.save()

        return redirect("settings_app:whatsapp")

    return render(request, "settings/whatsapp.html", {
        "settings_obj": settings_obj,
        "templates": templates,
    })


def whatsapp_webhook(request):
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token == os.getenv("WHATSAPP_VERIFY_TOKEN", ""):
            return HttpResponse(challenge or "")
        return HttpResponseBadRequest("Invalid token")

    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

    if settings.WHATSAPP_APP_SECRET:
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not signature.startswith("sha256="):
            return HttpResponseBadRequest("Invalid signature")
        expected = "sha256=" + hmac.new(
            settings.WHATSAPP_APP_SECRET.encode("utf-8"),
            msg=request.body,
            digestmod=hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return HttpResponseBadRequest("Invalid signature")

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for status in value.get("statuses", []):
                msg_id = status.get("id", "")
                st = status.get("status", "")
                if msg_id and st:
                    update_message_status(msg_id, st)

    return JsonResponse({"ok": True})
