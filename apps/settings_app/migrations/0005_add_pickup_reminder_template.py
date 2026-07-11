from django.db import migrations


def add_template(apps, schema_editor):
    WhatsAppTemplate = apps.get_model("settings_app", "WhatsAppTemplate")

    WhatsAppTemplate.objects.get_or_create(
        key="pickup_reminder",
        defaults={
            "name": "Pickup Reminder",
            "enabled": True,
            "template_name_en": "pickup_reminder",
            "template_name_ar": "pickup_reminder",
            "body_en": "Reminder: your order #{order_no} is ready for pickup at {branch}. Pickup code: {pickup_code}.",
            "body_ar": "تذكير: طلبك رقم {order_no} جاهز للاستلام من {branch}. رمز الاستلام: {pickup_code}.",
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("settings_app", "0004_update_whatsapp_template_names"),
    ]

    operations = [
        migrations.RunPython(add_template, migrations.RunPython.noop),
    ]
