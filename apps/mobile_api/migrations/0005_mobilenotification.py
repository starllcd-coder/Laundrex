from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0016_order_extended_statuses"),
        ("mobile_api", "0004_mobileordermeta_fulfillment_mode"),
    ]

    operations = [
        migrations.CreateModel(
            name="MobileNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=140)),
                ("message", models.CharField(max_length=255)),
                ("event_code", models.CharField(blank=True, default="", max_length=40)),
                ("is_read", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mobile_notifications", to="orders.customer")),
                ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="mobile_notifications", to="orders.order")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
