from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("settings_app", "0006_sync_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="BankTransferSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("enabled", models.BooleanField(default=True)),
                ("bank_name", models.CharField(blank=True, default="", max_length=120)),
                ("account_name", models.CharField(blank=True, default="", max_length=120)),
                ("account_number", models.CharField(blank=True, default="", max_length=120)),
                ("iban", models.CharField(blank=True, default="", max_length=120)),
                ("instructions", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
