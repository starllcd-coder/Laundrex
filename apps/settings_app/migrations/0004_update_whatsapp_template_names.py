from django.db import migrations


def update_templates(apps, schema_editor):
    WhatsAppTemplate = apps.get_model("settings_app", "WhatsAppTemplate")

    mapping = {
        "receipt": "order_received",
        "ready_pickup": "order_ready_for_pickup",
        "out_for_delivery": "order_out_for_delivery",
        "payment_due": "payment_due_reminder",
    }

    for key, template_name in mapping.items():
        tpl = WhatsAppTemplate.objects.filter(key=key).first()
        if not tpl:
            continue
        if not tpl.template_name_en:
            tpl.template_name_en = template_name
        tpl.save(update_fields=["template_name_en"])

    WhatsAppTemplate.objects.get_or_create(
        key="delivered",
        defaults={
            "name": "Delivered",
            "enabled": True,
            "template_name_en": "order_delivered",
            "body_en": "Your order #{order_no} has been delivered. Thank you for choosing {branch}.",
            "body_ar": "تم تسليم طلبك رقم {order_no}. شكرا لاختيارك {branch}.",
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("settings_app", "0003_add_allow_auto_send"),
    ]

    operations = [
        migrations.RunPython(update_templates, migrations.RunPython.noop),
    ]
