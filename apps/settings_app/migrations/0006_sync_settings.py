from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("settings_app", "0005_add_pickup_reminder_template"),
    ]

    operations = [
        migrations.CreateModel(
            name="SyncSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("enabled", models.BooleanField(default=False)),
                ("endpoints_enabled", models.BooleanField(default=False)),
                ("api_token", models.CharField(blank=True, default="", max_length=120)),
                ("cloud_base_url", models.CharField(blank=True, default="", max_length=255)),
                ("interval_seconds", models.PositiveIntegerField(default=120)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
