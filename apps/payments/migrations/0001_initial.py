from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("method", models.CharField(choices=[("CASH", "Cash"), ("CARD", "Card"), ("WALLET", "Wallet"), ("BANK", "Bank Transfer")], default="CASH", max_length=10)),
                ("amount", models.DecimalField(decimal_places=3, default=0, max_digits=10)),
                ("reference", models.CharField(blank=True, default="", max_length=120)),
                ("note", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payments", to="orders.order")),
            ],
        ),
    ]
