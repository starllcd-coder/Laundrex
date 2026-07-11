from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("mobile_api", "0001_initial"),
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="savedaddress",
            name="latitude",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="savedaddress",
            name="longitude",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="DeviceToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(max_length=255)),
                ("platform", models.CharField(blank=True, default="", max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="device_tokens", to="orders.customer")),
            ],
            options={"unique_together": {("customer", "token")}},
        ),
        migrations.CreateModel(
            name="MobileOrderMeta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payment_method", models.CharField(blank=True, default="", max_length=20)),
                ("transfer_reference", models.CharField(blank=True, default="", max_length=120)),
                ("receipt_name", models.CharField(blank=True, default="", max_length=255)),
                ("promo_code", models.CharField(blank=True, default="", max_length=40)),
                ("promo_discount", models.DecimalField(decimal_places=3, default=0, max_digits=10)),
                ("points_used", models.PositiveIntegerField(default=0)),
                ("customer_notes", models.CharField(blank=True, default="", max_length=255)),
                ("pickup_time_slot", models.CharField(blank=True, default="", max_length=120)),
                ("speed", models.CharField(blank=True, default="", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="mobile_meta", to="orders.order")),
            ],
        ),
    ]
