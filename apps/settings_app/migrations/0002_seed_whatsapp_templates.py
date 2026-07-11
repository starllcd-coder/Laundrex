from django.db import migrations


def seed_templates(apps, schema_editor):
    WhatsAppTemplate = apps.get_model("settings_app", "WhatsAppTemplate")
    WhatsAppSettings = apps.get_model("settings_app", "WhatsAppSettings")

    if not WhatsAppSettings.objects.exists():
        WhatsAppSettings.objects.create(enabled=False, sender_name="Laundrex", allow_manual_send=True)

    defaults = [
        (
            "order_received",
            "Order Received",
            "Hello! Your order #{order_no} is received at {branch}. Total: {total} OMR. Pickup code: {pickup_code}.",
            "مرحبا! تم استلام طلبك رقم {order_no} في {branch}. الإجمالي: {total} ريال. رمز الاستلام: {pickup_code}.",
        ),
        (
            "ready_pickup",
            "Ready for Pickup",
            "Your order #{order_no} is ready for pickup at {branch}. Pickup code: {pickup_code}.",
            "طلبك رقم {order_no} جاهز للاستلام من {branch}. رمز الاستلام: {pickup_code}.",
        ),
        (
            "out_for_delivery",
            "Out for Delivery",
            "Your order #{order_no} is out for delivery. Track: {pickup_link}",
            "طلبك رقم {order_no} في طريقه للتوصيل. تتبع: {pickup_link}",
        ),
        (
            "payment_due",
            "Payment Due",
            "Payment due for order #{order_no}: {amount_due} OMR. Total: {total} OMR.",
            "المبلغ المتبقي للطلب رقم {order_no}: {amount_due} ريال. الإجمالي: {total} ريال.",
        ),
        (
            "receipt",
            "Receipt",
            "Receipt for order #{order_no}: Total {total} OMR. Pickup: {pickup_link}",
            "إيصال الطلب رقم {order_no}: الإجمالي {total} ريال. رابط الاستلام: {pickup_link}",
        ),
    ]

    for key, name, body_en, body_ar in defaults:
        WhatsAppTemplate.objects.get_or_create(
            key=key,
            defaults={
                "name": name,
                "enabled": True,
                "body_en": body_en,
                "body_ar": body_ar,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("settings_app", "0001_whatsapp_models"),
    ]

    operations = [
        migrations.RunPython(seed_templates, migrations.RunPython.noop),
    ]
