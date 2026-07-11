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
            name="PhoneOTP",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("phone", models.CharField(db_index=True, max_length=40)),
                ("purpose", models.CharField(choices=[("login", "Login"), ("register", "Register")], default="login", max_length=20)),
                ("code", models.CharField(max_length=6)),
                ("is_used", models.BooleanField(default=False)),
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="CustomerAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("phone", models.CharField(db_index=True, max_length=40, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="account", to="orders.customer")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="customer_account", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="SavedAddress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(default="Home", max_length=80)),
                ("city", models.CharField(blank=True, default="", max_length=120)),
                ("area", models.CharField(blank=True, default="", max_length=120)),
                ("address_line_1", models.CharField(max_length=255)),
                ("address_line_2", models.CharField(blank=True, default="", max_length=255)),
                ("building", models.CharField(blank=True, default="", max_length=120)),
                ("is_default", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="saved_addresses", to="orders.customer")),
            ],
            options={"ordering": ["-is_default", "-updated_at"]},
        ),
    ]
