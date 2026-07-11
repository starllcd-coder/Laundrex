import re
import requests
from datetime import timedelta
from django.conf import settings
from django.utils import timezone

from .models import WhatsAppSettings, WhatsAppTemplate, WhatsAppMessageLog, SyncSettings


PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def get_whatsapp_settings():
    return WhatsAppSettings.objects.first()


def get_sync_settings():
    return SyncSettings.objects.first()


def get_template(template_key):
    return WhatsAppTemplate.objects.filter(key=template_key).first()


def build_context(order, customer, branch_name=""):
    pickup_code = f"LAUNDREX:{order.order_no}" if order else ""
    pickup_token = ""
    if order:
        pickup_token = order.ensure_pickup_token()
    pickup_link = f"{settings.SITE_BASE_URL}/p/{pickup_token}/" if pickup_token else ""
    return {
        "order_no": order.order_no if order else "",
        "total": str(order.total) if order else "",
        "amount_due": str(order.balance) if order else "",
        "pickup_code": pickup_code,
        "branch": branch_name,
        "pickup_link": pickup_link,
        "delivery_fee": str(order.delivery_fee) if order else "",
    }


def render_body(template_text, context):
    body = template_text or ""
    for key, value in context.items():
        body = body.replace("{" + key + "}", str(value))
    return body


def extract_placeholders(template_text):
    return PLACEHOLDER_RE.findall(template_text or "")


def _send_whatsapp_message(order, customer, branch_name, template_key, language, allow_manual_check=True):
    wa_settings = get_whatsapp_settings()
    template = get_template(template_key)

    if not settings.WHATSAPP_ENABLED:
        return False, "WhatsApp disabled"
    if not wa_settings or not wa_settings.enabled:
        return False, "WhatsApp not enabled in settings"
    if allow_manual_check and not wa_settings.allow_manual_send:
        return False, "Manual send disabled"
    if not template or not template.enabled:
        return False, "Template disabled"

    to_number = (customer.whatsapp_number or customer.phone or "").strip()
    if not to_number:
        return False, "Missing WhatsApp number"
    if not customer.whatsapp_opt_in:
        return False, "Customer not opted in"

    # Basic rate limit: 1 message per minute per number
    recent = WhatsAppMessageLog.objects.filter(
        to_number=to_number,
        created_at__gte=timezone.now() - timedelta(seconds=60),
    )
    if recent.exists():
        return False, "Rate limit: try again in a minute"

    body = template.body_ar if language == "ar" else template.body_en
    template_name = template.template_name_ar if language == "ar" else template.template_name_en
    if not template_name:
        return False, "Template name missing"

    context = build_context(order, customer, branch_name)
    rendered_body = render_body(body, context)

    placeholders = extract_placeholders(body)
    parameters = [{"type": "text", "text": str(context.get(k, ""))} for k in placeholders]

    log = WhatsAppMessageLog.objects.create(
        order=order,
        customer=customer,
        template_key=template_key,
        language=language,
        to_number=to_number,
        message_body=rendered_body,
        status="queued",
        attempts=1,
    )

    url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "ar" if language == "ar" else "en"},
            "components": [{"type": "body", "parameters": parameters}],
        },
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=20)
        if res.status_code >= 400:
            log.status = "failed"
            log.last_error = f"HTTP {res.status_code}: {res.text[:200]}"
            log.save(update_fields=["status", "last_error"])
            return False, "Send failed"

        data = res.json()
        msg_id = ""
        if data.get("messages"):
            msg_id = data["messages"][0].get("id", "")
        log.status = "sent"
        log.provider_message_id = msg_id
        log.last_status_at = timezone.now()
        log.save(update_fields=["status", "provider_message_id", "last_status_at"])
        return True, "Sent"
    except Exception as exc:
        log.status = "failed"
        log.last_error = str(exc)[:200]
        log.save(update_fields=["status", "last_error"])
        return False, "Send failed"


def send_whatsapp_message(order, customer, branch_name, template_key, language, user=None):
    return _send_whatsapp_message(
        order,
        customer,
        branch_name,
        template_key,
        language,
        allow_manual_check=True,
    )


def send_whatsapp_message_auto(order, customer, branch_name, template_key, language, user=None):
    wa_settings = get_whatsapp_settings()
    if not wa_settings or not wa_settings.allow_auto_send:
        return False, "Auto send disabled"
    return _send_whatsapp_message(
        order,
        customer,
        branch_name,
        template_key,
        language,
        allow_manual_check=False,
    )


def update_message_status(provider_message_id, status):
    log = WhatsAppMessageLog.objects.filter(provider_message_id=provider_message_id).first()
    if not log:
        return
    if status not in ["sent", "delivered", "read", "failed"]:
        return
    log.status = status
    log.last_status_at = timezone.now()
    log.save(update_fields=["status", "last_status_at"])
