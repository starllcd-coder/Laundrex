from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_errorlog"),
    ]

    operations = [
        migrations.CreateModel(
            name="SyncState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=64, unique=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
