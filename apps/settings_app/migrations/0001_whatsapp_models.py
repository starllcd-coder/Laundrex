from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("orders", "0008_order_permissions"),
    ]

    operations = [
        migrations.CreateModel(
            name="WhatsAppSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("enabled", models.BooleanField(default=False)),
                ("sender_name", models.CharField(blank=True, default="", max_length=120)),
                ("allow_manual_send", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="WhatsAppTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=40, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("enabled", models.BooleanField(default=True)),
                ("template_name_en", models.CharField(blank=True, default="", max_length=120)),
                ("template_name_ar", models.CharField(blank=True, default="", max_length=120)),
                ("body_en", models.TextField(blank=True, default="")),
                ("body_ar", models.TextField(blank=True, default="")),
            ],
        ),
        migrations.CreateModel(
            name="WhatsAppMessageLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("template_key", models.CharField(max_length=40)),
                ("language", models.CharField(default="en", max_length=5)),
                ("to_number", models.CharField(max_length=40)),
                ("message_body", models.TextField(blank=True, default="")),
                ("status", models.CharField(choices=[("queued", "Queued"), ("sent", "Sent"), ("delivered", "Delivered"), ("read", "Read"), ("failed", "Failed")], default="queued", max_length=20)),
                ("provider_message_id", models.CharField(blank=True, default="", max_length=120)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.CharField(blank=True, default="", max_length=255)),
                ("last_status_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="orders.customer")),
                ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="orders.order")),
            ],
        ),
    ]
